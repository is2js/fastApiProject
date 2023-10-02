### 카카오

1. 타인의 전화번호로 보내려면, 핸드폰 -> 알림톡서비스(사업자 필요) 5~7원 정도가 필요하다.
2. SOLAPI: 저렴하고 싸게 서비스 이용가능.
3. 카카오 개발자 > 메세지
    - 나에게 보내기만 가능
    - 타인: 내 친구 + 내 어플리케이션 가입 + 개발자도 가입 된 상태 -> 사실상 못보낸다.
4. 다른 플랫폼의 서비스 -> 내 rest api에서 사용하는 것이 주 목적
5. 도커 메일 서버 -> 스팸으로 빠지지 않기 위해 많은 장치 필요
    - **AWS SES로 한달 6만건 정도 무료로 사용해본다.**
6. AWS SES -> 프리티어는 EC2에 호스팅된 어플리케이션에 대해 62000건 무료(영원히 무료)

#### 카카오 설정

1. 내 어플리케이션 > 앱이름/사업자명(한의원인증앱/조재성)
2. 카카오 로그인 > 동의항목 (소셜로그인용)
    - 닉네임+프로필사진+이메일 필수, 성별/연령대/친구목록 추가
    - 카카오톡 메시지 전송 / talk_message 필수 추가
3. 카카오 로그인 클릭 > 활성화 설정 ON
    - 안하면 나에게 메세지 보내기 테스트에서 로그인 설정안된 앱이라고 뜸.
4. 문서 > restapi에서 필요한 정보 보기(sample, 등)
5. **도구 > RESTAPI 테스트 > `나에게 기본 템플릿으로 보내기`를 선택 한 뒤,**
    - 인증앱을 sample -> 내가 만든 애플리케이션으로 선택
    - **8시간되면 만료. 추후 코드로 refresh해서 재생산해야하는 `access token`을 발급한 뒤 가져온다.**
    - **발급받은 임시토큰을 .env에 `KAKAO_KEY=`라고 저장해놓고, Config 수정하기 전까진 직접 router에서 쓸 예정.**
    - **해당 토큰은 나에게보내기 메세지 요청시 `headers의 Authorization`으로 넣어줘야한다.**

### config.py 재설계

1. os.path를 `pathlib.Path`로 변경한다.
    - **폴더를 연결한다면,`폴더/`로 .joinpath로 하면된다.**
    ```python
    from pathlib import Path
    
    # config.py의 위치에 따라 변동
    # base_dir = path.dirname(path.dirname(path.dirname(path.abspath(__file__))))
    # C:\Users\cho_desktop\PycharmProjects\fastApiProject
    base_dir = Path(__file__).parents[2]
    # /app
    @dataclass
    class Config:
        """
        기본 Configuration
        """
        BASE_DIR: str = base_dir
        # LOG_DIR: str = path.join(BASE_DIR, 'logs')
        LOG_DIR: str = base_dir.joinpath('logs/')
    ```
2. load_dotenv()를 이용하기 위해, **`python-dotenv` 패키지를 설치하고 재빌드해준다.**
    ```shell
    pip install python-dotenv
    pip freeze > .\requirements.txt
    
    docker-compose build --no-cache api; docker-compose up -d api;
    ```

3. **load_dotenv()의 return값을 if에서 호출하면서, .env파일을 가져왓는지 알려준다.**
    ```python
    from dotenv import load_dotenv
    
    # config.py의 위치에 따라 변동
    base_dir = Path(__file__).parents[2]
    
    # load .env
    print("- Loaded .env file successfully.") if load_dotenv() else print("- Failed to load .env file.")
        
    ```

4. **.env에 `API_ENV=`를 작성한다. 문자열 "local", "prod", "test"가 가능하다.**
    ```dotenv
    # API_ENV can be "local", "test", "prod"
    API_ENV="local"
    ```

5. API_ENV외에 `DOCKER_MODE=` 여부도 `default True`로 설정하는데, **도커모드는 `main.py 실행`을 제외하면 일단 무조건 True이므로 `.env에는 설정안한다`**
    - **bool로 삽입해야하는데, getenv는 문자열 "true"이므로, `== "true"`로 비교해서 들어가게 한다.**
    ```python   
    API_ENV: str = os.getenv("API_ENV", "local")
    DOCKER_MODE: bool = os.getenv("DOCKER_MODE", "true") == "true"
    print(f"- API_ENV: {API_ENV}")
    print(f"- DOCKER_MODE: {DOCKER_MODE}")
    ```

