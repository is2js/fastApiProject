import discord
from fastapi import APIRouter, Depends, HTTPException
from fastapi_users import BaseUserManager, models
from fastapi_users.exceptions import UserAlreadyExists
from fastapi_users.router import ErrorCode
from fastapi_users.router.oauth import generate_state_token
from starlette import status
from starlette.requests import Request

from app.common.config import DISCORD_CLIENT_ID, JWT_SECRET
from app.libs.auth.oauth_clients import get_oauth_client
from app.libs.auth.oauth_clients.discord import DiscordClient
from app.libs.auth.strategies import get_jwt_strategy
from app.libs.auth.transports import get_cookie_redirect_transport
from app.libs.discord.bot.ipc_client import discord_ipc_client
from app.pages.oauth_callback import get_discord_callback, DiscordAuthorizeCallback
from app.models import SnsType, RoleName, Permissions
from app.api.dependencies.auth import get_user_manager
from app.errors.exceptions import TokenExpiredException, OAuthProfileUpdateFailException
from app.pages.decorators import oauth_login_required, role_required, permission_required
from app.schemas.discord import GuildLeaveRequest
from app.utils.date_utils import D
from app.utils.http_utils import render, redirect, is_htmx, hx_vals_schema

# router = APIRouter(route_class=DiscordRoute)
router = APIRouter()


@router.get("/")
async def discord_home(request: Request):
    """
    `Discord Bot Dashboard Home`
    """

    return render(request, "dashboard/home.html")


@router.get("/guilds")
@oauth_login_required(SnsType.DISCORD)
@role_required(RoleName.ADMINISTRATOR)
# @permission_required(Permissions.ADMIN)
async def guilds(request: Request):
    access_token = request.state.user.get_oauth_access_token(SnsType.DISCORD)

    oauth_client: DiscordClient = get_oauth_client(SnsType.DISCORD)
    user_guilds = await oauth_client.get_guilds(access_token)

    guild_ids = await discord_ipc_client.request('guild_ids')
    # guild_ids.response >> {'guild_ids': [1156511536316174368]}
    guild_ids = guild_ids.response['guild_ids']

    # https://discord.com/developers/docs/resources/user#get-current-user-guilds
    for guild in user_guilds:
        # 해당user의 permission으로 guild 관리자인지 확인
        # (1) discord.Permissions( guild['permissions'] ).administrator   or  (2) guild['owner']
        is_admin: bool = discord.Permissions(guild['permissions']).administrator or guild.get('owner')
        if not is_admin:
            continue

        # (2) icon 간편주소를 img주소로 변경
        if guild.get('icon', None):
            guild['icon'] = 'https://cdn.discordapp.com/icons/' + guild['id'] + '/' + guild['icon']
        else:
            guild['icon'] = 'https://cdn.discordapp.com/embed/avatars/0.png'

        # (3) user의 guild id가 bot에 포함되면, use_bot 속성에 True, 아니면 False를 할당하자.
        # => user_guilds의 guild마다 id는 string으로 적혀있으니 int로 변환해서 확인한다. (서버반환은 guild_ids는 int)
        guild['use_bot'] = (int(guild['id']) if isinstance(guild['id'], str) else guild['id']) in guild_ids

        # (4) 개별guild 접속에 필요한 guild['id'] -> guild['url] 만들어서 넘겨주기
        guild['url'] = str(request.url_for('get_guild', guild_id=guild['id']))

    # bool을 key로 주면, False(0) -> True(1) 순으로 가므로, reverse까지 해줘야함
    user_guilds.sort(key=lambda x: x['use_bot'], reverse=True)

    context = {
        'user_guilds': user_guilds,
    }

    return render(
        request,
        "dashboard/guilds.html",
        context=context
    )


@router.get("/guilds/{guild_id}")
@oauth_login_required(SnsType.DISCORD)
async def get_guild(request: Request, guild_id: int):
    ...
    guild_stats = await discord_ipc_client.request('guild_stats', guild_id=guild_id)
    guild_stats = guild_stats.response  # 비었으면 빈 dict

    # user 관리 서버 중, bot에 없는 guild -> [bot 추가 url]을 만들어준다.
    if not guild_stats:
        return redirect(
            f'https://discord.com/oauth2/authorize?'
            f'&client_id={DISCORD_CLIENT_ID}'
            f'&scope=bot&permissions=8'
            f'&guild_id={guild_id}'
            f'&response_type=code'
            f'&redirect_uri={str(request.url_for("template_oauth_callback", sns_type=SnsType.DISCORD.value))}'
            f'&state={generate_state_token(dict(next=str(request.url)), JWT_SECRET)}'
        )

    return render(request, 'dashboard/guild-detail.html', context={**guild_stats})


@router.post("/guilds/delete")
@oauth_login_required(SnsType.DISCORD)
async def delete_guild(
        request: Request,
        # guild_id: int = Form(...),
        # body: GuildLeaveRequest, # 422 Entity error <- hx_vals를 pydantic이 route에서 바로 못받는다.
        # body = Body(...),
        # body >> b'guild_id=1161106117141725284&member_count=3'
        body=Depends(hx_vals_schema(GuildLeaveRequest)),
        is_htmx=Depends(is_htmx),
):
    # print(f"body >> {body}")
    # body >> guild_id=1161106117141725284
    # body >> guild_id=1161106117141725284 member_count=3

    # leave_guild = await discord_ipc_client.request('leave_guild', guild_id=guild_id)
    leave_guild = await discord_ipc_client.request('leave_guild', guild_id=body.guild_id)
    leave_guild = leave_guild.response

    # user 관리 서버 중, bot에 없는 guild -> [bot 추가 url]을 만들어준다.
    if not leave_guild['success']:
        raise

    # return redirect(request.url_for('guilds'))
    return redirect(request.url_for('guilds'), is_htmx=is_htmx)


# @app.route("/dashboard")
# async def dashboard():
# 	if not await discord.authorized:
# 		return redirect(url_for("login"))
#
# 	guild_count = await ipc_client.request("get_guild_count")
# 	guild_ids = await ipc_client.request("get_guild_ids")
#
# 	user_guilds = await discord.fetch_guilds()
#
# 	guilds = []
#
# 	for guild in user_guilds:
# 		if guild.permissions.administrator:
# 			guild.class_color = "green-border" if guild.id in guild_ids else "red-border"
# 			guilds.append(guild)
#
# 	guilds.sort(key = lambda x: x.class_color == "red-border")
# 	name = (await discord.fetch_user()).name
# 	return await render_template("dashb


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

    oauth_client = get_oauth_client(SnsType.DISCORD)
    account_id, account_email = await oauth_client.get_id_email(oauth2_token["access_token"])

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
        oauth_client = get_oauth_client(SnsType.DISCORD)
        if profile_info := await oauth_client.get_profile_info(oauth2_token["access_token"]):
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
