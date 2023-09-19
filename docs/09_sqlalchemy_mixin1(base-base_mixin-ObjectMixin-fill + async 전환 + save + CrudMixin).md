### ㅇ
#### conn.py에서 세션 주입용 메서드 get_db에서  rollback + raise 추가
```python
class SQLAlchemy:
    #...
    def get_db(self):
        # 세션 객체를 만들고, yield한 뒤, 돌아와서는 close까지 되도록
        # -> 실패시 rollback 후 + raise e 로 미들웨어에서 잡도록
        db_session = None
        try:
            db_session = self._Session()
            yield db_session
        except Exception as e:
            db_session.rollback()
            raise e
        finally:
            db_session.close()
```
 
### async mixin 개발
1. async를 적용하려면, sqlalchemy `1.4` 버전 이상, python `3.6`이상을 권장한다
    - https://github.com/alteralt/async-sqlalchemy-mixins/commit/03e5a25766c7f37cfffbe7febddc58d604d6ed9a

#### User.session, User.query를 쓰게 해주는 utils > class_property.py
- 클래스 변수를, 
```python
# noinspection PyPep8Naming
class class_property(object):
    """
    @property for @classmethod
    taken from http://stackoverflow.com/a/13624858
    """

    def __init__(self, fget):
        self.fget = fget

    def __get__(self, owner_self, owner_cls):
        return self.fget(owner_cls)

```
#### mixins > object_mixin.py
##### 기존 create 부터 변환하기
1. 인스터싱을 BaseModel의 get / create에 했떤 것들을 모두 mixin으로 옮길 것인데, **가장 먼저 `ObjectMixin`을 만들고, 실제 작동은 안하지만 명시적으로 생성자를 만든다.**
    - **기존 baseModel의 create, get에서는 필요없었지만, `filter, order`부터는 `내부 query 변수`를 사용해야한다.**
    - **session은 주입식으로 쓸 것이다. Model cls에 scoped session을 박아놓을 수 없기 때문에, `내부 session변수`도 필요하다.**
    - 단순 1개 조회 등은 외부주입을 받을 필요가 없으므로, `내부 served(공용세션 사용여부) 변수`도 필요하다.?!
    - **`ObjectMixin`을 만들고, 호출되진 않지만, `명시용 생성자를 정의`해놓고 -> `관련메서드`들도 정의한다.**
    - Mixin에 쓸 query, session, served는 
       - **`칼럼외 추가필드(_query, _session, served)`를 만들었으므로, 생성자를 재정의해주되 `args, kwargs`를 인자로 추가해 Base의 생성자도 같이 필수로 호출해줘야한다.**
```python
class ObjectMixin:

    def __init__(self, *args, **kwargs):
        # 필드 추가를 위해, 생성자 재정의 했으면, 기존 부모의 생성자를 ids_, kwargs로 커버
        super().__init__(*args, **kwargs)
        self._query = None
        self._session = None
        self._served = None  # 공용 session 받은 여부
```

2. basemodel의 create 함수에서, 모델객체를 session에 add하는 과정에서 `obj = cls()` 내부 인스터싱 작업 대신, 각 model 내부에서 `cls.create_obj()`를 호출할 수 있도록 classmethod로 정의해준다.
    - 기존
        ```python
        @classmethod
        def create(cls, session: Session, auto_commit=False, **kwargs):
            obj = cls()
        ```
   - 변경
       ```python
           @classmethod
           async def create_test(cls, session: Session = None, auto_commit=False, **kwargs):
               obj = cls.create_obj(session=session)
       ```
  
3. 위와 같이 만드려면, **`Mixin class에서, @classmethod`로 정의해야, baseModel 등에서 `cls.메서드()`가 호출 된다.**
    - **이 때, `session`과 기본쿼리`select(해당cls)`도 같이 `self._session`, `self._query`에 초기화해주기 위해, 아래과 같이 작성한다.**