6. main.py로 실행시 Docker_mode를 False로 환경변수에 박아준다.
    - main실행 & **test환경만 아니면, docker_mode False로 처리해주고, `uvicorn.run()`으로 실행시킨다.**
    ```python
    if __name__ == '__main__':
        if os.getenv('API_ENV') != 'test':
            os.environ["API_ENV"] = "local"
        os.environ["DOCKER_MODE"] = "False"
   
       uvicorn.run("main:app", port=8010, reload=True)
    ```

7. 어차피 실행이 안되는데, 그 이유는 db_url 때문이다.
    - **DOCKER_MODE=False라면, Config의 DB_URL을 `localhost:3306`로 `동적으로 변경`해줘야 한다.**
    - **동적으로 string을 바꾸려면 `f"{} {}"`가 아닌 `변수:str ="{} {}" -> 상황마다 변수.format(, )"`로 채워줘야한다.**
        - dataclass Config에서는 동적으로 값을 바꿀 땐, `__post_init__`을 활용한다.
    - **각 채울 값들도 `dialect + driver`를 제외하고 이미 .env에 정의되어있어야 한다.**
    ```python
    @dataclass
    class Config():
        # ...
        # database
        DB_URL_FORMAT: str = "{dialect}+{driver}://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
        MYSQL_ROOT_PASSWORD: str = environ["MYSQL_ROOT_PASSWORD"]
        MYSQL_USER: str = environ["MYSQL_USER"]
        MYSQL_PASSWORD: str = environ.get("MYSQL_PASSWORD", "")
        MYSQL_HOST: str = "mysql"  # docker 서비스명
        MYSQL_DATABASE: str = environ["MYSQL_DATABASE"]
        MYSQL_PORT: int = int(environ.get("MYSQL_PORT", 3306))
        
        # ...
        
        def __post_init__(self):
            if not DOCKER_MODE:
                self.MYSQL_USER = 'root'
                self.MYSQL_PASSWORD = parse.quote(self.MYSQL_ROOT_PASSWORD)
                self.MYSQL_HOST = "localhost"
    
            self.DB_URL = self.DB_URL_FORMAT.format(
                dialect="mysql",
                driver="aiomysql",
                user=self.MYSQL_USER,
                password=parse.quote(self.MYSQL_PASSWORD),
                host=self.MYSQL_HOST,
                port=self.MYSQL_PORT,
                database=self.MYSQL_DATABASE,
            )
    
    ```
    - **그대로 해당 요소들을 .env에 정의하고 -> docker-compose.yml에서 가져다 사용하도록 변경한다.**
    ```dotenv
    # API_ENV can be "local", "test", "prod"
    API_ENV="local"
    
    # Your MySQL DB info
    MYSQL_DATABASE="notification_api"
    MYSQL_ROOT_PASSWORD="root"
    MYSQL_USER="travis"
    MYSQL_PASSWORD="travis"
    
    ```
    ```dotenv
    services:
      mysql:
        build:
          context: .
          dockerfile: docker/db/mysql/Dockerfile
        restart: always
        env_file:
          - .env
        ports:
          # [수정]
          - "13306:3306"
        environment:
          TZ: Asia/Seoul
          MYSQL_ROOT_PASSWORD: "${MYSQL_ROOT_PASSWORD}"
          MYSQL_DATABASE:  "${MYSQL_DATABASE}"
          # travis CI는 test용db를 만들 때 유저명이 travis를 쓴다.
          MYSQL_USER: "${MYSQL_USER}"
          MYSQL_PASSWORD: "${MYSQL_PASSWORD}"
    ```

