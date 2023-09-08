### ReprMixin
1. mixin에 `repr_mixin.py`를 생성하고 아래와 같이 정의함
    ```python
    from sqlalchemy import inspect
    
    
    class ReprMixin:
        __abstract__ = True
    
        __repr_attrs__ = []
        __repr_max_length__ = 10
    
        def __repr__(self):
            info: str = f"<{self.__class__.__name__}" \
                        f"#{self._id_str}"
            info += f" {self._repr_attrs_str}" if self.__repr_attrs__ else ""
            info += ">"
            return info
    
        # id -> string
        @property
        def _id_str(self):
            _ids = inspect(self).identity  # 생성객체라면 id없어서 None 반환 / 있으면 (1, ) tuple
            if not _ids:
                return 'None'
            return '-'.join([str(_id) for _id in _ids]) if len(_ids) > 1 else str(_ids[0])
    
        # id 외 __repr_attrs__에 표시한 칼럼 -> string
        @property
        def _repr_attrs_str(self):
            max_length = self.__repr_max_length__
    
            values = []
            # 1) 표시할게 1개라면,
            single = len(self.__repr_attrs__) == 1
            for key in self.__repr_attrs__:
                if not hasattr(self, key):
                    raise KeyError(f"Invalid attribute '{key}' in __repr__attrs__ of {self.__class__}")
                value = getattr(self, key)
    
                value = str(value)
                if len(value) > max_length:
                    value = value[:max_length] + '...'
    
                values.append(f"{value!r}" if single else f"{key}:{value}")
    
            return ' '.join(values)
    ```
   
2. BaseModel에서 `최상위 CRUDMixin`에 **추가로 ReprMixin을 상속한다**
    ```python
    class BaseModel(CRUDMixin, ReprMixin):
        __abstract__ = True 
    ```
   
### CUD 1session 동시 DB connection을 막기 위한 @with_transaction 데코레이터 만들기
1. **문제 상황 -> `같은 DB-row에 동시 CUD 접근시, commit이 없어 1번째 트랜잭션 아직 안풀린 상태에서 -> 두번째 트랜잭션을 생성하여 -> lock 충돌 (잠금해제 실패)` -> time out이 난다**
    - **.create()메서드를 auto_commit=True없이 호출하면, `session이 완전히 Create를 완전히 마치기 전에, create전 SELECT를 위한 트랜잭션으로 잠금상태`인데**
    - **`비동기로 같은 row에 Create전 SELECT를 위한 트랜잭션을 또 열다가` -> `이미 다른 `접근하게 될 것이다.**
        - 첫 번째 코드가 Users.create() 메서드를 호출하면, 데이터베이스는 INSERT 명령을 실행하기 위해 트랜잭션을 시작합니다. 트랜잭션은 데이터베이스 테이블에 SELECT 명령을 실행하여 레코드가 이미 존재하는지 확인합니다. 레코드가 존재하면, 트랜잭션은 중단됩니다.
        - 두 번째 코드가 Users.create() 메서드를 호출하면, 데이터베이스는 INSERT 명령을 실행하기 위해 트랜잭션을 시작합니다. 트랜잭션은 데이터베이스 테이블에 SELECT 명령을 실행하여 레코드가 이미 존재하는지 확인합니다. 레코드가 존재하면, 트랜잭션은 Lock wait timeout exceeded; try restarting transaction 오류를 발생시킵니다.
        - 이 오류는 트랜잭션이 SELECT 명령을 실행하기 위해 레코드를 잠갔지만, `다른 트랜잭션이 레코드를 잠그고 있어서 잠금을 해제할 수 없기 때문 or 타 트랜잭션을 방해`해서 발생한다.
    - **각 create 호출에 대한 `트랜잭션 범위를 제한`해서 `락 충돌 문제를 최소화`해야한다**
    ```python
    user = await Users.create(email='abc@gmail.com')
    user = await Users.create(email='abc@gmail.com')
    ```
    - 트랜잭션 격리 수준 변경: SQLAlchemy에서 사용하는 트랜잭션 격리 수준을 "SERIALIZABLE" 또는 "REPEATABLE READ" 등으로 변경하여 `데이터를 동시에 수정하지 못하도록 제한`할 수 있습니다. 이러한 격리 수준은 MySQL 서버 설정 또는 SQLAlchemy 설정을 통해 변경할 수 있습니다.

