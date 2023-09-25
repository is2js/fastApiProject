from fastapi import Depends
from fastapi_users import FastAPIUsers

from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.config import JWT_SECRET, config
from app.database.conn import db
from app.libs.auth.oauth_clients import google_oauth_client, get_oauth_clients
from app.models import Users, OAuthAccount
from app.schemas import UserRead, UserCreate, UserUpdate
from app.libs.auth.backends import get_auth_backends, cookie_auth_backend
from app.libs.auth.managers import UserManager


async def get_user_db(session: AsyncSession = Depends(db.session)):
    # yield SQLAlchemyUserDatabase(session=session, user_table=Users)
    yield SQLAlchemyUserDatabase(session=session, user_table=Users, oauth_account_table=OAuthAccount)


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


# router에서 쿠키 아닌(no db조회) 로그인(sns_type선택한 api 회원가입/로그인)시 hash/verify하기 위함.
async def get_password_helper(user_manager=Depends(get_user_manager)):
    yield user_manager.password_helper


fastapi_users = FastAPIUsers[Users, int](
    get_user_manager,
    get_auth_backends(),
)


def get_auth_routers():
    routers = []

    for auth_backend in get_auth_backends():
        routers.append({
            "name": auth_backend.name,
            "router": fastapi_users.get_auth_router(auth_backend),
        })

    return routers


def get_register_router():
    return fastapi_users.get_register_router(user_schema=UserRead, user_create_schema=UserCreate)


def get_users_router():
    return fastapi_users.get_users_router(
        user_schema=UserRead,
        user_update_schema=UserUpdate
    )


def get_oauth_router():
    router = fastapi_users.get_oauth_router(
        oauth_client=google_oauth_client,
        backend=cookie_auth_backend,
        state_secret=JWT_SECRET,
        associate_by_email=True,
        # redirect_url=None,  # 자동으로 /callback router로 redirect 됨.
        # redirect_url=config.FRONTEND_URL + '', # 만약, front를 거쳐가는 경우, 직접 입력해야함.
    )
    return router


def get_cookie_oauth_routers():
    routers = []

    for oauth_client in get_oauth_clients():
        routers.append({
            "name": f'{oauth_client.name}/' + cookie_auth_backend.name ,
            "router": fastapi_users.get_oauth_router(
                oauth_client=oauth_client,
                backend=cookie_auth_backend,
                state_secret=JWT_SECRET,
                associate_by_email=True,
            )
        })

    return routers


def get_bearer_oauth_routers():
    routers = []

    for oauth_client in get_oauth_clients():
        ...

    return routers


active_user = fastapi_users.current_user(active=True)
