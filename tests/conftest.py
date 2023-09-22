import asyncio
from datetime import datetime
from typing import AsyncGenerator, Generator, Any, Literal

import httpx
import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import NullPool, create_engine
from sqlalchemy_utils import database_exists, create_database
from starlette.testclient import TestClient

from app import create_app
from app.common.config import config  # 이미 pytest모듈 상황에선 TestConfig로 들어옴.
from app.database.conn import Base, db
from app.database.mysql import MySQL
from app.models import Users
from app.schemas import UserToken
from app.utils.auth_utils import create_access_token
from app.utils.date_utils import D
from app.utils.faker_utils import my_faker
from app.utils.param_utils import to_query_string, hash_query_string

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


@pytest.fixture(scope="session")
async def session():
    async with db.scoped_session() as session:
        yield session


@pytest.fixture(scope="session")
def app() -> FastAPI:
    if not config.TEST_MODE:
        raise SystemError("'test' environment must be set true ")

    app = create_app(config)
    yield app


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


@pytest.fixture(scope="session")
def user_info() -> dict[str, str]:
    return my_faker.create_user_info(status="active")


@pytest.fixture(scope="session")
def create_user_info():
    def func(**kwargs):
        return my_faker.create_user_info(**kwargs, status="active")

    return func


@pytest.fixture(scope="session")
async def login_headers(user_info: dict[str, str]) -> dict[str, str]:
    """
    User 생성 -> data(dict) 생성 -> token 생성
    """
    new_user = await Users.create(auto_commit=True, refresh=True, **user_info)

    new_user_data = UserToken \
        .model_validate(new_user) \
        .model_dump(exclude={'hashed_password', 'marketing_agree'})

    new_token = await create_access_token(data=new_user_data, expires_delta=24, )

    return dict(
        Authorization=f"Bearer {new_token}"
    )


@pytest.fixture(scope="session")
async def api_key_info(async_client: AsyncClient, login_headers: dict[str, str]):
    """
    asyncClient + 로그인 headers + api user_memo(랜덤)
     ->  api생성 및 access+secret_key 첫응답 속에 정보 추출
    """
    response = await async_client.post(
        "api/v1/users/apikeys",
        headers=login_headers,
        json=dict(user_memo=f"TESTING: {str(datetime.utcnow())}")
    )

    assert response.status_code == 201

    response_body = response.json()
    # assert "access_key" in response_body
    # assert "secret_key" in response_body
    assert "access_key" in response_body['data']
    assert "secret_key" in response_body['data']

    # return response_body
    return response_body['data']
    # {'user_memo': 'TESTING: 2023-09-20 01:09:27.206007', 'id': 1,
    # 'created_at': '2023-09-20T01:09:31',
    # 'access_key': '97a17d4c-50c3-41d5-ab7d-bd086699-ed1b-4cfc-a58a-267911c049f0',
    # 'secret_key': 'uVEMWd99axBFzs7CP5i3fCHcxZ98bQJSGB0r3zzW'}


@pytest.fixture(scope="session")
async def request_service(async_client: AsyncClient, api_key_info: dict[str, str]) -> Any:
    async def func(
            http_method: Literal["get", "post", "put", "delete", "options"],
            service_name: str = "",
            additional_headers: dict = {},
            method_options: dict = {},
            allowed_status_code: tuple = (200, 201),
            json: dict = {},
            data: dict = {},
    ):
        # 1. 서비스 요청 url 생성 with access_key -> query_string -> url
        url: str = f"/api/v1/services"

        # fastapi에서 마지막 endpoint에 /가 있으면 rediect되도록 인식된다. -> service_name이 있을때만 앞에 '/'를 붙인다.
        if service_name:
            url += f"/{service_name}"

        datetime_kst = D.datetime(diff_hours=9)
        timestamp = int(datetime_kst.timestamp())
        params = dict(key=api_key_info['access_key'], timestamp=timestamp)
        query_string: str = to_query_string(params)

        url += f"?{query_string}"

        # 2. service_login_headers 생성  'secret'=  query_string + secret_key를 해쉬한 값(DB와 일치)
        hashed_secret: str = hash_query_string(query_string, api_key_info['secret_key'])
        service_login_headers = dict(secret=hashed_secret) | additional_headers
        # {'secret': '/6Br4HL0G4QlYbmMvFD35hCQ1BDdD86MzKaAgyNao/Q='}

        method_options: dict = dict(headers=service_login_headers) | dict(json=json) | dict(data=data) | method_options

        # response = await async_client.get(url, headers=service_login_headers, )
        # response = await async_client.get(url, **method_options)
        client_method = getattr(async_client, http_method.lower())
        response = await client_method(url, **method_options)

        # assert response.status_code == 200
        assert response.status_code in allowed_status_code

        response_body = response.json()

        return response_body['data']

    return func
