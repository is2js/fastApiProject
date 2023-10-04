from fastapi import APIRouter, Depends, HTTPException
from fastapi_users import BaseUserManager, models
from fastapi_users.exceptions import UserAlreadyExists
from fastapi_users.router import ErrorCode
from httpx_oauth.oauth2 import OAuth2Token
from starlette import status
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.common.consts import USER_AUTH_MAX_AGE
from app.libs.auth.strategies import get_jwt_strategy
from app.libs.auth.transports import get_cookie_transport, get_cookie_redirect_transport
from app.models import Users
from app.api.dependencies.auth import get_user_manager, current_active_user, optional_current_active_user
from app.common.config import config, DISCORD_AUTHORIZE_URL
from app.errors.exceptions import TokenExpiredException, OAuthProfileUpdateFailException, NotAuthorized
from app.libs.discord.ipc_client import discord_ipc_client
from app.libs.discord.oauth_client import discord_client
from app.pages import templates
from app.schemas import UserToken
from app.utils.auth_utils import update_query_string, create_access_token
from app.utils.date_utils import D

router = APIRouter()

authorize_url = "https://discord.com/api/oauth2/authorize?client_id=1156507222906503218&" \
                "redirect_uri=http%3A%2F%2Flocalhost%3A8001%2Fdiscord%2Fcallback" \
                "&response_type=code&scope=identify%20guilds"


@router.get("/dashboard")
async def discord_dashboard(request: Request):
    """
    `Discord Bot Dashboard`
    """
    # bot에 연결된 @server.route에 요청
    guild_count = await discord_ipc_client.request("guild_count")

    context = {
        'request': request,  # 필수
        'count': guild_count.response,  # 커스텀 데이터
        'authorize_url': update_query_string(
            DISCORD_AUTHORIZE_URL,
            # redirect_uri=config.DOMAIN + '/discord/callback'
            redirect_uri=request.url_for('discord_callback')
        ),
    }
    return templates.TemplateResponse(
        "discord_dashboard.html",
        context
    )


@router.get("/callback", name='discord_callback')
async def discord_callback(
        request: Request,
        code: str,
        user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
):
    """
    `Discord callback for Developer OAuth Generated URL`
    """

    # 1. 받은 code 및 redirect_url로 OAuth2Token (dict wrapping 객체)을 응답받는다.
    oauth2_token: OAuth2Token = await discord_client.get_access_token(
        code=code,
        redirect_uri=request.url_for('discord_callback'),  # 콜백라우터지만, access_token요청시 자신의 url을 한번 더 보내줘야한다.
    )

    # 2. 응답받은 oauth2_token객체로 만료를 확인하고
    if oauth2_token.is_expired():
        raise TokenExpiredException()
    # {
    # 'token_type': 'Bearer',
    # 'access_token': 'zv9SHN0TGA5lwxxx',
    # 'expires_in': 604800,
    # 'refresh_token': 'p8XpO6fCAykjxxxx',
    # 'scope': 'identify guilds email', '
    # expires_at': 1696919521
    # }

    # 4. 받은 token으로 1) profile_info -> 2) user DB -> oauth_account DB 등록
    # venv/Lib/site-packages/httpx_oauth/clients/discord.py

    # 4-2. httx_oauth의 각 oauth client에서 공통으로 사용하는 메서드
    # - venv/Lib/site-packages/httpx_oauth/clients/discord.py
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
            associate_by_email=True,
            is_verified_by_default=False,
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
                last_seen=D.datetime(), # on_after_login에 정의된 로직도 가져옴
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
    cookie_redirect_transport = get_cookie_redirect_transport(
        redirect_url=request.url_for('guilds')  # 로그인 성공 후 cookie정보를 가지고 돌아갈 곳.
    )
    response = await cookie_redirect_transport.get_login_response(user_token_for_cookie)

    return response


@router.get("/guilds")
async def guilds(request: Request, user: Users = Depends(current_active_user)):
    # token = request.cookies.get("Authorization")
    # if not token:
    #     raise NotAuthorized()

    # discord_access_token = ''
    # for existing_oauth_account in user.oauth_accounts:
    #     if existing_oauth_account.oauth_name == 'discord':
    #         discord_access_token = existing_oauth_account.access_token

    access_token = user.get_oauth_access_token('discord')

    guilds = await discord_client.get_guilds(access_token)

    # {
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
    return dict(guilds=guilds)