```python
class ObjectMixin:
    #...
    @classmethod
    def _create_obj(cls, session: Session = None, query=None):
        obj = cls()
        obj._set_session(session=session)
        obj._set_query(query=query)

        return obj
```
4. **둘다 obj mixin내에서, self method로 정의하여 객체상태에서 호출할 수 있게 하며, 각각의 값을 외부 _create_obj메서드에서 `obj.session, obj.query`로 뽑아볼 수 있게 @property로 정의해준다.**
    ```python
    class ObjectMixin:
        def _set_session(self, session: Session = None):
            """
            공용 session이 따로 안들어오면, 단순조회용으로 db에서 새발급
            """
            if session:
                self._session, self._served = session, True
            else:
                local_session = next(db.session())
                self._session, self._served = local_session, False
    
    
        @property
        def session(self):
            """
             외부 CRUD 메서드 내부
             obj = cls._create_obj() ->  obj.session.add()
            """
            if self._session is not None:
                return self._session
    
            raise Exception("Can get session.")
    
        def _set_query(self, query=None):
            """
            query를 따로 안넣으면, select( Users by self.__class__ )
            """
            if query:
                self._query = query
            else:
                self._query = select(self.__class__)
    
        @property
        def query(self):
            """
             외부 CRUD 메서드 내부
             obj = cls._create_obj() ->  obj.query == select(Users)    에 .xxxx
            """
            return self._query
    ```

5. test는 async로 `BaseModel`에서 `ObjectMixin`을 상속하여 달고, `asyn create_test`를 만든 뒤, /test 에서 `await User.create_test()`로 찍어본다.
```python
class BaseModel(Base, ObjectMixin):
    #...
    @classmethod
    async def create_test(cls, session: Session = None, auto_commit=False, **kwargs):
        obj = cls.create_obj(session=session)
        print(obj.__dict__)
        print(obj.session) # property
        print(obj.query)
```
```python
@router.get("/test")
async def test(request: Request):
    try:
        print(await Users.create_test())
    except Exception as e:
        request.state.inspect = frame()
        raise e

    current_time = datetime.utcnow()
    return Response(f"Notification API (UTC: {current_time.strftime('%Y.%m.%d %H:%M:%S')})")

```
```python
# {'_sa_instance_state': <sqlalchemy.orm.state.InstanceState object at 0x7fa2b2609ac0>, '_session': <sqlalchemy.orm.session.Session object at 0x7fa2b25b6f40>, '_served': False, '_query': <sqlalchemy.sql.selectable.Select object at 0x7fa2b25c1820>}

# <sqlalchemy.orm.session.Session object at 0x7fa2b25b6f40>

# SELECT users.status, users.email, users.pw, users.name, users.phone_number, users.profile_img, users.sns_type, users.marketing_agree, users.id, users.created_at, users.updated_at 
# FROM users
```

6. **이제 object에 kwargs로 들어올 요소들을 순회하며 채우는 `fill`메서드를 구현해준다.**
    - **칼럼을 순회하기 위해 `all_columns` self메서드를 구현했지만, sqlalchemy 적으로 접근하기 위해**
    - `Base`를 상속한 자식class(BaseModel)에서  + `cls.columns`를 호출하기 위해 `@class_property`를 이용하여, **테이블 칼럼객체들을 추출하는 `column_names`를 정의한다**
```python
class BaseModel(Base, ObjectMixin):
    #...
    @class_property
    def column_names(cls):
        return cls.__table__.columns.keys()
```
  - **현재 테이블의 칼럼명 외에 `관계칼럼명` + `hybrid_property명`을 추출하는 classproperty도, `fill가능하므로 정의`해놔야한다.**
