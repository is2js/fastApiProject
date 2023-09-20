### 테스트 코드 작성

#### conftest.py

##### config객체

1. config는 이미 import되는 상황에서 TestConfig가 생기도록 설정했다.
    - 직접 config객체를 `config.get('test')`로 생성해서 create_app(config)로 fixture를 집어넣어도 되지만
    - **이미 `pytest 모듈로 실행`시, API_ENV="test"가 들어가서 TestConfig가 생성되도록 결정된다.**
    ```python
    # config.py
    print("- Loaded .env file successfully.") if load_dotenv() \
        else print("- Failed to load .env file.")
    if modules.get("pytest") is not None:
        print("- Run in pytest.")
        environ["API_ENV"] = "test"
        environ["DOCKER_MODE"] = "false"
    ```
    - **이렇게 한 이유는, conftest.py 내부 전역변수로 engine -> create_db해야하는데, config.DB_URL이 필요하기 때문**
2. 이미 DB_URL에는 async로 db_url을 연결하는 engine이 있지만, **`Docker서비스 자동생성되지 않는 test database는 직접 sync_engine으로 생성`해야하기 때문이다.**
    - **async_engine으로 run_sync를 하더라도 `이미 database가 생성되지 않으면 연결에러`난다.**
    - **async용 DB_URL에서 `driver="aiomysql"`를 sync용 driver `pymsql`로 변경한 `SYNC_DB_URL`을 만들고, 동기엔진 create_engine으로 만들
      되 `poolcass=NullPool`로 만들어서, pool연결 재활용 없이 1회성 연결로 만들어 dispose안해도 상관없도록 만든다.**
    ```python
    from app.common.config import config
    
    SYNC_DB_URL: str = config.DB_URL.replace("aiomysql", "pymysql")
    sync_engine = create_engine(SYNC_DB_URL, poolclass=NullPool)
    ```

3. sync_engine도 필요하면 fixture로 만들어서 쓰면 된다.

```python
@pytest.fixture(scope="session")
def engine():
    return sync_engine
```

##### sync engine + sqlalchemy_utils로 으로 Test용 database 직접 생성 -> yield를 통해 table 생성 -> 작업완료후 drop

- **async_engine으로는 database를 생성하지 못한다(run_sync를 하기 전에 .conn() 부터 에러)**
    - 그러므로, sync_engine으로 전역메서드로 처리해야한다.

1. **sqlalchemy-utils는 `database_extsts()`와 `create_database()` 함수를 제공하나 `오로지 sync용`의 버전이다.**
    - 한번만 수행하면 되기 때문에, 전역변수에서 미리 실행시킨다.
    ```python
    from sqlalchemy_utils import database_exists, create_database
    
    SYNC_DB_URL: str = config.DB_URL.replace("aiomysql", "pymysql")
    sync_engine = create_engine(SYNC_DB_URL, poolclass=NullPool, echo=config.DB_ECHO)
    
    # if not database_exists(SYNC_DB_URL):
    #     create_database(SYNC_DB_URL)
    if not database_exists(sync_engine.url):
        create_database(sync_engine.url)
    ```

2. 이제 sync_engine으로 Base객체를 이용해서, table을 생성/drop되도록 한다.
    ```python
    from app.database.conn import Base, db
    
    @pytest.fixture(scope="session")
    def engine():
        return sync_engine
    
    
    @pytest.fixture(autouse=True, scope='session')
    async def prepare_database(engine):
        with engine.connect() as conn:
            Base.metadata.create_all(conn)
            Base.metadata.reflect(conn)
            conn.commit()
            yield
            Base.metadata.drop_all(conn)
    ```

##### 대박) sync_engine + query로 docker없이 생성된 database에 user등록 + 권한부여해주기

- 안타깝게도 user생성 및 권한부여는 sqlalchemy-utils가 제공해주지 않는다.

