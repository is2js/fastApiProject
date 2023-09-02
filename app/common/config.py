from dataclasses import dataclass, asdict
from os import path, environ

# config.py의 위치에 따라 변동
base_dir = path.dirname(path.dirname(path.dirname(path.abspath(__file__))))


# print(base_dir)
# C:\Users\cho_desktop\PycharmProjects\fastApiProject

@dataclass
class Config:
    """
    기본 Configuration
    """
    BASE_DIR = base_dir
    LOG_DIR = path.join(BASE_DIR, 'logs')

    DB_POOL_RECYCLE: int = 900
    DB_ECHO: bool = True


# print(Config())  # 객체는, class __str__으로 찍힌다.
# Config(DB_POOL_RECYCLE=900, DB_ECHO=True)

# def abc(DB_ECHO=None, DB_POOL_RECYCLE=None, **kwargs):
#     print(DB_ECHO, DB_POOL_RECYCLE)

# abc(Config()) # 객체를 키워드인자에 넘기면, 첫번째의 객체로 대입된다.
# Config(DB_POOL_RECYCLE=900, DB_ECHO=True) None

# asdict()는 dataclass전용으로, 상수로 구성된 class의 객체를, dict로 변환해준다.
# print(asdict(Config()))
# {'DB_POOL_RECYCLE': 900, 'DB_ECHO': True}

# asdict()로 dict가 된 것을 **언패킹해서 함수에 넘겨주면, 상수들이, 해당하는 키워드인자에 각각 꼽히게 된다.
# abc(**asdict(Config()))
# True 900


@dataclass
class LocalConfig(Config):
    PROJ_RELOAD: bool = True

    # 도커 서비스 mysql + 도커자체port 3306으로 접속
    # - host에 연결시에는 localhost + 13306
    DB_URL: str = "mysql+pymysql://travis:travis@mysql:3306/notification_api?charset=utf8mb4"

    # 미들웨어
    ALLOW_SITE = ["*"]
    TRUSTED_HOSTS = ["*"]

    # log
    LOG_BACKUP_COUNT = 1


@dataclass
class ProdConfig(Config):
    PROJ_RELOAD: bool = False

    # CORS
    ALLOW_SITE = ["*"]
    # TRUSTED_HOST
    TRUSTED_HOSTS = ["*"]

    # log
    LOG_BACKUP_COUNT = 10


def conf():
    """
    Config객체들을, 환경별(key) -> value의 dict로 만들어놓고,
    환경변수 APP_ENV에 따라, 해당 Config객체를 추출하기
    :return: dataclass Config 객체
    """
    config = dict(prod=ProdConfig(), local=LocalConfig())
    return config.get(environ.get("APP_ENV", "local"))
