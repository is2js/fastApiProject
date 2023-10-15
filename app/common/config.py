import os
from dataclasses import dataclass, field
from os import environ
from pathlib import Path
from sys import modules
from typing import Optional, Union
from urllib import parse

from dotenv import load_dotenv

from app.utils.singleton import SingletonMetaClass

# app 설정
# config.py의 위치에 따라 변동
base_dir = Path(__file__).parents[2]

# load .env
print("- Loaded .env file successfully.") if load_dotenv() \
    else print("- Failed to load .env file.")

# pytest가 동작할 땐, .env파일의 API_ENV=를 무시하고 "test"를 덮어쓰기 한다.
# -> 이렇게 해줌으로써, config객체를 import하면, 자동으로 testConfig로 생성되어있다.
if modules.get("pytest") is not None:
    print("- Run in pytest.")
    environ["API_ENV"] = "test"
    environ["DOCKER_MODE"] = "false"

API_ENV: str = os.getenv("API_ENV", "local")
DOCKER_MODE: bool = os.getenv("DOCKER_MODE", "true") == "true"  # main.py 실행시 False 체크하고 load됨.

print(f"- API_ENV: {API_ENV}")
print(f"- DOCKER_MODE: {DOCKER_MODE}")

# database
DB_URL_FORMAT: str = "{dialect}+{driver}://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"

# prod
HOST_MAIN: str = environ.get("HOST_MAIN", "localhost")
# auth
JWT_SECRET = environ.get("JWT_SECRET", "secret_key!!")

## REST API SERVICE
# kakao - 나에게 메세지 보내기: 카카오개발자 > 도구 > REST API 테스트 > 내앱 선택 > 엑세스 토큰 발급
KAKAO_SEND_ME_ACCESS_TOKEN = environ.get("KAKAO_SEND_ME_ACCESS_TOKEN", None)

KAKAO_SEND_ME_IMAGE_URL: Optional[
    str] = "https://github.com/is3js/hospital/blob/master/images/popup/mainPopup_530x640_2.jpg?raw=true"
KAKAO_SEND_ME_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

# email
ADMIN_GMAIL = os.getenv('ADMIN_GMAIL', None)
ADMIN_GMAIL_APP_PASSWORD = os.getenv('ADMIN_GMAIL_APP_PASSWORD', None)
ADMIN_GMAIL_NICKNAME = os.getenv('ADMIN_GMAIL_NICKNAME', None)

# aws ses
AWS_ACCESS_KEY: str = environ.get("AWS_ACCESS_KEY", None)
AWS_SECRET_KEY: str = environ.get("AWS_SECRET_KEY", None)
AWS_SES_AUTHORIZED_EMAIL: str = environ.get("AWS_SES_AUTHORIZED_EMAIL", None)

# oauth
GOOGLE_CLIENT_ID: str = environ.get("GOOGLE_CLIENT_ID", None)
GOOGLE_CLIENT_SECRET: str = environ.get("GOOGLE_CLIENT_SECRET", None)

KAKAO_CLIENT_ID: str = environ.get("KAKAO_CLIENT_ID", None)
KAKAO_CLIENT_SECRET: str = environ.get("KAKAO_CLIENT_SECRET", None)

DISCORD_CLIENT_ID: str = environ.get("DISCORD_CLIENT_ID", None)
DISCORD_CLIENT_SECRET: str = environ.get("DISCORD_CLIENT_SECRET", None)

DISCORD_BOT_TOKEN: str = environ.get("DISCORD_BOT_TOKEN", None)
DISCORD_BOT_SECRET_KEY: str = environ.get("DISCORD_BOT_SECRET_KEY", None)
DISCORD_GENERATED_AUTHORIZATION_URL: str = environ.get("DISCORD_GENERATED_AUTHORIZATION_URL", None)