1. database > `mysql.py`를 생성하고, **classmethod로 정해진 query_set_format_map으로 `engine`**
    ```python
    class MySQL:
        query_set_format_map: dict = {
            "exists_user": "SELECT EXISTS(SELECT 1 FROM mysql.user WHERE user = '{user}');",
            "create_user": "CREATE USER '{user}'@'{host}' IDENTIFIED BY '{password}'",
            "is_user_granted": (
                "SELECT * FROM information_schema.schema_privileges "
                "WHERE table_schema = '{database}' AND grantee = '{user}';"
            ),
            "grant_user": "GRANT {grant} ON {on} TO '{to_user}'@'{user_host}'",
            
            "is_db_exists": "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = '{database}';",
            "create_db": "CREATE DATABASE {database} CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;",
            "drop_db": "DROP DATABASE {database};",
        }
    ```

2. 특정user를 받아서 존재를 확인해야한다. from mysql.user에서 user='{}'로 필터링해서 select 1 한뒤, select exists()로 t/f로 반환받는다.
    - execute는 반복되므로 `engine, scalar여부 + 완성된 query_set`을 바당서 실행하도록 따로 정의한다.
    ```python
    @classmethod
    def exists_user(cls, user: str, engine: Engine) -> bool:
        return bool(
            cls.execute(
                cls.query_set_format_map["exists_user"].format(user=user),
                engine,
                scalar=True,
            )
        )
    ```

3. **sync_engine은 connect()를 with로 만든 뒤, execute()하되, 내부에는 `text()` or `sqlalchemy쿼리`를 넣어주면 되며, **
    - **실행된 cursor는 scalar=True값을 원하면, `.scalar()`를 붙여서 반환하면 된다.**
    - 만약, drop_db 같은 것들은 반환이 없으니, None을 반환하게 한다.
    - 외부에서 호출할 수 있으며, cls.xxx를 이용안하니 execute메서드는 `staticmethod`로 만든다.

    ```python
    @staticmethod
    def execute(query: str, engine: Engine, scalar: bool = False) -> Any | None:
        with engine.connect() as conn:
            cursor = conn.execute(
                text(query + ";" if not query.endswith(";") else query)
            )
            return cursor.scalar() if scalar else None
    ```


4. 추가로 필요한 메서드들을 정의한다.
    ```python
        @classmethod
        def create_user(cls, user: str, password: str, host: str, engine: Engine) -> None:
            return cls.execute(
                cls.query_set_format_map["create_user"].format(
                    user=user, password=password, host=host
                ),
                engine,
            )
    
        @classmethod
        def is_user_granted(cls, user: str, database: str, engine: Engine) -> bool:
            return bool(
                cls.execute(
                    cls.query_set_format_map["is_user_granted"].format(user=user, database=database),
                    engine,
                    scalar=True,
                )
            )
    
        @classmethod
        def grant_user(
                cls,
                grant: str,
                on: str,
                to_user: str,
                user_host: str,
                engine: Engine
        ) -> None:
            return cls.execute(
                cls.query_set_format_map["grant_user"].format(
                    grant=grant, on=on, to_user=to_user, user_host=user_host
                ),
                engine,
            )
        
        
        @classmethod
        def drop_db(cls, database: str, engine: Engine) -> None:
            return cls.execute(
                cls.query_set_format_map["drop_db"].format(database=database),
                engine,
            )
    
        @classmethod
        def create_db(cls, database: str, engine: Engine) -> None:
            return cls.execute(
                cls.query_set_format_map["create_db"].format(database=database),
                engine,
            )
    ```


5. **database 도 init.py를 만들어 기존의 `db, Base`외 `MySQL class`도 추가 import해준다.**
    ```python
    from .conn import db, Base
    from .mysql import MySQL
    ```

6. 기존 local실행은 무조건 root로 접속하던 것을 삭제한다.
    ```python
    @dataclass
    
    class Config(metaclass=SingletonMetaClass):
    
        def __post_init__(self):
            # main.py(not DOCKER_MODE ) or local pytest(self.TEST_MODE) 실행
            if not DOCKER_MODE or self.TEST_MODE:
                self.PORT = 8001  # main.py 전용 / docker(8000) 도는 것 대비 8001
    
                self.MYSQL_HOST = "localhost"  # main.py시 mysql port는 환경변수로
                # self.MYSQL_USER = 'root'
                # self.MYSQL_PASSWORD = parse.quote(self.MYSQL_ROOT_PASSWORD)
    ```