```python
class BaseModel(Base, ObjectMixin):
    #...
    @class_property
    def relation_names(cls):
        """
        Users.relation_names
        ['role', 'inviters', 'invitees', 'employee']
        """
        mapper = cls.__mapper__
        # mapper.relationships.items() # ('role', <RelationshipProperty at 0x2c0c8947ec8; role>), ('inviters', <RelationshipProperty at 0x2c0c8947f48; inviters>),
        return [prop.key for prop in mapper.iterate_properties
                if isinstance(prop, RelationshipProperty)]
    
    @class_property
    def hybrid_property_names(cls):
        """
        Users.hybrid_property_names
        ['is_staff', 'is_chiefstaff', 'is_executive', 'is_administrator', 'is_employee_active', 'has_employee_history']
        """
        mapper = cls.__mapper__
        props = mapper.all_orm_descriptors # [ hybrid_property  +  InstrumentedAttribute (ColumnProperty + RelationshipProperty) ]
        return [prop.__name__ for prop in props
                if isinstance(prop, hybrid_property)]
```

7. 각각의 칼럼 + relation프로퍼티 + hybrid프로퍼티 등 read가능한 것들을 가져온다고 하더라도, **`칼럼 + relation` 중에 settable 한 것만 또 따로 추출해야한다.**
    - cls.__table__.columns의 dict를 .keys()로 keyword만 바로 추출하지말고, pk여부 확인 및 created_at 칼럼을 제외시킨다.
    - relation_names에서는 .property의 .viewonly 인것을 피한다.
    - **통합해서, `settable_attributes`로 정의한다.**
```python
    @class_property
    def settable_column_names(cls):
        """"
        pk여부 False + create_at을 제외한 칼럼들의 name
        """
        return [column.name for column in cls.__table__.columns if
                column.primary_key is False and column.name != "created_at"]

    @class_property
    def settable_relation_names(cls):
        """
        Users.settable_relation_names
        ['role', 'inviters', 'invitees', 'employee']
        """
        return [prop for prop in cls.relation_names if getattr(cls, prop).property.viewonly is False]

    @class_property
    def settable_attributes(cls):
        return cls.settable_column_names + cls.settable_relation_names + cls.hybrid_property_names

```
- test하면 아래와 같이 출력된다.

```python
@classmethod
async def create_test(cls, session: Session = None, auto_commit=False, **kwargs):
    obj = cls.create_obj(session=session)
    print(obj.__dict__)
    # print(obj.session)  # property
    # print(obj.query)
    print(obj.settable_attributes)
    # ['status', 'email', 'pw', 'name', 'phone_number', 'profile_img', 'sns_type', 'marketing_agree', 'updated_at']

    return
```
#### Base를 상속한 것만 취급할 수 있으므로 Mixin에서 못씀 -> BaseMixin(Base)를 생성하고, BaseModel이 상속하도록 변경 -> ObjectMixin(BaseMixin)으로 사용
1. mixins > base_mixin.py 생성 후, `Base 상속`
```python
from app.database.conn import Base

class BaseMixin(Base):
    __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.

    @class_property
    def column_names(cls):
        return cls.__table__.columns.keys()
```
2. object_mixin.py는 BaseMixin을 상속한 뒤, 정의한 요소들 사용
```python
class ObjectMixin(BaseMixin):
    __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.
```
3. **base.py의 BaseModel은 `Base을 상속한 BaseMixin or ObjectMixin을 상속`**
```python
class BaseModel(ObjectMixin):
    __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.

```

