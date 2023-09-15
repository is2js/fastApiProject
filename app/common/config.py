import os
from dataclasses import dataclass, field
from os import environ
from pathlib import Path
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

API_ENV: str = os.getenv("API_ENV", "local")
DOCKER_MODE: bool = os.getenv("DOCKER_MODE", "true") == "true"  # main.py 실행시 False 체크하고 load됨.
print(f"- API_ENV: {API_ENV}")
print(f"- DOCKER_MODE: {DOCKER_MODE}")

# database
DB_URL_FORMAT: str = "{dialect}+{driver}://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"

# prod
HOST_MAIN: str = environ.get("HOST_MAIN", "localhost")

## REST API SERVICE
# kakao - 나에게 메세지 보내기
KAKAO_SEND_ME_ACCESS_TOKEN = "Bearer " + environ.get("KAKAO_ACCESS_TOKEN")
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


@dataclass
class Config(metaclass=SingletonMetaClass):
    """
    기본 Configuration
    """
    BASE_DIR: str = base_dir
    LOG_DIR: str = base_dir.joinpath('logs/')

    PORT: int = int(environ.get("PORT", 8000))  # for docker
    DEBUG: bool = False  # Local main.py에서만 True가 되도록 설정 -> api/v1/services접속시 키2개요구x headers에 access_key만

    # database
    MYSQL_ROOT_PASSWORD: str = environ["MYSQL_ROOT_PASSWORD"]
    MYSQL_USER: str = environ["MYSQL_USER"]
    MYSQL_PASSWORD: str = environ.get("MYSQL_PASSWORD", "")
    MYSQL_HOST: str = "mysql"  # docker 서비스명
    MYSQL_DATABASE: str = environ["MYSQL_DATABASE"]
    MYSQL_PORT: int = int(environ.get("MYSQL_PORT", 13306))  # docker 내부용 -> 내부3306 고정
    DB_URL: str = None  # post_init에서 동적으로 채워진다.

    # sqlalchemy
    DB_ECHO: bool = True
    DB_POOL_RECYCLE: int = 900
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # prod or aws-ses
    HOST_MAIN: str = HOST_MAIN

    # middleware
    TRUSTED_HOSTS: list[str] = field(default_factory=lambda: ["*"])
    ALLOWED_SITES: list[str] = field(default_factory=lambda: ["*"])

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


@dataclass
class LocalConfig(Config):
    PROJ_RELOAD: bool = True
    DEBUG: bool = True
    # log
    LOG_BACKUP_COUNT: int = 1


@dataclass
class ProdConfig(Config):
    PROJ_RELOAD: bool = False
    # log
    LOG_BACKUP_COUNT = 10

    # sqlalchemy
    DB_ECHO: bool = True

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


config = Config.get()
# config = Config.get(option='prod')
# print(config)