7. 이 때, `root여야만, database 생성, 유저권한부여`가 가능하므로, root정보로 test에서는 바꿔줘야한다.
    - `'%'` 호스트는 MySQL에서 모든 호스트를 나타냅니다. '%'를 사용하면 해당 사용자가 어떤 호스트에서든 접속할 수 있도록 허용됩니다.
    ```python
    SYNC_DB_URL: str = config.DB_URL.replace("aiomysql", "pymysql") \
        .replace(config.MYSQL_USER, 'root') \
        .replace(config.MYSQL_PASSWORD, config.MYSQL_ROOT_PASSWORD)
    
    if not database_exists(SYNC_DB_URL):
        sync_engine = create_engine(SYNC_DB_URL, poolclass=NullPool, echo=config.DB_ECHO)
        create_database(sync_engine.url)
    
        if not MySQL.exists_user(user=config.MYSQL_USER, engine=sync_engine):
            MySQL.create_user(user=config.MYSQL_USER, password=config.MYSQL_PASSWORD, host=config.MYSQL_HOST,
                              engine=sync_engine)
        if not MySQL.is_user_granted(user=config.MYSQL_USER, database=config.MYSQL_DATABASE, engine=sync_engine):
            MySQL.grant_user(
                grant="ALL PRIVILEGES",
                on=f"{config.MYSQL_DATABASE}.*",
                to_user=config.MYSQL_USER,
                user_host='%',
                engine=sync_engine,
            )
    
    ```
8. conn.py에서도 database를 체크한다(`docker없는 환경에서 생성하는 경우`)
    - 이 땐, create/drop table할 일이 없으므로, engine생성도 DB가 없을 때만 생성한다.
    ```python
    class SQLAlchemy(metaclass=SingletonMetaClass):
        # ...
        def init_app(self, app: FastAPI, **kwargs):
    
            # no docker시, database + user 정보 생성
            SYNC_DB_URL: str = config.DB_URL.replace("aiomysql", "pymysql") \
                .replace(config.MYSQL_USER, 'root') \
                .replace(config.MYSQL_PASSWORD, config.MYSQL_ROOT_PASSWORD)
    
            if not database_exists(SYNC_DB_URL):
                sync_engine: Engine = create_engine(SYNC_DB_URL, poolclass=NullPool, echo=config.DB_ECHO)
                create_database(sync_engine.url)
    
                if not MySQL.exists_user(user=config.MYSQL_USER, engine=sync_engine):
                    MySQL.create_user(user=config.MYSQL_USER, password=config.MYSQL_PASSWORD, host=config.MYSQL_HOST,
                                      engine=sync_engine)
                if not MySQL.is_user_granted(user=config.MYSQL_USER, database=config.MYSQL_DATABASE, engine=sync_engine):
                    MySQL.grant_user(
                        grant="ALL PRIVILEGES",
                        on=f"{config.MYSQL_DATABASE}.*",
                        to_user=config.MYSQL_USER,
                        user_host='%',
                        engine=sync_engine,
                    )
    ```
    ```python
    # no docker시, database + user 정보 생성
    self.create_database_and_user()

    def create_database_and_user(self):
        SYNC_DB_URL: str = config.DB_URL.replace("aiomysql", "pymysql") \
            .replace(config.MYSQL_USER, 'root') \
            .replace(config.MYSQL_PASSWORD, config.MYSQL_ROOT_PASSWORD)
        
        if not database_exists(SYNC_DB_URL):
            sync_engine: Engine = create_engine(SYNC_DB_URL, poolclass=NullPool, echo=config.DB_ECHO)
            create_database(sync_engine.url)

            if not MySQL.exists_user(user=config.MYSQL_USER, engine=sync_engine):
                MySQL.create_user(user=config.MYSQL_USER, password=config.MYSQL_PASSWORD, host=config.MYSQL_HOST,
                                  engine=sync_engine)
            if not MySQL.is_user_granted(user=config.MYSQL_USER, database=config.MYSQL_DATABASE, engine=sync_engine):
                MySQL.grant_user(
                    grant="ALL PRIVILEGES",
                    on=f"{config.MYSQL_DATABASE}.*",
                    to_user=config.MYSQL_USER,
                    user_host='%',
                    engine=sync_engine,
                )
    ```

