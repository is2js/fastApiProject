### conn.py에 scoped_session 도입하기

    - 참고: https://github.dev/c0sogi/LLMChat

#### session에 관해서

- 참고 문서
    1. [Session vs scoped_session](https://jay-ji.tistory.com/114)
    2. [async_scoped_session과 context-local](https://jay-ji.tistory.com/115)
    3. [SQLAlchemy의 세션 관리](https://miintto.github.io/docs/python-sqlalchemy-session) 

#### async_scoped_session 도입

1. sqlalchemy의 생성자에서 async_sessionmaker를 받는 self._Session 대신 **`async_sessionmaker`를 인자로, `async_scoped_session()`으로 감싸서
   **
    - **async with yield가 되는 `async_scoped_session객체`를 만든다.**
    - **이 때, `future=True`옵션을 줘야, `Future 객체를 반환`히야 `async with`가 가능해진다.**
    - **또한 async_scoped_session을 만들 때 `asyncio.current_task`를 주면, 현재작업까지 scope를 가지게 한다.**
    - 기존
    ```python
    def init_app(self, app: FastAPI, **kwargs):
        # ...
        self._Session: async_sessionmaker[AsyncSession] = \
            async_sessionmaker(
            bind=self._async_engine, autocommit=False,
            autoflush=False,
            expire_on_commit=False,  # 필수 for schema
            )
    ```
    - 변경
    ```python
    from asyncio import current_task, shield

    def init_app(self, app: FastAPI, **kwargs):
    
        self._scoped_session: async_scoped_session[AsyncSession] | None = \
            async_scoped_session(
                async_sessionmaker(
                    bind=self._async_engine, autocommit=False, autoflush=False, future=True,
                    expire_on_commit=False  # refresh로 대체할려 했으나, 매번 select가 되어 필요시마다 하기로.
                ),
                scopefunc=current_task,
            )
    ```

2. **async_scoped_session + future=True의 session이라면, 이라면, yield만 하는게 아니라 외부에서도 `async with`로 사용가능해진다.**
    - async with가 가능 -> close 생략가능
    - **await shield()를 해주면 rollback시 에러를 스무스하게 다음줄로 가서 -> log를 찍을 수 있다.**
    ```python
    async def get_db(self):
        # 초기화 X -> Session cls없을 땐 에러
        if self._Session is None:
            raise Exception("must be called 'init_app'")
    
        # 세션 객체를 만들고, yield한 뒤, 돌아와서는 close까지 되도록
        # -> 실패시 rollback 후 + raise e 로 미들웨어에서 잡도록
        db_session = self._Session()
        # db_session = None
        try:
            yield db_session
        except Exception as e:
            # db_session.rollback()
            await db_session.rollback()
            raise e
        finally:
            # db_session.close()
            #  sqlalchemy.exc.IllegalStateChangeError: Method 'close()' can't be called here; method '_connection_for_bind()' is already in progress and this would cause an unexpected state change to <SessionTransactionState.CLOSED: 5>
            # 비동기session은 -> 이미 커밋 또는 롤백이 발생했을 때만 세션을 닫음
            if db_session.is_active:
                await db_session.close()
                
    ```
    ```python
    async def get_db(self) -> AsyncGenerator[AsyncSession, str]:
        # 초기화 X -> Session cls없을 땐 에러
        if self._scoped_session is None:
            raise Exception("must be called 'init_app'")
    
        async with self._scoped_session() as transaction:
            try:
                yield transaction
            except Exception as e:
                # shield는 rollback에서 예외가 발생하더라도, 밑에서 로그를 찍거나 할 수 있게 해준다.
                await shield(transaction.rollback())
                # logging
                raise e
    ```
    ```python
    @property
    def scoped_session(self):
        return self._scoped_session
    ```


3. **이제 외부에서 `async with db.scoped_session() as session`으로 ass객체를 `__call__`인 `()`로 호출해서 session을 생성한다.**
    - **미들웨어 == router가 아니라서 Depends불가지역에서 `async with`로 session을 발급받아 쓴다.**
    ```python
    # TODO: redis cache
    @staticmethod
    async def get_api_key_with_owner(query_params_map):
    
        async with db.scoped_session() as session:
            # print("session", session)
    
            matched_api_key: Optional[ApiKeys] = await ApiKeys.filter_by(
                session=session,
                access_key=query_params_map['key']
            ).first()
            # print("matched_api_key", matched_api_key)
    
            if not matched_api_key:
                raise NoKeyMatchException()
    
            # user객체는, relationship으로 가져온다. lazy인데, 2.0.4버전에서는 refresh로 relationship을 load할 수 있다.
            await session.refresh(matched_api_key, attribute_names=["user"])
            # print("matched_api_key.user", matched_api_key.user)
    
            if not matched_api_key.user:
                raise NotFoundUserException()
    
            return matched_api_key
    ```

    - **추가로 set_session시, 자체세션발급할 때도 따로 발급하는데 `objectmixin객체는 알아서 close/commit`하므로 `db.scoped_session()`
      의 `no future session발급`으로 변경한다.**
    ```python
    async def set_session(self, session: AsyncSession = None):
    
       # 외부 X and 자신O(필드 + session) -> 아예 실행도 X
        self_session = getattr(self, '_session', None)
        if not session and self_session:  # and not self_session.get_transaction().is_active():
            return
        # 외부 O or 자신X
        if session:
            # (외부 O) & (자신O or 자신X 노상관) -> 무조건 덮어쓰기
            self._session, self._served = session, True
        else:
            # (외부 X) and 자신X -> 새 발급
            # self._session = await db.session().__anext__()
            self._session = db.scoped_session()
    
            self._served = False
    ```

4. **여러 AsyncScopedSession객체는 registry에 계속 등록되기 때문에. 일단 shut_down에서 `.remove()`로 삭제해준다.**
    ```python
    @app.on_event("shutdown")
    async def shut_down():
        await self._scoped_session.remove() # async_scoped_session은 remove까지 꼭 해줘야한다.
        await self._async_engine.dispose()
        logging.info("DB disconnected.")
    ```

5. SQlalchemy class의 객체 역시 `singleton`을 적용해준다.
    ```pyhton
    from app.utils.singleton import SingletonMetaClass
    
    
    class SQLAlchemy(metaclass=SingletonMetaClass):
        #...
    ```
   

#### mixin에서 db.session발급기 import 의존성 -> Base에 주입하도록 바꾸기
1. 기존 sqlalchemy의 cls.query가 가능하게 했던 코드
    ```python
    session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
    Base = declarative_base()
    Base.query = session.query_property()
    ```

2. 이것을 참고해서 **async_scoped_session객체를 `Base.scoped_session=`으로 집어넣어서, mixin 내부 set_session-자체session발급시 사용가능하게 한다.**
    ```python
    class SQLAlchemy(metaclass=SingletonMetaClass):
        #...
        def init_app(self, app: FastAPI, **kwargs):
            #...
            self._scoped_session: async_scoped_session[AsyncSession] | None = \
                async_scoped_session(
                    async_sessionmaker(
                        bind=self._engine, autocommit=False, autoflush=False, future=True,
                        expire_on_commit=False  # refresh로 대체할려 했으나, 매번 select가 되어 필요시마다 하기로.
                    ),
                    scopefunc=current_task,
                )
            
            Base.scoped_session = self._scoped_session
    ```

3. **이제 `BaseModel(Base)`에는 `이미 self.scoped_session이 사용 가능한 상태`이므로, mixin에서도 사용한다.**
    - objectmixin에서 외부session(X)로, 자체 session을 발급할 때, `self.scoped_sesion`을 async with로 발급한다.
    ```python
    class ObjectMixin(BaseMixin):
        #....
        async def set_session(self, session: AsyncSession = None):
            # 외부 O or 자신X
            if session:
                self._session, self._served = session, True
            else:
                if not getattr(self, "scoped_session"):
                    raise Exception(f'세션 주입이 안되었습니다. >> Base.scoped_session = db.scoped_session')
    
                # (외부 X) and 자신X -> 새 발급
                # self._session = await db.session().__anext__()
                async with self.scoped_session() as self_session:
                    self._session = self_session
    
                self._served = False
    ```
    - 어차피 tr을 생성할 것이 아니므로 그냥 발급해도 된다.
    ```python
    # async with self.scoped_session() as self_session:
    #     self._session = self_session
    self._session = self.scoped_session()
    ```
4. **async_scoped_session은 `thread별 안전성`을 지켜주고, 새로 session을 발급하므로 tr decorator를 crud메서드에 안들아줘도 된다.**
    ```python
    # @with_transaction
    async def save(self, auto_commit=False, refresh=False):
        #...
    
    # @with_transaction
    async def remove(self, auto_commit=False):
        #...
    ```
   
5. 사용법에 따라 사용한다.
    ```python
    # router Depends() 주입용
    @property
    def session(self):
        return self.get_db
    
    # non router -> async with 발급 용
    @property
    def scoped_session(self):
        return self._scoped_session
    ```
   

### refresh 도입
1. **`expire_on_commit=False`를 통해, commit된 객체도 Pydantic Resonse Model에서 사용가능해졌지만**
    - **`commit <-> 응답사이에 변할 수 있는 객체`의 경우, `refresh해서 db와 일치(select쿼리)를 따로 정의`해준다.**
    ```python
    self._scoped_session: async_scoped_session[AsyncSession] | None =
        async_scoped_session(
            async_sessionmaker(
                bind=self._async_engine, autocommit=False, autoflush=False, future=True,
                expire_on_commit=False  # refresh로 대체할려 했으나, 매번 select가 되어 필요시마다 하기로.
            ),
            scopefunc=current_task,
        )
    ```
   

2. `refresh=`옵션은 save(CU)/delete(D) 실행메서드에 옵션을 추가시킨다. **이 때, CU만 추가시킨다. D에서는 이미 삭제된 객체므로 따로 쓸 필요 없다.**
    - **refresh를 호출했는데, `자체 세션`이면, commit 후에도 `해당 객체가 해당session에 유지`되기 위해, session삭제부분을 if/else로 나눠준다.**
```python
async def save(self, auto_commit=False, refresh=False):

    try:

        if self.id is not None and self.served:
            await self.session.merge(self)
        else:
            self.session.add(self)
            await self.session.flush()
        if auto_commit:
            await self.session.commit()
            # 자체세션이라면, commit하고 refresh True인 경우 계속 쓸 수 있게
            if refresh:
                await self.session.refresh(self)
            # refresh면, 해당객체를 쓴다는 말인데, 외부 공용세션 세션삭제x/served삭제x -> 노상관
            # 자체세션이 -> 계속 쓸것이므로, sesion삭제 안하도록 if/else를 나눈다.
            else:
                self._session = None
                self._served = False

        return self
```
3. save()를 호출하는 메서드 create/update에, refresh=옵션을 추가한다.
    ```python
    @class_or_instance_method
    async def create(cls, session: AsyncSession = None, auto_commit=False, refresh=False, **kwargs):
        obj = await cls.create_obj(session=session)
        if kwargs:
            obj.fill(**kwargs)
    
        return await obj.save(auto_commit=auto_commit, refresh=refresh)
    
    
    @update.instancemethod
    async def update(self, session: AsyncSession = None, auto_commit: bool = False, refresh=False, **kwargs):
        await self.set_session(session=session)
    
        is_filled = self.fill(**kwargs)
    
        if not is_filled:
            return None
    
        return await self.save(auto_commit=auto_commit, refresh=refresh)
    ```
   
4. 생성된 객체가 **외부 수정을 거칠 가능성이 있다면, refresh되게 해서 내보낸다.**
```python
@router.get("/", response_model=UserMe)
async def index(session: AsyncSession = Depends(db.session)):
    user = await Users.create(email='asdf', auto_commit=True, refresh=True)
    return user
```
### 도커 명령어

1. (`패키지 설치`시) `pip freeze` 후 `api 재실행`

```shell
pip freeze > .\requirements.txt

docker-compose build --no-cache api; docker-compose up -d api;
```

2. (init.sql 재작성시) `data폴더 삭제` 후, `mysql 재실행`

```shell
docker-compose build --no-cache mysql; docker-compose up -d mysql;
```

```powershell
docker --version
docker-compose --version

docker ps
docker ps -a 

docker kill [전체이름]
docker-compose build --no-cache
docker-compose up -d 
docker-compose up -d [서비스이름]
docker-compose kill [서비스이름]

docker-compose build --no-cache [서비스명]; docker-compose up -d [서비스명];

```

- 참고
    - 이동: git clone 프로젝트 커밋id 복사 -> `git reset --hard [커밋id]`
    - 복구: `git reflog` -> 돌리고 싶은 HEAD@{ n } 복사 -> `git reset --hard [HEAD복사부분]`