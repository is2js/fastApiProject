from datetime import datetime
from typing import List, Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends
from fastapi.params import Query
from fastapi_users import BaseUserManager, models
from fastapi_users.exceptions import UserAlreadyExists
from fastapi_users.router import ErrorCode
from fastapi_users.router.oauth import OAuth2AuthorizeResponse
from google.oauth2.credentials import Credentials
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.api.dependencies.auth import get_user_manager
from app.common.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from app.database.conn import db
from app.errors.exceptions import NoSupportException, TokenExpiredException, OAuthProfileUpdateFailException
from app.libs.auth.managers import UserManager
from app.libs.auth.oauth_clients import get_oauth_client
from app.libs.auth.strategies import get_jwt_strategy
from app.libs.auth.transports import get_cookie_redirect_transport
from app.pages.exceptions import TemplateException, OAuthDeniedException, GoogleCredentialsCreateException
from app.pages.oauth_callback import get_oauth_callback, OAuthAuthorizeCallback
from app.models import Users, SnsType
from app.utils.date_utils import D
from app.utils.http_utils import render

router = APIRouter()


@router.get("/")
async def index(request: Request, session: AsyncSession = Depends(db.session)):
    """
    `ELB 헬스 체크용`
    """

    return "ok"


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
        # state: Optional[str] = None, => get_oauth_callback()으로 생성된 콜백객체가 받아줌.
        sns_type: SnsType,
        # 인증서버가 돌아올떄 주는 code=와 state= + sns_type까지 callback객체 내부에서 받아 처리.
        # + 인증 취소 될땐, code= 까지 받아준다.
        access_token_and_next_url: OAuthAuthorizeCallback = Depends(
            get_oauth_callback(route_name='template_oauth_callback')
        ),
        user_manager: UserManager = Depends(get_user_manager),
):
    """
    `Discord callback for Developer OAuth Generated URL`
    """

    oauth2_token, next_url = access_token_and_next_url

    if oauth2_token.is_expired():
        raise TokenExpiredException()

    # 1) google - creds 생성 후 oauth_account 모델이 3필드 입력을  로그인 무관하게 단독처리
    # creds 생성여부를 결정
    required_scopes = request.session.pop('required_scopes', None)
    # 단독처리로서 router에서 creds 생성(True) VS 통합처리로서 usermanage.oauth_callback() 내부에서 creds 생성(False)
    for_sync = request.session.pop('for_sync', False)

    if for_sync:
        refresh_token = oauth2_token.get("refresh_token")
        if not (required_scopes and refresh_token):
            raise GoogleCredentialsCreateException(detail=f'credentials 생성에는 refresh_token, required_scopes가 모두 필요합니다.')

        creds = Credentials.from_authorized_user_info(
            info=dict(
                token=oauth2_token.get("access_token"),
                refresh_token=refresh_token,
                client_id=GOOGLE_CLIENT_ID,
                client_secret=GOOGLE_CLIENT_SECRET,
                scopes=required_scopes,
            )
        )

        oauth_account_dict = {
            "google_creds_json": creds.to_json(),
            "google_creds_expiry": creds.expiry,
            "google_creds_last_refreshed": D.datetime(),
        }
        user: Users = request.state.user

        user = await user_manager.user_db.update_oauth_account(user, user.get_oauth_account(sns_type),
                                                               oauth_account_dict)

    # 2) google - creds 생성 후 oauth_account 모델이 3필드 입력을 user, oauth_account와 통합처리
    else:
        oauth_client = get_oauth_client(sns_type)
        account_id, account_email = await oauth_client.get_id_email(oauth2_token["access_token"])

        try:
            user = await user_manager.oauth_callback(
                oauth_name=sns_type.value,
                access_token=oauth2_token.get("access_token"),
                account_id=account_id,
                account_email=account_email,
                expires_at=oauth2_token.get("expires_at"),
                refresh_token=oauth2_token.get("refresh_token"),
                request=request,
                associate_by_email=True,  # sns로그인시, 이미 email가입이 있어도, oauth_account로 등록을 허용한다.
                # is_verified_by_default=False,
                is_verified_by_default=True,  # sns로그인한 사람이라면 email인증을 안거쳐도 된다고 하자.
                required_scopes=required_scopes,  # sync 처리 scopes를 넣어줘서, 내부에 oauth_account에 creds관련 정보 추가 저장용
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
            if profile_info := await oauth_client.get_profile_info(oauth2_token["access_token"]):
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
        redirect_url=next_url  # 로그인 성공 후 cookie정보를 가지고 돌아갈 곳.
    )

    response = await cookie_redirect_transport.get_login_response(user_token_for_cookie)

    return response


@router.get("/errors/{status_code}")
async def errors(request: Request, status_code: int, message: Optional[str] = None):
    # 쿼리 파라미터로 오는 한글은 디코딩 해야함.
    message = unquote(message) if message else "관리자에게 문의해주세요."

    # if status_code == status.HTTP_403_FORBIDDEN:
    #     message = "권한이 없습니다."

    context = {
        "status_code": status_code,
        "message": message,
    }

    return render(request, 'dashboard/errors.html', context=context)
