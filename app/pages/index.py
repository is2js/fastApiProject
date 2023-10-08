from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Path
from fastapi.params import Query
from fastapi_users import BaseUserManager, models
from fastapi_users.exceptions import UserAlreadyExists
from fastapi_users.router import ErrorCode
from fastapi_users.router.oauth import OAuth2AuthorizeResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse

from app.api.dependencies.auth import get_user_manager
from app.database.conn import db
from app.errors.exceptions import NoSupportException, TokenExpiredException, OAuthProfileUpdateFailException
from app.libs.auth.oauth_clients import get_discord_client, get_oauth_client
from app.libs.auth.strategies import get_jwt_strategy
from app.libs.auth.transports import get_cookie_redirect_transport
from app.libs.discord.pages.oauth_callback import get_oauth_callback, OAuthAuthorizeCallback
from app.libs.discord.pages.oauth_client import discord_client
from app.models import Users, SnsType
from app.utils.date_utils import D

router = APIRouter()


@router.get("/")
async def index(request: Request, session: AsyncSession = Depends(db.session)):
    """
    `ELB 헬스 체크용`
    """
    print(f"request.path_params['sns_type'] >> {request.path_params['sns_type']}")

    return "ok"
    # context = {
    #     'request': request,  # 필수
    # }
    # return templates.TemplateResponse(
    #     "index.html",
    #     context
    # )


@router.get("/test")
async def test(request: Request):
    try:
        user = await Users.create(email="abc@gmail.com", name='조재경', auto_commit=True)
        user.name = '2'
        await user.save(auto_commit=True)
    except Exception as e:
        from inspect import currentframe as frame

        request.state.inspect = frame()
        raise e

    current_time = datetime.utcnow()
    return Response(f"Notification API (UTC: {current_time.strftime('%Y.%m.%d %H:%M:%S')})")


@router.post("/auth/login/cookie/{sns_type}", status_code=200)
async def login_cookie_sns(sns_type: SnsType, request: Request):
    """
    `소셜 로그인 API`\n
    :param sns_type:
    :return:
    """

    if sns_type in SnsType:
        if sns_type == SnsType.EMAIL:
            # sns authorize(login) route는 get이라서, post에서 redirect 못넘김
            # return RedirectResponse(str(request.url_for(f'auth:{sns_type}.cookie.login')))
            return Response(
                status_code=status.HTTP_302_FOUND,
                headers={"Location": str(request.url_for(f'auth:{sns_type}.cookie.login'))}
            )
        # oauth:{oauth_client.name}.{backend.name}.authorize
        return Response(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": str(request.url_for(f'oauth:{sns_type}.cookie.authorize'))}
        )
    raise NoSupportException()


@router.get(
    "/auth/authorize/{sns_type}",
    name=f"template_oauth_authorize",
    response_model=OAuth2AuthorizeResponse,
)
async def template_oauth_authorize(
        request: Request,
        sns_type: SnsType,
        scopes: List[str] = Query(None),
        state: Optional[str] = None,
) -> OAuth2AuthorizeResponse:
    oauth_client = get_oauth_client(sns_type)

    authorization_url = await oauth_client.get_authorization_url(
        redirect_uri=str(request.url_for('template_oauth_callback', sns_type=sns_type.value)),
        state=state,
        scope=scopes,
    )

    return OAuth2AuthorizeResponse(authorization_url=authorization_url)


@router.get("/auth/callback/{sns_type}", name='template_oauth_callback')
async def template_oauth_callback(
        request: Request,
        # code: str,
        # state: Optional[str] = None,
        sns_type: SnsType,
        # sns_type: SnsType = Path(...),
        # 인증서버가 돌아올떄 주는 code와 state + sns_type까지 내부에서 받아 처리
        access_token_and_next_url: OAuthAuthorizeCallback = Depends(
            get_oauth_callback(route_name='template_oauth_callback')
        ),
        user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
):

    """
    `Discord callback for Developer OAuth Generated URL`
    """
    oauth2_token, next_url = access_token_and_next_url

    if oauth2_token.is_expired():
        raise TokenExpiredException()
    account_id, account_email = await discord_client.get_id_email(oauth2_token["access_token"])

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

    jwt_strategy = get_jwt_strategy()
    user_token_for_cookie = await jwt_strategy.write_token(user)
    cookie_redirect_transport = get_cookie_redirect_transport(
        # redirect_url=request.url_for('guilds')  # 로그인 성공 후 cookie정보를 가지고 돌아갈 곳.
        redirect_url=next_url  # 로그인 성공 후 cookie정보를 가지고 돌아갈 곳.
        # redirect_url=request.url_for('discord_dashboard')  # 로그인 성공 후 cookie정보를 가지고 돌아갈 곳.
    )
    response = await cookie_redirect_transport.get_login_response(user_token_for_cookie)

    return response