#### fill 메서드 구현
1. create나 update의 kwargs가 넘어올 때, BaseMixin에 구현한 `settable_attributes`를 이용하여 fill메서드 구현
    - **그 전에, settable_attr이 아니라도, `property로서 칼럼객체.hasattr( , 'setter' or 'expression')이라면 fill가능한 @property로서 추가한다.**
    ```python
    class BaseMixin(Base):
        __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.
    
        def is_setter_or_expression(self, column_name):
            return hasattr(getattr(self.__class__, column_name), 'setter') or \
                hasattr(getattr(self.__class__, column_name), 'expression')
    ```
2. fill을 채우기 전에 4단계의 검증을 거친다.
    - form데이터에 넘어오는 field들을 자동 제외로서 continue한다 `'csrf_token', 'submit`
    - settable_attribue에 속하는 것 or  속하지 않더라도 setter/expression을 hasattr()인 property라면 가능한데, `not (A or B)`로 어느것도 속하지 않는다면, invalid column이다.
    - 이미 같은 값이라면 continue한다.
    - 관계칼럼이면서 list형태면, list칼럼을 얻어서 append한다. 
    - 그것이 아니라면 setattr()한다.

    ```python
    class ObjectMixin(BaseMixin):
        __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.
        def fill(self, **kwargs):
            """
            create 내부 obj객체 or 외부 model객체.fill() 용 self메서드
            """
            for column_name, new_value in kwargs.items():
                # 1) form.data(dict) 에 더불어 오는 keyword => 에러X 무시하고 넘어가기
                if column_name in ['csrf_token', 'submit'] or column_name.startswith('hidden_'):
                    continue
                # 2) settable_attr이 아니라도 -> (@property일 수 있다)
                #    setter/expression을 hasattr()하고 있는 @property는, fill 가능이다.
                #    (settable_attr에 포함되면 바로 통과)
                if not (column_name in self.settable_attributes or self.is_setter_or_expression(column_name)):
                    raise KeyError(f'Invalid column name: {column_name}')
    
                # 3) (settable_attr or property지만) 2개를 포괄하는 column_names 중에
                #    -> 이미 현재 값과 동일한 값이면, continue로 넘어간다.
                if column_name in self.column_names and getattr(self, column_name) == new_value:
                    continue
    
                # 4) 이제 self의 column에 setattr() 해줄 건데, <관계칼럼이면서 & uselist=True>는 append를 해준다.
                if column_name in self.relation_names and isinstance(getattr(self, column_name), InstrumentedList) \
                        and not isinstance(new_value, list):
                    getattr(self, column_name).append(new_value)
                else:
                    setattr(self, column_name, new_value)
    
            return self
    ```

3. test메서드에 **if kwargs로 들어온다면, obj.fill(**kwargs)로 호출**하고 잘 들어가는지 확인한다.
    ```python
    @classmethod
    async def create_test(cls, session: Session = None, auto_commit=False, **kwargs):
        obj = cls.create_obj(session=session)
        if kwargs:
            obj.fill(**kwargs)
    
        print(obj.name)
    
        return
    ```
   
### save 구현(flush/commit 등) 전 async(비동기)로 전환하기
- 참고 유튜브: https://www.youtube.com/watch?v=cH0immwfykI
```python
results = await db.execute(select(User)) users = results.scalars().all() 
# 더 보기 좋게 만드는 대신 이 작업을 수행할 수도 있습니다. 
users = await db.scalars(select(User))  users = users.all()
```
- 참고 gist: https://gist.github.com/dunossauro/075cf06bc9dc7e16ddfa8717d6ee9c41


1. pymsql 대신 `aiomysql` 패키지 설치 (sqlite: , postgre: asyncpg)
    ```python
    pip install aiomysql
   
    pip freeze > .\requirements.txt
    docker-compose build --no-cache api; docker-compose up -d api;
    ```
    - sqlite의 경우, `engine생성시 connect_args={"check_same_thread" False}` 추가


2. config.py 에서 db url 변경 ( +pymysql -> +aiomysql )
    ```python
    @dataclass
    class LocalConfig(Config):
        PROJ_RELOAD: bool = True
        # DB_URL: str = "mysql+pymysql://travis:travis@mysql:3306/notification_api?charset=utf8mb4"
        # async 적용
        DB_URL: str = "mysql+aiomysql://travis:travis@mysql:3306/notification_api?charset=utf8mb4"
    ```

