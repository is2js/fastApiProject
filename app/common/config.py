import os
from dataclasses import dataclass, field
from os import path, environ
from pathlib import Path
from typing import Optional, Union
from urllib import parse

from dotenv import load_dotenv

from app.utils.singleton import SingletonMetaClass

# config.py의 위치에 따라 변동
base_dir = Path(__file__).parents[2]

# load .env
print("- Loaded .env file successfully.") if load_dotenv() \
    else print("- Failed to load .env file.")

API_ENV: str = os.getenv("API_ENV", "local")
DOCKER_MODE: bool = os.getenv("DOCKER_MODE", "true") == "true"
print(f"- API_ENV: {API_ENV}")
print(f"- DOCKER_MODE: {DOCKER_MODE}")

# prod 관련
HOST_MAIN: str = environ.get("HOST_MAIN", "localhost")


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
    DB_URL_FORMAT: str = "{dialect}+{driver}://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
    MYSQL_ROOT_PASSWORD: str = environ["MYSQL_ROOT_PASSWORD"]
    MYSQL_USER: str = environ["MYSQL_USER"]
    MYSQL_PASSWORD: str = environ.get("MYSQL_PASSWORD", "")
    MYSQL_HOST: str = "mysql"  # docker 서비스명
    MYSQL_DATABASE: str = environ["MYSQL_DATABASE"]
    MYSQL_PORT: int = int(environ.get("MYSQL_PORT", 13306))  # docker 내부용 -> 내부3306 고정

    # sqlalchemy
    DB_ECHO: bool = True
    DB_POOL_RECYCLE: int = 900
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # middleware
    TRUSTED_HOSTS: list[str] = field(default_factory=lambda: ["*"])
    ALLOWED_SITES: list[str] = field(default_factory=lambda: ["*"])

    def __post_init__(self):
        # main.py 실행
        if not DOCKER_MODE:
            self.PORT = 8001  # main.py 전용 / docker(8000) 도는 것 대비 8001
            self.MYSQL_HOST = "localhost"  # main.py시 mysql port는 환경변수로
            self.MYSQL_USER = 'root'
            self.MYSQL_PASSWORD = parse.quote("root")
        # docker 실행
        else:
            self.MYSQL_PORT = 3306  # docker 전용 / 3306 고정

        self.DB_URL = self.DB_URL_FORMAT.format(
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


# def conf():
#     """
#     Config객체들을, 환경별(key) -> value의 dict로 만들어놓고,
#     환경변수 APP_ENV에 따라, 해당 Config객체를 추출하기
#     :return: dataclass Config 객체
#     """
#     config = dict(prod=ProdConfig, local=LocalConfig)
#     # return config.get(environ.get("APP_ENV", "local"))
#     return config[environ.get("APP_ENV", "local")]()


config = Config.get()
print("singleton config>>>", config)
