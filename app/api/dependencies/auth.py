from fastapi import Depends
from fastapi_users import FastAPIUsers

from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.conn import db
from app.models import Users
from app.schemas import UserRead, UserCreate
from app.libs.auth.backends import get_auth_backends
from app.libs.auth.managers import UserManager


async def get_user_db(session: AsyncSession = Depends(db.session)):
    yield SQLAlchemyUserDatabase(session=session, user_table=Users)


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
    return fastapi_users.get_register_router(
        user_schema=UserRead,
        user_create_schema=UserCreate
    )


# bearer_transport = BearerTransport(tokenUrl="/login")
#
# auth_backend = AuthenticationBackend(
#     name="jwt",
#     transport=bearer_transport,
#     get_strategy=get_jwt_strategy,
# )
#


active_user = fastapi_users.current_user(active=True)