3. database > conn.py 에서 create_engine 및 sessionmaker를 asyncio 버전의 모듈로 변경
    ```python
    # from sqlalchemy import create_engine
    # from sqlalchemy.orm import sessionmaker
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    #...
    class SQLAlchemy:
        #...
        def init_app(self, app: FastAPI, **kwargs):
            # self._engine = create_engine(database_url, echo=echo, pool_recycle=pool_recycle, pool_pre_ping=True, )
            # self._Session = sessionmaker(bind=self._engine, autocommit=False, autoflush=False,)
            self._engine = create_async_engine(database_url, echo=echo, pool_recycle=pool_recycle,
                                               pool_pre_ping=True, )
            # expire_on_commit=False가 없으면, commit 이후, Pydantic Schema에 넘길 때 에러난다.
            self._Session = async_sessionmaker(bind=self._engine, autocommit=False, autoflush=False,
                                               expire_on_commit=False, # 필수 for schema
                                               )
            
    ```
    - 예를 들어, 세션 내의 객체들을 계속해서 사용하고자 할 때 유용합니다. expire_on_commit를 False로 설정하면 커밋 이후에도 동일한 세션을 사용하여 같은 객체들을 쿼리하거나 수정할 수 있습니다. 그러나 주의해야 할 점은 이 경우에는 세션에 로드된 객체들이 항상 최신 데이터를 반영하지 않으므로 데이터베이스의 변경 사항을 수동으로 다시로드해야 할 수 있습니다.
    - 반대로, expire_on_commit를 True로 설정하면 커밋 후에 세션에 로드된 객체들이 자동으로 만료되어 다음 데이터베이스 조회 시에 최신 데이터를 다시 로드하게 됩니다. 이는 항상 최신 데이터를 보장하지만, 동일한 세션을 재사용하려면 이전 객체들을 다시 로드해야 할 수 있습니다.
    - **flush 이후에도 사용할 수 있게 하는 듯?!**


4. `Base.metadtaa.create_all(engine)`에서 **현재 비동기 엔진이 아닌 `동기 엔진`을 추출해서 bind해줘야한다.**
   - 원래 위치를 주석처리하고
   - **주입용 get_db 메서드를 async로 변경한 뒤**
   - engine을 이용해서 engine.begin()으로 connection -> 연결한 상태로, 동기로 실행하는 .run_sync()안에 Base.metadata.create_all을 입력해준다.
    ```python
    # def get_db(self):
    async def get_db(self):
    
        # 테이블 생성 추가
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    ```
    - 추가로 **rollback, close시 await를 걸어준다.**

```python
async def get_db(self):

    # 테이블 생성 추가
    async with self.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 초기화 X -> Session cls없을 땐 에러
    if self._Session is None:
        raise Exception("must be called 'init_app'")
    db_session = None
    try:
        db_session = self._Session()
        yield db_session
    except Exception as e:
        # db_session.rollback()
        await db_session.rollback()
        raise e
    finally:
        # db_session.close()
        await db_session.close()
```

5. get_db -> 주입시에는 db.session by property의 힌트를 AsyncSession으로 바꿔준다.
```python
# async def register(sns_type: SnsType, user_register_info: UserRegister, session: Session = Depends(db.session)):
@router.post("/register/{sns_type}", status_code=201, response_model=Token)
async def register(sns_type: SnsType, user_register_info: UserRegister, session: AsyncSession = Depends(db.session)):
    #...
```

- **crud의 인자로 들어갔떤 typehint도 Session -> AsyncSession으로 변경한다.**
```python
@classmethod
    # async def get_by_email(cls, session: Session, email: str):
    async def get_by_email(cls, session: AsyncSession, email: str):
```
6. **app의 startup + engine connect()는 `동기로 그대로 둔다`(비동기로 바꾸면 에러뜸)**
    - **하지만 engine.dispose()가 있는 shutdown은 비동기로 바꾼다**
    - **또한 `Session cls의  .close_all()이 사라져서, 삭제`한다.**
    ```python
    def init_app_event(self, app):
        @app.on_event("startup")
        def start_up():
            self._async_engine.connect()
            logging.info("DB connected.")
    
        @app.on_event("shutdown")
        async def shut_down():
            # self._Session.close()
            await self._async_engine.dispose()
            logging.info("DB disconnected.")
    ```
   
