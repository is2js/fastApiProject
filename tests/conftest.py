import asyncio
from typing import AsyncGenerator, Generator

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import NullPool, create_engine
from sqlalchemy_utils import database_exists, create_database
from starlette.testclient import TestClient

from app import create_app
from app.common.config import config  # 이미 pytest모듈 상황에선 TestConfig로 들어옴.
from app.database.conn import Base, db
from app.database.mysql import MySQL

#########
# sync  # for database 생성
#########

SYNC_DB_URL: str = config.DB_URL.replace("aiomysql", "pymysql") \
    .replace(config.MYSQL_USER, 'root') \
    .replace(config.MYSQL_PASSWORD, config.MYSQL_ROOT_PASSWORD)

sync_engine = create_engine(SYNC_DB_URL, poolclass=NullPool, echo=config.DB_ECHO)

if not database_exists(sync_engine.url):
    create_database(sync_engine.url)

if not MySQL.exists_user(user=config.MYSQL_USER, engine=sync_engine):
    MySQL.create_user(user=config.MYSQL_USER, password=config.MYSQL_PASSWORD, host=config.MYSQL_HOST,
                      engine=sync_engine)
if not MySQL.is_user_granted(user=config.MYSQL_USER, database=config.MYSQL_DATABASE, engine=sync_engine):
    MySQL.grant_user(
        grant="ALL PRIVILEGES",
        on=f"{config.MYSQL_DATABASE}.*",
        to_user=config.MYSQL_USER,
        user_host='%',  # user가 부여받을 접근가능 host -> all '%'
        engine=sync_engine,
    )


@pytest.fixture(scope="session")
def engine():
    return sync_engine


@pytest.fixture(autouse=True, scope='session')
async def prepare_database(engine):
    with engine.connect() as conn:
        Base.metadata.reflect(conn)  # bind안된 engine에 sqlalchemy 정보를 넘겨준다
        Base.metadata.create_all(conn)
        conn.commit()
        yield
        Base.metadata.drop_all(conn)


#########
# async #
#########


@pytest.fixture(scope="session", autouse=True)
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def session():
    async with db.scoped_session() as session:
        yield session


@pytest.fixture(scope="session")
def app() -> FastAPI:
    if not config.TEST_MODE:
        raise SystemError("'test' environment must be set true ")

    return create_app(config)


@pytest.fixture(scope="session")
def base_http_url() -> str:
    return "http://localhost"


# @pytest_asyncio.fixture(scope="session") # asyncio_mode = auto
@pytest.fixture(scope="session")
async def async_client(app: FastAPI, base_http_url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(app=app, base_url=base_http_url) as ac:
        yield ac


@pytest.fixture(scope="session")
def base_websocket_url() -> str:
    return "ws://localhost"


@pytest.fixture(scope="session")
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app=app) as tc:
        yield tc
