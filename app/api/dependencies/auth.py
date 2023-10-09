from fastapi import Depends
from fastapi_users import FastAPIUsers

from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from httpx_oauth.clients.discord import DiscordOAuth2
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.clients.kakao import KakaoOAuth2
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.common.config import JWT_SECRET
from app.database.conn import db
from app.libs.auth.backends.oauth import get_google_backends, get_kakao_backends, get_discord_backends
from app.libs.auth.oauth_clients import get_oauth_clients
from app.models import Users, OAuthAccount
from app.schemas import UserRead, UserCreate, UserUpdate
from app.libs.auth.backends.base import get_auth_backends
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
    get_auth_backends(),  # oauth가 아닌 단순 /login, /logout  + /regitser router 생성용
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


def get_oauth_routers():
    routers = []

    for oauth_client in get_oauth_clients():
        if isinstance(oauth_client, GoogleOAuth2):
            for backend in get_google_backends():
                # oauth_client.name -> 'google' or ... (cusotm)
                # backend.name -> 'cookie' or 'bearer' (backend객체 생성시 약속)
                routers.append({
                    "name": f'{oauth_client.name}/' + backend.name,
                    "router": fastapi_users.get_oauth_router(
                        oauth_client=oauth_client,
                        backend=backend,
                        state_secret=JWT_SECRET,
                        associate_by_email=True,  # 이미 존재하는 email에 대해서 sns로그인시 oauth_account 정보 등록 허용(이미존재pass)
                        is_verified_by_default=True,  # 추가: sns 로그인시, email인증 안하고도 이메일인증(is_verified) True 설정
                    )
                })

        elif isinstance(oauth_client, KakaoOAuth2):
            for backend in get_kakao_backends():
                routers.append({
                    "name": f'{oauth_client.name}/' + backend.name,
                    "router": fastapi_users.get_oauth_router(
                        oauth_client=oauth_client,
                        backend=backend,
                        state_secret=JWT_SECRET,
                        associate_by_email=True,  # 이미 존재하는 email에 대해서 sns로그인시 oauth_account 정보 등록 허용(이미존재pass)
                        is_verified_by_default=True,  # 추가: sns 로그인시, email인증 안하고도 이메일인증(is_verified) True 설정
                    )
                })

        elif isinstance(oauth_client, DiscordOAuth2):
            for backend in get_discord_backends():
                routers.append({
                    "name": f'{oauth_client.name}/' + backend.name,
                    "router": fastapi_users.get_oauth_router(
                        oauth_client=oauth_client,
                        backend=backend,
                        state_secret=JWT_SECRET,
                        associate_by_email=True,  # 이미 존재하는 email에 대해서 sns로그인시 oauth_account 정보 등록 허용(이미존재pass)
                        is_verified_by_default=True,  # 추가: sns 로그인시, email인증 안하고도 이메일인증(is_verified) True 설정
                    )
                })

    return routers


current_active_user = fastapi_users.current_user(
    active=True,
)

optional_current_active_user = fastapi_users.current_user(
    active=True,
    optional=True,
)


# 템플릿용 인증안될 때, 템플릿 authorization_url 갔다오기
# async def discord_user(request: Request, user=Depends(optional_current_active_user)):
#     if not user:
#         authorization_url: str = await discord_client.get_authorization_url(
#             redirect_uri=str(request.url_for('discord_callback')),
#             state_data=dict(next=str(request.url))
#         )
#         from app import RedirectException
#         raise RedirectException(authorization_url)
#         # return RedirectResponse(authorization_url, status_code=302)
#     return user


##############
# Template용 # - base.html에서 매번 사용되어야하는
##############
async def request_with_fastapi_optional_user(request: Request, user=Depends(optional_current_active_user)) -> Request:
    request.state.user = user
    return request


# template + discord dashboard용
from app.libs.discord.bot.ipc_client import discord_ipc_client


async def request_with_fastapi_optional_user_and_bot_guild_count(
        request: Request, user=Depends(optional_current_active_user)
) -> Request:

    request.state.user = user

    server_response = await discord_ipc_client.request("guild_count")
    # <ServerResponse response=1 status=OK>
    request.state.bot_guild_count = server_response.response

    return request