2. models > utils > `decoratoros.py`를 만들고, 내부에 **with_transaction 데코레이터를 정의한다.**
    - **이 때, wrapper의 인자로 `self`를 첫번째로 받으면 `해당메서드 호출객체`를 받을 수 있다.**
    - **`async with self.session.begin()`로 `충돌 불가능한 완전히 잠글 수 있는 lock의 트랜잭션`을 만들면,`1row 트랜잭션 충돌`이 안일어난다.**
    - **이 때, transaction.commit()은 무조건 일어나는 게 아니라, `cud메서드의 session에 따라 내부에서 자체 판단`하므로 실패시 rollback만 하게 한다.**
    ```python
    def with_transaction(func):
        """
        C,U,D 메서드 ex> save/delete(?) 에 해당하는 메서드에 적용하는
        각 객체self가 가진 session을 이용해서  transaction으로 완전잠금해놓으면
        await로 같은 session을 await 동시 접근해도, DB에는 하나가 끝나야 나머지가 실행된다.
        
        lock 충돌 방지를 위한 트랜잭션 단위 만들기
    
        """
    
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            async with self.session.begin() as transaction:
                try:
                    result = await func(self, *args, **kwargs)
                    # await transaction.commit()
                    # CUD 메서드 내부에서 session.commit을 자체적으로 판단함.
                    return result
                except Exception as e:
                    await transaction.rollback()
                    raise e
    
        return wrapper
    
    ```
   
3. save메서드에 transaction 데코레이터를 달아준다.
    ```python
    @with_transaction
    async def save(self, auto_commit=False):
        #...
    ```
   

### delete - update와 같이 no query + instance_method
1. classmethod는 막는다. + `최종 self.실행메서드로서`, like update session인자 + set_session을 내부에서 수행한다.
    ```python
    @class_or_instance_method
    async def delete(self, session: AsyncSession = None, auto_commit: bool = False):
        raise NotImplementedError(f'delete 메서드는 객체상태에서만 호출 할 수 있습니다.')
    
    @delete.instancemethod
    async def delete(self, session: AsyncSession = None, auto_commit: bool = False):
        """
        """
        await self.set_session(session=session)
    ```
#### self.remove for delete   
2. **Users.create(), users.update() 내부의 `self.save()`처럼,  `user.delete()`내부에서 `with_transaction`으로 처리될 `self.remove()`메서드를 따로 정의한다**
    ```python
    @with_transaction
    async def remove(self, auto_commit=False):
        """
        obj.delete() -> self.remove()
        if commit 여부에 따라, commit
        """
        try:
            # id를 가진 조회된객체(자체sess)상태에서 + 외부 공용sess 주입 상태일때만 merge
            await self.session.delete(self)
            await self.session.flush()
    
            if auto_commit:
                await self.session.commit()
                self._session = None
                self._served = False
    
            return self
    
        except Exception as e:
            raise RemoveFailException(obj=self, exception=e)
    ```
   
3. 이 때, 필요한 DBException인 RemoveFailException을 정의해준다.
    ```python
    class RemoveFailException(DBException):
    
        def __init__(self, *, obj=None, exception: Exception = None):
            super().__init__(
                code_number=2,
                detail=f"{obj}의 데이터를 삭제하는데 실패했습니다.",
                exception=exception
            )
    
    ```
   
4. index에서 테스트시, **외부session을 이용해서 delete -> remove -> with_transaction 하면, `이미 transaction이 진행중`이라고 뜬다.**
    ```python
    import random
    import string
    random_email = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    random_email += '@gmail.com'
    user = await Users.create(email=random_email)
    
    user = await Users.get(user.id, session=session)
    print(user)
    await user.delete(session=session, auto_commit=True)
    
    #  "detail": "A transaction is already begun on this Session."
    ```
    - **자체 세션으로 조회 -> 해당session으로 delete는 잘됨.**

5. **외부 주입시에는 save/delete에서 transaction을 만들지 않도록, 데코레이터에서 early return하도록 하자.**
    ```python
    def with_transaction(func):
    
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # 외부 session이 주입된 경우, 주입시부터 tr생성하여 시작된 상태
            # -> transaction생성 없이 바로 실행만
            if self.served:
                result = await func(self, *args, **kwargs)
                return result
    
            async with self.session.begin() as transaction:
                try:
                    result = await func(self, *args, **kwargs)
                    # await transaction.commit()
                    # CUD 메서드 내부에서 session.commit을 자체적으로 판단함.
                    return result
                except Exception as e:
                    await transaction.rollback()
                    raise e
        return wrapper
    ``` 
6. index에서 테스트용 user를 만드는 메서드를 임시로 작성해놓는다.
    ```python
    async def create_random_user():
        import random
        import string
        random_email = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        random_email += '@gmail.com'
        user = await Users.create(email=random_email)
        return user
    
    @router.get("/")
    async def index(session: AsyncSession = Depends(db.session)):
        user = await create_random_user()
    
        user = await Users.get(user.id, session=session)
        print(user)
        await user.delete(session=session, auto_commit=True)
        current_time = datetime.utcnow()
        return Response(f"Notification API (UTC: {current_time.strftime('%Y.%m.%d %H:%M:%S')})")
    
    ```
   
7. 주의) filter_by() 중간메서드로 obj생성된 상태에서 바로 delete하면 안됨. **조회 후, session이 닫히거나 외부 같은session인 상태에서 실행해야됨.**
    ```python
    user = await create_random_user()
    # user = await Users.filter_by(id=user.id).delete() # 영속성 에러
    user = await Users.filter_by(id=user.id).first()
    await user.delete(auto_commit=True)
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