7. 조회메서드 수정시, async query 수행은 **2가지 타입으로 수정할 수 있다.**
    - await session.execute( stmt ) -> result.scalar() or result.scalars().first() | .all()
    ```python
    @classmethod
    # async def get_by_email(cls, session: Session, email: str):
    async def get_by_email(cls, session: AsyncSession, email: str):
        # result = session.scalars(
        #     select(cls).where(cls.email == email)
        # ).first()
    
        # result = await session.execute(
        #     select(cls).where(cls.email == email)
        # )
        # result.scalars().first()
    
        result = await session.scalars(
            select(cls).where(cls.email == email)
        )
        return result.first()
    ```
   
8. **router에 Depends로 주입하는 것은 db.session == db.get_db 가 잘 주입되지만, `단순조회 등 내부 session 발급`시 `yield AsyncSession`는 단순 generator가 아니라 에러가 난다.**
    - `'async_generator' object is not an iterator`로 비동기 generator는 다르게 처리해야한다.
    - ObjectMixin의 _set_session에서 내부세션 발급시 코드를 `단순 generator ->next()`를 **`비동기 generator -> await .__anext()`로 변경한다**
    - await가 붙으니 async 메서드로 변경하고 -> 호출하는 곳에서 await로 변경한다.
    ```python
    class ObjectMixin(BaseMixin):
        #... 
        
        # def _set_session(self, session: Session = None):
        async def _set_session(self, session: Session = None):
            """
            공용 session이 따로 안들어오면, 단순조회용으로 db에서 새발급
            """
            if session:
                self._session, self._served = session, True
            else:
                # session = next(db.session())
                # 비동기 AsyncSession는 yield하더라도, # 'async_generator' object is not an iterator 에러가 뜬다.
                # => 제네레이터가 아니라 비동기 제네레이터로서, wait + 제네레이터.__anext__()를 호출한다.
                session = await db.session().__anext__()
    
                self._session, self._served = session, False
    ```
    ```python
    class ObjectMixin(BaseMixin):
        #...
        @classmethod
        async def _create_obj(cls, session: Session = None, query=None):
            obj = cls()
            # obj._set_session(session=session) # 비동기 session을 받아오는 비동기 호출 메서드로 변경
            await obj._set_session(session=session) # 비동기 session을 받아오는 비동기 호출 메서드로 변경
            obj._set_query(query=query)
    
            return obj
    ```

9. **비동기 Session은 변화(commit, rollback 등)이 없는데 제네레이터 돌아온 뒤 session.close()를 하면 워닝이 난다.**
    - 비동기session.is_active로 커밋or롤백의 상황에서만 close를 호출하도록 변경한다.
```python
async def get_db(self):
    #...
    db_session = self._Session()
    try:
        yield db_session
    except Exception as e:
        await db_session.rollback()
        raise e
    finally:
        # db_session.close()

        #  sqlalchemy.exc.IllegalStateChangeError: Method 'close()' can't be called here; method '_connection_for_bind()' is already in progress and this would cause an unexpected state change to <SessionTransactionState.CLOSED: 5>
        # 비동기session은 -> 이미 커밋 또는 롤백이 발생했을 때만 세션을 닫음
        if db_session.is_active:
            await db_session.close()
```