8. 더 작업하기 전에 Config를 `싱글톤`으로 만든다.
    - utils > `singleton.py`에 metaclass=로 쓰일 싱글톤 클래스를 정의하고
    - Config가 metaclass=로 상속하고, API_ENV를 사용해서, 싱글톤으로 가져오게 한다.
    ```python
    # singleton.py
    
    class SingletonMetaClass(type):
        _instances = {}
    
        def __call__(cls, *args, **kwargs):
            if cls not in cls._instances:
                cls._instances[cls] = super().__call__(*args, **kwargs)
            return cls._instances[cls]
    ```
    - `.get()`으로 객체를 가져오는 데, 원하면 `API_ENV`보다 우선적으로 `option`을 넣을 수 있따.
    ```python
    # config.py
   
    @dataclass
    class Config(metaclass=SingletonMetaClass):
       # ...
      
      @staticmethod
      def get(
              option: Optional[str] = None,
      ) -> Union["LocalConfig", "ProdConfig", "TestConfig"]:
          if option is not None:
              return {
                  "prod": ProdConfig,
                  "local": LocalConfig,
                  # "test": TestConfig,
              }[option]()
          else:
              if API_ENV is not None:
                  return {
                      "prod": ProdConfig,
                      "local": LocalConfig,
                      # "test": TestConfig,
                  }[API_ENV.lower()]()
              else:
                  return LocalConfig()
    ```
   ```python
    # def conf():
    # """
    #     Config객체들을, 환경별(key) -> value의 dict로 만들어놓고,
    #     환경변수 APP_ENV에 따라, 해당 Config객체를 추출하기
    #     :return: dataclass Config 객체
    #     """
    #     config = dict(prod=ProdConfig, local=LocalConfig)
    #     # return config.get(environ.get("APP_ENV", "local"))
    #     return config[environ.get("APP_ENV", "local")]()
    
    
    config = Config.get()
    print("singleton config>>>", config)
    ```

9. conf가 사용됬던 곳들을 수정해준다.
    - conf().xxx => config.바로 사용

```python
def create_app():
    """
    앱 함수 실행
    :return:
    """
    app = FastAPI()

    # config = conf()
    # config_dict = asdict(config)
    db.init_app(app, **asdict(config))
```

```python
class Logger:

    # def __init__(self, log_name, backup_count=conf().LOG_BACKUP_COUNT):
    def __init__(self, log_name, backup_count=config.LOG_BACKUP_COUNT):
```

11. **추후 docker로 앱을 run할 때의 host와 port는 `dockerfile`의 `ENTRYPOINT`에서 실행 + `docker-compose.yml`의
    command로 `--host`, `--port`지정할 예정이지만**
    - 이 때, `main.py(local)`로 실행시, config의 `PORT`를 따르게 config를 가져와주는데, `도커용 8000` + **DOCKER_MODE False시 동적으로 `8001`**으로
      설정하고 가져와준다.
        - `local - docker` 실행시에는, docker-compose.yml에 `--host`, `--port`를 command에 입력하고, `실행은 Dockerfile`의 `ENTRY`에
          적어놓는다?
    ```python
    @dataclass
    class Config(metaclass=SingletonMetaClass):
        # ...
        PORT: int = int(environ.get("PORT", 8000))  # for docker
        # ...
        def __post_init__(self):
            if not DOCKER_MODE:
                self.PORT = 8001  # main.py 전용 / docker(8000) 도는 것 대비 8001
    ```
    ```dotenv
    PORT=8000
    ```
    ```dockerfile
    api:
    ports:
      - "${PORT}:8000"
    ```
12. **docker내부의 포트는 8000으로 고정시키기 위해 `dockerfile`에서 `unvicorn app.main:app`을 ENTRYPOINT로 옮기고**
    - **docker-compose에서 --host --port를 8000으로 고정한다.**
    - **ports에서 host접근PORT만 환경변수로 되도록 유지한다.**
    ```dockerfile
    RUN python -m pip install --upgrade pip && \
        pip install -r requirements.txt --root-user-action=ignore && \
        rm -rf /root/.cache/pip && \
        ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
    
    ENTRYPOINT ["uvicorn", "app.main:app"]
    ```
    ```dockerfile
    # docker-compose.yml
      api:
        command: [
    #      "uvicorn",
    #      "app.main:app",
          "--host=0.0.0.0",
          "--port=8000",
          "--reload"
        ]
    ```
    - **Dockerfile 수정하면 `재빌드`해야한다.**
    ```shell
    docker-compose build --no-cache api; docker-compose up -d api;
    ```
13. 이제 main.py(only olca)에서의 `포트를 8001로 고정한 것을 사용`하기 위해, **main.py에서 `config.PORT(default8000, docker_mode false시, 8001)`를 지정해준다.**
    ```python
    if __name__ == '__main__':
        if os.getenv('API_ENV') != 'test':
            os.environ["API_ENV"] = "local"
        os.environ["DOCKER_MODE"] = "False"
    
        uvicorn.run("main:app", port=config.PORT, reload=config.PROJ_RELOAD)
    ```

