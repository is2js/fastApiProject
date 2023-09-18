### 참고
1. sqlalchemy class에서, is_test_mode면, 을 추가해서, 
    - self._engine.url의 db_url이 localhost여야한다. -> 아니면 에러
    - 새롭게 임시엔진을 만든다.
    - database가 있으면 drop하고, 다시 생성한다
    - 임시엔진을 .dispose()한다.

2. TestConfig에서는 database가 test용으로 notification_test 등으로 만들어야한다.
    - 이 때, travis를 쓸거면, travis@`localhost`를 db host로 써야한다.
3. pytest를 돌릴 때, Config객체가 testconfig로 들어가야한다.
    - config객체에 따라서 sqlalchemy 내부에서 초기화되는게 다르다.

4. conftest.py 
    - 일단 app객체를 만들 때, os.environ['API_ENV'] = "test"로 환경변수를 덮어쓴다.
    - 그다음에 해당엔진으로 table을 생성 + TestClient(app=app)생성을 동시에 한다.
5. session을 1개 뽑아와야하는데, Depends를 오버라이딩해서 처리해본다.
    - yield session이 돌아오면, 커밋을 하지 않고, 해당 sess로 table데이터를 다 삭제한 뒤, rollback을 해준다.
    - 이 때, table데이터 삭제시 해당session으로 fk제한을 제거시켜서 삭제한다.
6. login은 해당session으로 유저객체를 미리 생성 -> 토큰 생성 -> headers형태의 dict(Authorization=) 반환해준다.
7. pytest패키지를 설치 후, pytest만 명령해도 바로 가능하다.
8. 테스트코드는 실패의 경우도 다룬다.
9. 만약, kakao_token을 받는 테스트를 만들려면, mocking을 해야한다.
10. 실행편집 > `+` > Pytest 체크 후 > 경로 설정

### Test Conifg 작성
1. `pytest`로 작동할 때만, 환경변수 `API_ENV`에 .env파일을 무시하고 `test`로 덮어쓰기 한다.
    - modules.get("pytest")를 사용하여 현재 환경에서 pytest 모듈이 로드되었는지 확인합니다.
    ```python
    # pytest가 동작할 땐, .env파일의 API_ENV=""를 무시하고 "test"를 덮어쓰기 한다.
    if modules.get("pytest") is not None:
        print("- Run in pytest.")
        environ["API_ENV"] = "test"
    API_ENV: str = os.getenv("API_ENV", "local")
    DOCKER_MODE: bool = os.getenv("DOCKER_MODE", "true") == "true"  # main.py 실행시 False 체크하고 load됨.
    ```

2. 강제로 `Config.get(option="test")`로 option=을 주거나, `API_ENV가 "test"`면, TestConfig를 호출할 수 있게 한다.
    ```python
    @staticmethod
    def get(
            option: Optional[str] = None,
    ) -> Union["LocalConfig", "ProdConfig", "TestConfig"]:
        if option is not None:
            return {
                "prod": ProdConfig,
                "local": LocalConfig,
                "test": TestConfig,
            }[option]()
        else:
            if API_ENV is not None:
                return {
                    "prod": ProdConfig,
                    "local": LocalConfig,
                    "test": TestConfig,
                }[API_ENV.lower()]()
            else:
                return LocalConfig()
    ```

3. TestConfig를 정의한다.
    - **`TEST_MODE`=를 Config에서 기본 False로 두고, TestConfig에서는 True로 둔다.**
    - **해당 _MODE들은, db, redis 등의 `database test환경을 만드는데 사용`될 예정이다.**
    ```python
    @dataclass
    class Config(metaclass=SingletonMetaClass):
        TEST_MODE: bool = False  # sqlalchemy에서 TEST용 db를 지웠다 만들기 등 db/redis 관련 설정
    
    
    @dataclass
    class TestConfig(Config):
        TEST_MODE: bool = True  # test db 관련 설정 실행
        # sqlalchemy
        DB_POOL_SIZE: int = 1
        DB_MAX_OVERFLOW: int = 0
    ```

4. **추가로 test환경에서 쓸, database이름을 `MYSQL_DATABASE_TEST`로 따로 받고, 없으면 `MYSQL_DATABASE` + `_test`로 만든다.**
    ```python
    # Your MySQL DB info
    MYSQL_DATABASE="notification_api"
    MYSQL_DATABASE_TEST="notification_api_test"
    ```
    ```python
    @dataclass
    class TestConfig(Config):
        TEST_MODE: bool = True  # test db 관련 설정 실행
    
        # sqlalchemy
        DB_POOL_SIZE: int = 1
        DB_MAX_OVERFLOW: int = 0
    
        # db
        MYSQL_DATABASE: str = os.getenv('MYSQL_DATABASE_TEST', environ["MYSQL_DATABASE"] + '_test')
        MYSQL_HOST: str = "localhost"  # 테스트 환경에서는 무조건 localhost
    ```
   