### 이제 obj를 내부 session으로 add + flush하는데 await로 호출하는 save 를 구현한다.
1. async def save()메서드를 구현한다.
    - **id가 이미 부여된 객체 -> `타 세션` 조회 or `sessoin끊어진 객체` -> `add/flush` 대신 `merge`를 해주고, id가 없는 쌩 객체면, `add/flush` 해주되**
    - commit한다면, **커밋 직후, db변화상황 받는 refrsh( 객체 ) 이후 반환**하도록 작성한다.
    - `DB로 보내는 메서드들(add제외 모두)`은 모두 `await`로 호출한다.
    - **`commit`으로 close되면, `self._session/self._served를 초기화 `해준다.**
    - **commit이후 refresh하려 했지만, `refresh는 session에 add를 포함하고 있어서 다음호출시 문제가 되서 삭제`한다.**
    - **추가) update메서드 처럼 self용 메서드는 `조회후 id`를 가진 상태이지만, `set_session에 의해 session을 가진 상태`이다.**
        - **`merge`는 `id를 가진 조회된 상태(자체sess가능성)` + `served된 외부공용session일때만 적용`하도록 한다.**
```python
class ObjectMixin(BaseMixin):
    __abstract__ = True

    async def save(self, auto_commit=False):
        """
        obj.fill() -> obj.save() or user.fill() -> user.save()
        1) 공용세션(served) -> merge (add + flush + refresh / update + flush + refresh)
        2) 자체세션 -> add + flush + refresh 까지
        if commit 여부에 따라, commit
        """
        if self.id is not None and self.served:
            await self.session.merge(self)
        else:
            self.session.add(self)
            await self.session.flush()

        if auto_commit:
            await self.session.commit()
            #await self.session.refresh(self)
            self._session = None
            self._served = False

        return self
```

2. 테스트 create_test메서드에 fill 이후, `await obj.save()`를 호출해본다.
```python
class BaseModel(ObjectMixin):
    #...
    @classmethod
    async def create_test(cls, session: Session = None, auto_commit=False, **kwargs):
        obj = await cls._create_obj(session=session)
        if kwargs:
            obj.fill(**kwargs)

        return await obj.save(auto_commit=auto_commit)
```
```python
@router.get("/test")
async def test(request: Request):
    try:
        user = await Users.create_test(email="abc@gmail.com", name='조재경', auto_commit=True)
    except Exception as e:
        request.state.inspect = frame()
        raise e

    current_time = datetime.utcnow()
    return Response(f"Notification API (UTC: {current_time.strftime('%Y.%m.%d %H:%M:%S')})")

```

### CRUDMixin.py를 생성 후, create_obj -> fill -> save 로 create를 완성한다.
1. CRUDMixin 을 생성하여, ObjectMixin을 상속하고, BaseModel은 이제 CRUDMixin을 상속하도록 변경한다.
    ```python
    from app.models.mixins.object_mixin import ObjectMixin
    
    
    class CRUDMixin(ObjectMixin):
        __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.
    
        ...
    ```
    ```python
    from app.models.mixins.crud_mixin import CRUDMixin
    
    class BaseModel(CRUDMixin):
        __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.
        #...
    
    ```
   
2. BaseModel에 정의했던 create_test -> create메서드로 가져온다.
```python
class CRUDMixin(ObjectMixin):
    __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.

    @classmethod
    async def create(cls, session: AsyncSession = None, auto_commit=False, **kwargs):
        obj = await cls._create_obj(session=session)
        if kwargs:
            obj.fill(**kwargs)

        return await obj.save(auto_commit=auto_commit)
```
3. 기존에 있던 BaseModel의 create를 삭제한다.

4. register에서 사용되는 User.create()가 잘작동하는지 확인한다.
    - **이 때 test에서 먼저, User.create() -> `user객체(id부여된 객체)` -> 필드변경 후 .save() -> `내부 merge로 변경`이 잘되는지 확인한다.**
    ```python
    @router.get("/test")
    async def test(request: Request):
        try:
            user = await Users.create(email="abc@gmail.com", name='조재경', auto_commit=True)
            user.name = '2'
            await user.save(auto_commit=True)
        except Exception as e:
            request.state.inspect = frame()
            raise e
    
        current_time = datetime.utcnow()
        return Response(f"Notification API (UTC: {current_time.strftime('%Y.%m.%d %H:%M:%S')})")
    
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