14. **하지만 main내부에서, DOCKER_MODE=False를 줬어도, config객체가 생겨난 이후 준 것이라, 설정 이후 메모리에 로드되도록 import순서를 바꿔야한다.**
    - **main실행이 아닌 `else`에서도 config객체를 쓰려면, create_app이 config객체를 인자로 받도록 수정한다.**
    - 이렇게 되면, 실행명령에선 create_app 팩토리메서드가 아닌 무조건 config를 받아 생성된 객체 app을 호출해야한다.
    - **추가로 main 실행시 running in multiprocessing mode에서 multiprocess spawning될 때 에러가 나는데 `pass`한다**
    - **그 전에 `def create_app` 정의 과정에서 config가 결정되어버리므로, `app(root)/__init__.py에 create_app을 옮긴다`**
    ```python
    # app/__init__.py
    from dataclasses import asdict
    
    from fastapi import FastAPI
    from starlette.middleware.cors import CORSMiddleware
    
    from app import api
    from app.common.config import Config
    from app.database.conn import db
    from app.middlewares.access_control import AccessControl
    from app.middlewares.trusted_hosts import TrustedHostMiddleware
    from app.pages import index
    
    
    def create_app(config: Config):
        """
        앱 함수 실행
        :return:
        """
        app = FastAPI()
    
        db.init_app(app, **asdict(config))
    
        # 미들웨어 추가 (실행순서는 반대)
        app.add_middleware(AccessControl)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.ALLOW_SITE,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.TRUSTED_HOSTS, except_path=["/health"])
    
        # route 등록
        app.include_router(index.router)  # template or test
        app.include_router(api.router, prefix='/api')
        # app.include_router(auth.router, tags=["Authentication"], prefix="/api")
        # app.include_router(user.router, tags=["Users"], prefix="/api", dependencies=[Depends(API_KEY_HEADER)])
    
        return app
    ```
    - **main.py에서는 app객체를 일단 생성해야하는데, `DOCKER_MODE=False -> create_app import -> config import` 순으로 설정해서 실행되도록 한다**
    ```python
    import os
    
    if __name__ == "__mp_main__":
        """Option 1: Skip section for multiprocess spawning
        This section will be skipped when running in multiprocessing mode"""
        pass
    
    elif __name__ == '__main__':
        if os.getenv('API_ENV') != 'test':
            os.environ["API_ENV"] = "local"
        os.environ["DOCKER_MODE"] = "False"
    
        from app import create_app
        from app.common.config import config
        import uvicorn
    
        app = create_app(config)
        uvicorn.run("main:app", port=config.PORT, reload=config.PROJ_RELOAD)
    
    else:
        from app import create_app
        from app.common.config import config
    
        app = create_app(config)
    ```
15. main.py를 app>main.py 에서 `root > main.py`로 옮긴 뒤,  dockerfile과 main.py에서의 명령 string을 변경해준다.
    ```dockerfile
    #ENTRYPOINT ["uvicorn", "app.main:app"]
    ENTRYPOINT ["uvicorn", "main:app"]
    ```
    ```python
    elif __name__ == '__main__':
        # uvicorn.run("app.main:app", port=config.PORT, reload=config.PROJ_RELOAD)
        uvicorn.run("main:app", port=config.PORT, reload=config.PROJ_RELOAD)
    ```
    

16. **MYSQL_PORT의 환경변수를 `docker돌때면 무조건 3306`, 그외(main.py)는 `localhost + local port`로 `DB_URL`을 바꿔야한다.**
    ```dotenv
    MYSQL_PORT="13306" # local main.py시(DOCKER_MODE=False)에만 (내부는 3306 고정)
    ```
    ```python
    @dataclass
    class Config(metaclass=SingletonMetaClass):
        #...
        MYSQL_PORT: int = int(environ.get("MYSQL_PORT", 13306))  # docker 내부용 -> 내부3306 고정
    
        def __post_init__(self):
            # main.py 실행
            if not DOCKER_MODE:
                self.PORT = 8001  # main.py 전용 / docker(8000) 도는 것 대비 8001
                self.MYSQL_HOST = "localhost" # main.py시 mysql port는 환경변수로
                self.MYSQL_USER = 'root'
                self.MYSQL_PASSWORD = parse.quote(self.MYSQL_ROOT_PASSWORD)
            # docker 실행
            else:
                self.MYSQL_PORT = 3306  # docker 전용 / 3306 고정
    ```
    ```dockerfile
    services:
      mysql:
        ports:
          - "${MYSQL_PORT}:3306"
    ```
    
17. **DB_URL을 이후 초기화할거면, `기본값 None으로 초기화는 해놔야한다. post_init에서 self.DB_URL을 최초 정의하면 안된다.`**
    - DB_URL_FORMAT은 전역상수로 선언해놓고
    - DB_URL: str = None으로 초기화해놓고
    - post_init에서 동적 생성하도록 한다.