@dataclass
class Config(metaclass=SingletonMetaClass):
    """
    기본 Configuration
    """
    APP_VERSION: str = environ.get("APP_VERSION", "")
    APP_TITLE: str = environ.get("APP_TITLE", "")
    APP_DESCRIPTION: str = environ.get("APP_DESCRIPTION", "")

    BASE_DIR: str = base_dir
    LOG_DIR: str = base_dir.joinpath('logs/')
    LOG_BACKUP_COUNT: int = 1

    PORT: int = int(environ.get("PORT", 8000))  # for docker
    PROJ_RELOAD: bool = False  # local에서만 True
    DEBUG: bool = False  # Local main.py에서만 True가 되도록 설정 -> api/v1/services접속시 키2개요구x headers에 access_key만
    TEST_MODE: bool = False  # sqlalchemy에서 TEST용 db를 지웠다 만들기 등
    #### DOCKER_MODE는 main.py 실행인지/docker실행인지 모르기 때문에
    #### => 직접 실행 직전에 os.environ[]에 넣어줘야, MYSQL_HOST와 PORT가 바뀐다.

    # admin user for role
    ADMIN_EMAIL = environ.get("ADMIN_EMAIL")

    # database
    MYSQL_ROOT_PASSWORD: str = environ["MYSQL_ROOT_PASSWORD"]
    MYSQL_USER: str = environ["MYSQL_USER"]
    MYSQL_PASSWORD: str = environ.get("MYSQL_PASSWORD", "")
    MYSQL_HOST: str = environ.get("MYSQL_HOST", "localhost")  # docker 서비스명
    MYSQL_DATABASE: str = environ["MYSQL_DATABASE"]
    MYSQL_PORT: int = int(environ.get("MYSQL_PORT", 13306))  # docker 내부용 -> 내부3306 고정
    DB_URL: str = None  # post_init에서 동적으로 채워진다.

    # sqlalchemy
    DB_ECHO: bool = True
    DB_POOL_RECYCLE: int = 900
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # middleware
    TRUSTED_HOSTS: list[str] = field(default_factory=lambda: ["*"])
    ALLOWED_SITES: list[str] = field(default_factory=lambda: ["*"])

    # prod or aws-ses
    HOST_MAIN: str = HOST_MAIN
    FRONTEND_URL: str = f'https://{HOST_MAIN}'

    def __post_init__(self):
        # main.py(not DOCKER_MODE ) or local pytest(self.TEST_MODE) 실행
        if not DOCKER_MODE or self.TEST_MODE:
            self.PORT = 8001  # main.py 전용 / docker(8000) 도는 것 대비 8001

            self.MYSQL_HOST: str = "localhost"  # main.py시 mysql port는 환경변수로
            # self.MYSQL_USER = 'root'
            # self.MYSQL_PASSWORD = parse.quote(self.MYSQL_ROOT_PASSWORD)

        # not main.py  실행 -> docker or pytest
        else:
            self.MYSQL_PORT: int = 3306  # docker 전용 / 3306 고정

        self.DB_URL: str = DB_URL_FORMAT.format(
            dialect="mysql",
            driver="aiomysql",
            user=self.MYSQL_USER,
            password=parse.quote(self.MYSQL_PASSWORD),
            host=self.MYSQL_HOST,
            port=self.MYSQL_PORT,
            database=self.MYSQL_DATABASE,
        )

        # redirect시 필요한 프론트 DOMAIN 동적으로 만들기
        # self.FRONTEND_URL: str = f'http://localhost:{self.PORT}/authenticated-route' if API_ENV != 'prod' \
        #     else f'https://{HOST_MAIN}'
        self.DOMAIN: str = f'http://{self.HOST_MAIN}:{self.PORT}' if API_ENV != 'prod' else f'https://{HOST_MAIN}'

    @staticmethod
    def get(option: Optional[str] = None) -> Union["LocalConfig", "ProdConfig", "TestConfig"]:
        if option is not None:
            return dict(
                prod=ProdConfig,
                local=LocalConfig,
                test=TestConfig,
            )[option]()
        elif API_ENV is not None:
            return dict(
                prod=ProdConfig,
                local=LocalConfig,
                test=TestConfig,
            )[API_ENV.lower()]()
        else:
            return LocalConfig()


@dataclass
class LocalConfig(Config):
    HOST_MAIN: str = "localhost"

    PROJ_RELOAD: bool = True  # 자동 재시작
    DEBUG: bool = True  # access_control service를 jwt로 처리(not access_key+ secret key)


@dataclass
class ProdConfig(Config):
    # log
    LOG_BACKUP_COUNT = 10

    # sqlalchemy
    DB_ECHO: bool = False

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


@dataclass
class TestConfig(Config):
    TEST_MODE: bool = True  # test db 관련 설정 실행

    HOST_MAIN: str = "localhost"

    # sqlalchemy
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 1
    DB_MAX_OVERFLOW: int = 0

    # db
    MYSQL_DATABASE: str = os.getenv('MYSQL_DATABASE_TEST', environ["MYSQL_DATABASE"] + '_test')
    MYSQL_HOST: str = "localhost"


config = Config.get()
print(config)