##### prepare_database

1. 이제 db가 생성된 상태이므로, engine을 이용해서connection을 만든 뒤, Base.metadata에 `reflect`로 변경사항을 반영하고, `create_all`로 테이블을 생성한다
    - yield로 반환 후, `drop_all`로 모든 테이블을 삭제한다
    ```python
    @pytest.fixture(scope="session")
    def engine():
        return sync_engine
    
    
    @pytest.fixture(autouse=True, scope='session')
    async def prepare_database(engine):
        with engine.connect() as conn:
            Base.metadata.reflect(conn) # bind안된 engine에 sqlalchemy 정보를 넘겨준다
            Base.metadata.create_all(conn)
            conn.commit()
            yield
            Base.metadata.drop_all(conn)
    ```

#### async conftest

##### event_loop with autouse=True

1. async 요청이나 실행을 위해서 yield loop를 주입시켜와서 닫도록 해줘야 async가 제대로 작동한다.
    ```python
    @pytest.fixture(scope="session", autouse=True)
    def event_loop():
        loop = asyncio.get_event_loop()
        yield loop 
        loop.close()
    ```

##### session

1. session은 비동기session의 generator에서 직접 추출(not depends)해서 사용해야므로, **future=True인 async_scoped_session을 async with으로 직접
   발급해서 쓴다.**
    - 직접 발급하는 내용은, 주입용 메서드 async def get_db -> 프로퍼티 db.session과 동일하다.
    ```python
    @pytest.fixture(scope="session")
    async def session():
        async with db.scoped_session() as session:
            yield session
    ```
2. **하지만, creaet_app(config) -> db.init_app()의 `app시작이 안된 상황`에서는 자체세션발급을 위한 `Base.scoped_session = `이 주어지지 않아서,
   db.session(get_db)로 세션을 꺼낼 수 없다.**

##### app구동 없이 db= Sqlalchemy(config)로 초기화하도록 구조변경 -> 앱 구동시만 db.init_app(app)

1. class Sqlalchemy()에 대해, init_app에서 초기화가 아니라, 생성자(init)에서 바로 초기화하도록 변경한다.
    - app객체만 옵션이고, `kwargs`나 외부에서 `**asdict(config객체)`로 객체 생성시 초기화되게 한다

```python
class SQLAlchemy(metaclass=SingletonMetaClass):

    # 1. 애초에 app객체 + 키워드인자들을 받아서 생성할 수 있지만,
    def __init__(self, app: FastAPI = None, **kwargs) -> None:
        # self._async_engine: AsyncEngine | None = None
        # self._Session: AsyncSession | None = None  # 의존성 주입용 -> depricated
        # self._scoped_session: async_scoped_session[AsyncSession] | None = None  # 자체 세션발급용

        database_url = kwargs.get("DB_URL",
                                  "mysql+aiomysql://travis:travis@mysql:13306/notification_api?charset=utf8mb4")
        pool_recycle = kwargs.setdefault("DB_POOL_RECYCLE", 900)
        echo = kwargs.setdefault("DB_ECHO", True)
        pool_size = kwargs.setdefault("DB_POOL_SIZE", 5)
        max_overflow = kwargs.setdefault("DB_MAX_OVERFLOW", 10)

        self._async_engine = create_async_engine(
            database_url,
            echo=echo,
            pool_recycle=pool_recycle,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
        )

        self._scoped_session: async_scoped_session[AsyncSession] | None =
            async_scoped_session(
                async_sessionmaker(
                    bind=self._async_engine, autocommit=False, autoflush=False, future=True,
                    expire_on_commit=False  # refresh로 대체할려 했으나, 매번 select가 되어 필요시마다 하기로.
                ),
                scopefunc=current_task,
            )

        # no docker시, database + user 정보 생성
        self.create_database_and_user()

        # 2. 혹시 app객체가 안들어올 경우만, 빈 객체상태에서 메서드로 초기화할 수 있다.
        if app is not None:
            self.init_app(app)

```
2. db.init_app()시 app객체만 받게 한다.
    ```python
    def init_app(self, app: FastAPI):
        """
        :param app:
        :return:
        """
        @app.on_event("startup")
        async def start_up():
            # 테이블 생성 추가
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                logging.info("DB create_all.")
    
        @app.on_event("shutdown")
        async def shut_down():
            # self._Session.close()
            await self._scoped_session.remove()  # async_scoped_session은 remove까지 꼭 해줘야한다.
            await self._async_engine.dispose()
            logging.info("DB disconnected.")
    ```
   