5. docker모드이지만, config확인을 위해 찍어본다.
    - docker모드에서 api 서비스가 -> mysql서비스를 localhost로 인식이 안된다.
    ```python
    config = Config.get(option="test")
    print(config)
    ```
    ```python
    sqlalchemy.exc.OperationalError: (pymysql.err.OperationalError) (2003, "Can't connect to MySQL server on 'localhost'")
    ```
   
6. **도커에 `links: -서비스명`없이, ~~`localhost`로 연결되도록 networks 구성~~ 구성해도 localhost는 불가 host에 `서비스명`연결은 가능하다.**
    - **추후 traefik 사용을 위해 네트워크명을 `reverse-proxy-public`으로 지어놓는다.**
    ```dockerfile
    services:
      mysql:
        networks:
          - reverse-proxy-public
      api:
        networks:
          - reverse-proxy-public
      networks:
        reverse-proxy-public:
          driver: bridge
          ipam:
            driver: default
    ```
7. `MYSQL_HOST`를 .env 및 config에 정의해준다.
    ```dotenv
    MYSQL_HOST="mysql" # docker 서비스명(d-d) or aws 등 주소명 or 비우면 기본값localhost
    ```
    ```python
    @dataclass
    class Config(metaclass=SingletonMetaClass):
        MYSQL_HOST: str = environ.get("MYSQL_HOST", "localhost")  # docker 서비스명
    
    ```

### sqlalchemy init_app에서 config의 TEST_MODE 상태를 저장하기

1. create_app에서 db.init_app의 kwargs(config-> dict -> kwargs) 에서 TEST_MODE여부을 받을 수 있가 만들어놓기
    ```python
    class SQLAlchemy(metaclass=SingletonMetaClass):
    
        # 1. 애초에 app객체 + 키워드인자들을 받아서 생성할 수 있지만,
        def __init__(self, app: FastAPI = None, **kwargs) -> None:
            self._engine: AsyncEngine | None = None
            self._Session: AsyncSession | None = None  # 의존성 주입용 -> depricated
            self._scoped_session: async_scoped_session[AsyncSession] | None = None  # 자체 세션발급용
            
            self._is_test_mode: bool = False # 테스트 여부
    ```
    ```python
        def init_app(self, app: FastAPI, **kwargs):
            """
            DB 초기화
            :param app:
            :param kwargs:
            :return:
            """
            database_url = kwargs.get("DB_URL",
                                      "mysql+aiomysql://travis:travis@mysql:13306/notification_api?charset=utf8mb4")
            pool_recycle = kwargs.setdefault("DB_POOL_RECYCLE", 900)
            echo = kwargs.setdefault("DB_ECHO", True)
            pool_size = kwargs.setdefault("DB_POOL_SIZE", 5)
            max_overflow = kwargs.setdefault("DB_MAX_OVERFLOW", 10)
   
            self._is_test_mode = kwargs.get('TEST_MODE', False)
    
    ```
   

2. init_app_event시, `self._is_test_mode`면, 테이블 drop 하기
    ```python
    def init_app_event(self, app):
        @app.on_event("startup")
        async def start_up():
            # 테이블 생성 추가
            async with self.engine.begin() as conn:
                # 테스트모드라면, 테이블 삭제하고 생성하기
                if self._is_test_mode:
                    await conn.run_sync(Base.metadata.drop_all)
                    logging.info("TEST DB drop_all.")
    
                await conn.run_sync(Base.metadata.create_all)
                logging.info("TEST" if self._is_test_mode else "" + "DB create_all.")
    
    ```
### pytest 설치 및 테스트 코드 작성
1. pytest, pytest-asyncio 패키지 설치
    - asyncio 패키지는 `@pytest.mark.asyncio`데코레이터를 통해, event loop를 매번 생성하지 않아도 되게 해준다.
    ```shell
    pip install pytest pytest-asyncio
    
    pip freeze > .\requirements.txt
    
    docker-compose build --no-cache api; docker-compose up -d api;
    ```
    ```python
    def test_async_code():
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(async_function())
        assert result == 42
    
    @pytest.mark.asyncio
    async def test_async_code():
        result = await async_function()
        assert result == 42
    ```
2. root에 `tests`폴더를 만들고, 환경설정해주기
    - **`pytest` 명령어로 바로 실행되도도록 `pytest.ini`를 root 폴더에 생성(안잡아주면, docker의 파일을 검색하다가 에러남)**
        - `asyncio_mode=auto`를 통해, **mark.asyncio 데코를 안붙혀줘도 된다.**
    ```ini
    [pytest]
    pythonpath = [".", "app"]
    testpaths = tests/
    asyncio_mode = auto
    ```
   - **파이참에서는 실행버튼 좌측 > 구성편집 > `+` > pytest > 스크립트 경로 `tests폴더 지정`으로 해당 폴더를 바로 잡아준다.**



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