```python
# database
DB_URL_FORMAT: str = "{dialect}+{driver}://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"

@dataclass
class Config(metaclass=SingletonMetaClass):
    #...
    # database
    MYSQL_ROOT_PASSWORD: str = environ["MYSQL_ROOT_PASSWORD"]
    MYSQL_USER: str = environ["MYSQL_USER"]
    MYSQL_PASSWORD: str = environ.get("MYSQL_PASSWORD", "")
    MYSQL_HOST: str = "mysql"  # docker 서비스명
    MYSQL_DATABASE: str = environ["MYSQL_DATABASE"]
    MYSQL_PORT: int = int(environ.get("MYSQL_PORT", 13306))  # docker 내부용 -> 내부3306 고정
    DB_URL: str = None # post_init에서 동적으로 채워진다.

    def __post_init__(self):
        # main.py 실행
        if not DOCKER_MODE:
            self.PORT = 8001  # main.py 전용 / docker(8000) 도는 것 대비 8001

            self.MYSQL_HOST = "localhost"  # main.py시 mysql port는 환경변수로
            self.MYSQL_USER = 'root'
            self.MYSQL_PASSWORD = parse.quote(self.MYSQL_ROOT_PASSWORD)

        # docker 실행
        else:
            self.MYSQL_PORT = 3306  # docker 전용 / 3306 고정

        self.DB_URL: str = DB_URL_FORMAT.format(
            dialect="mysql",
            driver="aiomysql",
            user=self.MYSQL_USER,
            password=parse.quote(self.MYSQL_PASSWORD),
            host=self.MYSQL_HOST,
            port=self.MYSQL_PORT,
            database=self.MYSQL_DATABASE,
        )
```
    
### 기타 변수 설정
1. `DB_URL, pool_size, max_overflow`는 Config에서 동적완성되도록 고정하고 `Local Prod에선 삭제`한다.
    - `DEBUG`는 기본 False에 local에서만 True여부만 둔다.
    - `DB_ECHO`는 기본 True에 prod에서만 False로 둔다.

    ```python
    @dataclass
    class Config(metaclass=SingletonMetaClass):
    
        DEBUG: bool = False  # Local main.py에서만 True가 되도록 설정 -> api/v1/services접속시 키2개요구x headers에 access_key만
    
        # sqlalchemy
        DB_ECHO: bool = True
        DB_POOL_RECYCLE: int = 900
        DB_POOL_SIZE: int = 5
        DB_MAX_OVERFLOW: int = 10
   
    @dataclass
    class LocalConfig(Config):
    
        DEBUG: bool = True
    
    @dataclass
    class ProdConfig(Config):
    
        # sqlalchemy
        DB_ECHO: bool = True
    ```
   
2. trusted_hosts, allowed_sites는 **list == mutable변수로서, `field(default_factory=)`로 기본값을 줘야하고, 덮어써야한다.**
    - **`HOST_MAIN`을 지정하고, Config `*` 기본값에 Prod에서만 `f"*.{HOST_MAIN}"`, `HOST_MAIN`, `localhost`를 추가한다.**
    ```dotenv
    # Define these if you want to open production server with API_ENV="prod"
    # - e.g. yourdomain.com, if you are running API_ENV as production,
    # - this will be needed for TLS certificate registration
    HOST_MAIN="abc.com"
    ```
    ```python
    # prod 관련 
    HOST_MAIN: str = environ.get("HOST_MAIN", "localhost")
    
    @dataclass
    class Config(metaclass=SingletonMetaClass):
    
        # middleware
        TRUSTED_HOSTS: list[str] = field(default_factory=lambda: ["*"])
        ALLOWED_SITES: list[str] = field(default_factory=lambda: ["*"])
    
    
    @dataclass
    class ProdConfig(Config):
        # middleware
        TRUSTED_HOSTS: list = field(
            default_factory=lambda: [
                f"*.{HOST_MAIN}",
                HOST_MAIN,
                "localhost",
            ]
        )
        ALLOWED_SITES: list = field(
            default_factory=lambda: [
                f"*.{HOST_MAIN}",
                HOST_MAIN,
                "localhost",
            ]
        )
    ```
   

3. app > init.py의 create_app에 변수명 확인해준다.
    ```python
    def create_app(config: Config):
        # 미들웨어 추가 (실행순서는 반대)
        app.add_middleware(AccessControl)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.ALLOWED_SITES,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.TRUSTED_HOSTS, except_path=["/health"])
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