3. 외부에서는 Sqlalchemy객체 미리 생성할 때, config를 kwargs로 입력시키고, Base에 단일세션도 주입한다.
    ```python
    db = SQLAlchemy(**asdict(config))
    
    Base = declarative_base()
    # for mixin 자체 세션 발급
    Base.scoped_session = db.scoped_session
    ```
   
4. create_app에서도 config객체가 아닌 app객체로만 초기화한다
    ```python
    def create_app(config: Config):
        """
        앱 함수 실행
        :return:
        """
        app = FastAPI()
    
        db.init_app(app)
    ```
##### app객체 with config fixture

- pytest모듈환경내에서 이미 Test인 config로 app객체를 발행한다

1. app의 init.py에 있는 create_app메서드를 가져와서 생성한다.
    - 이 때, test모드가 아니면 에러를 내주는 게 좋다?
    ```python
    @pytest.fixture(scope="session")
    def app(config) -> FastAPI:
        if not config.TEST_MODE:
            raise SystemError("'test' environment must be set true ")
    
        return create_app(config)
    
    ```

##### api 테스트용 async_client 만들기

1. client를 만들기 위해서는 `app객체` + `base_url`이 필요하다.
    - 추후 동기로 작동하는, websocket url을 위해 `base_http_url` + `base_websocket_url`을 fixture로 만든다.
    - 추후 동기로 작동하는, TestClient도 생성해준다.


2. **비동기 테스트를 위해 `httpx`패키지를 설치하고, httpx의 AsyncClient를 가져온다.**
    ```shell
    pip install httpx
    
    pip freeze > .\requirements.txt
    
    docker-compose build --no-cache api; docker-compose up -d api;
    ```

3. AsyncClient fixture를 생성한다.
    ```python
    @pytest.fixture(scope="session")
    def base_http_url() -> str:
        return "http://localhost"
    
    
    # @pytest_asyncio.fixture(scope="session") # asyncio_mode = auto
    @pytest.fixture(scope="session")
    async def async_client(app: FastAPI, base_http_url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
        async with httpx.AsyncClient(app=app, base_url=base_http_url) as ac:
            yield ac
    ```
4. websocket용 TestClient를 생성한다. 이 때는 자체 starlette의 testclient라 url이 필요없다
    ```python
    @pytest.fixture(scope="session")
    def base_websocket_url() -> str:
        return "ws://localhost"
    
    
    @pytest.fixture(scope="session")
    def client(app: FastAPI) -> Generator[TestClient, None, None]:
        with TestClient(app=app) as tc:
            yield tc
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

3. docker 추가 명령어

```powershell
docker stop $(docker ps -aq)
docker rm $(docker ps -aqf status=exited)
docker network prune 

docker-compose -f docker-compose.yml up -d
```

### pip 명령어

```powershell
# 파이참 yoyo-migration 설치

pip freeze | grep yoyo

# 추출패키지 복사 -> requirements.txt에 붙혀넣기

```

### git 명령어

```powershell
git config user.name "" 
git config user.email "" 

```

### yoyo 명령어

```powershell
yoyo new migrations/

# step 에 raw sql 작성

yoyo apply --database [db_url] ./migrations 
```

- 참고
    - 이동: git clone 프로젝트 커밋id 복사 -> `git reset --hard [커밋id]`
    - 복구: `git reflog` -> 돌리고 싶은 HEAD@{ n } 복사 -> `git reset --hard [HEAD복사부분]`