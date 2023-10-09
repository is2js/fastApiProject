from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi_users import BaseUserManager, models
from fastapi_users.exceptions import UserAlreadyExists
from fastapi_users.router import ErrorCode
from starlette import status
from starlette.requests import Request

from app.libs.discord.pages.route import DiscordRoute
from app.libs.auth.strategies import get_jwt_strategy
from app.libs.auth.transports import get_cookie_redirect_transport
from app.libs.discord.pages.oauth_callback import get_discord_callback, DiscordAuthorizeCallback
from app.models import Users
from app.api.dependencies.auth import get_user_manager, optional_current_active_user, request_with_fastapi_optional_user
from app.common.config import DISCORD_GENERATED_AUTHORIZATION_URL
from app.errors.exceptions import TokenExpiredException, OAuthProfileUpdateFailException
from app.libs.discord.bot.ipc_client import discord_ipc_client
from app.libs.discord.pages.oauth_client import discord_client
from app.pages import templates
from app.utils.auth_utils import update_query_string
from app.utils.date_utils import D
from app.utils.http_utils import render

router = APIRouter(route_class=DiscordRoute)


# async def discord_home(request: Request, user: Users = Depends(optional_current_active_user)):
@router.get("/")
async def discord_home(request: Request):
    """
    `Discord Bot Dashboard Home`
    """
    # request.state.user >> <Users#4>
    # request.state.bot_guild_count >> 1

    # return templates.TemplateResponse(
    #     "bot_dashboard/home.html",
    #     context
    # )
    #
    return render(request, "bot_dashboard/home.html")


@router.get("/callback", name='discord_callback')
async def discord_callback(
        request: Request,
        # code: str,
        # state: Optional[str] = None,
        access_token_and_next_url: DiscordAuthorizeCallback = Depends(
            get_discord_callback(route_name='discord_callback')
        ),  # 인증서버가 돌아올떄 주는 code와 state를 내부에서 받아 처리
        user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
):
    """
    `Discord callback for Developer OAuth Generated URL`
    """
    oauth2_token, next_url = access_token_and_next_url

    # 2. 응답받은 oauth2_token객체로 만료를 확인하고
    if oauth2_token.is_expired():
        raise TokenExpiredException()

    account_id, account_email = await discord_client.get_id_email(oauth2_token["access_token"])

    # 4-1. fastapi-users callback route 로직
    # - venv/Lib/site-packages/fastapi_users/router/oauth.py
    try:
        user = await user_manager.oauth_callback(
            oauth_name='discord',
            access_token=oauth2_token.get("access_token"),
            account_id=account_id,
            account_email=account_email,
            expires_at=oauth2_token.get("expires_at"),
            refresh_token=oauth2_token.get("refresh_token"),
            request=request,
            associate_by_email=True,  # sns로그인시, 이미 email가입이 있어도, oauth_account로 등록을 허용한다.
            # is_verified_by_default=False,
            is_verified_by_default=True,  # sns로그인한 사람이라면 email인증을 안거쳐도 된다고 하자.
        )

    except UserAlreadyExists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorCode.OAUTH_USER_ALREADY_EXISTS,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorCode.LOGIN_BAD_CREDENTIALS,
        )

    # 4-3. backend에서 oauth_client에서 못가져온 추가정보 가져오는 로직도 추가한다.
    # - app/libs/auth/backends/oauth/discord.py
    try:
        if profile_info := await discord_client.get_profile_info(oauth2_token["access_token"]):
            await user.update(
                auto_commit=True,
                **profile_info,
                sns_type='discord',
                last_seen=D.datetime(),  # on_after_login에 정의된 로직도 가져옴
            )
    except Exception as e:
        raise OAuthProfileUpdateFailException(obj=user, exception=e)

    # 5. 쿠키용 user_token을 jwt encoding하지않고, fastapi-users의 Strategy객체로 encoding하기
    # token_data = UserToken.model_validate(user).model_dump(exclude={'hashed_password', 'marketing_agree'})
    # token = await create_access_token(data=token_data)
    jwt_strategy = get_jwt_strategy()
    user_token_for_cookie = await jwt_strategy.write_token(user)
    # {
    #   "sub": "4",
    #   "aud": [
    #     "fastapi-users:auth"
    #   ],
    #   "exp": 1696397563
    # }

    # 6. 직접 Redirect Response를 만들지 않고, fastapi-users의 쿠키용 Response제조를 위한 Cookie Transport를 Cusotm해서 Response를 만든다.
    # 3. 데이터를 뿌려주는 api router로 Redirect시킨다.
    # return RedirectResponse(url='/guilds')
    # try:
    #     decode_jwt(state, JWT_SECRET, [STATE_TOKEN_AUDIENCE])
    #     next_url = decode_jwt(state, JWT_SECRET, [STATE_TOKEN_AUDIENCE])['next'] if state \
    #         else str(request.url_for('discord_dashboard'))
    # except jwt.DecodeError:
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    cookie_redirect_transport = get_cookie_redirect_transport(
        # redirect_url=request.url_for('guilds')  # 로그인 성공 후 cookie정보를 가지고 돌아갈 곳.
        redirect_url=next_url  # 로그인 성공 후 cookie정보를 가지고 돌아갈 곳.
        # redirect_url=request.url_for('discord_dashboard')  # 로그인 성공 후 cookie정보를 가지고 돌아갈 곳.
    )
    response = await cookie_redirect_transport.get_login_response(user_token_for_cookie)

    return response


@router.get("/guilds")
async def guilds(request: Request, user: Users = Depends(optional_current_active_user)):
    # async def guilds(request: Request, user: Users = Depends(current_active_user)):
    # async def guilds(request: Request, user: Users = Depends(discord_user)):
    # if not user:
    #     authorization_url = await discord_client.get_authorization_url(
    #         redirect_uri=str(request.url_for('discord_callback')),
    #         state_data=dict(next=str(request.url)),
    #     )
    #     return RedirectResponse(authorization_url, status_code=302)

    user_guilds: list = []
    if user:
        access_token = user.get_oauth_access_token('discord')
        user_guilds = await discord_client.get_guilds(access_token)
        # middel웨어없이 bot ipc통신이라 data 형식이 아니게 됨.
        # user_guilds  >> [{'id': '1156511536316174368', 'name': '한의원 인증앱', 'icon': None, 'owner': True, 'permissions': 2147483647, 'permissions_new': '562949953421311', 'features': []}]

    bot_guild_count = await discord_ipc_client.request("guild_count")

    #     "data":{
    #         "guilds":[
    #             {
    #                 "id":"1156511536316174368",
    #                 "name":"한의원 인증앱",
    #                 "icon":null,
    #                 "owner":true,
    #                 "permissions":xxx,
    #                 "permissions_new":"xxxx",
    #                 "features":[
    #                 ]
    #             }
    #         ]
    #     },
    #     "version":"1.0.0"
    # }
    # return dict(guilds=guilds)
    context = {
        'request': request,
        'user': user,
        'bot_guild_count': bot_guild_count.response,  # 커스텀 데이터

        'authorize_url': update_query_string(
            DISCORD_GENERATED_AUTHORIZATION_URL,
            # redirect_uri=config.DOMAIN + '/discord/callback'
            redirect_uri=request.url_for('discord_callback')
        ),

        'user_guilds': user_guilds,
    }
    return templates.TemplateResponse(
        "bot_dashboard/guilds.html",
        context
    )
