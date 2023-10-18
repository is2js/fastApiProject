from functools import wraps
from typing import Optional, List

from fastapi import Request
from fastapi_users.router.oauth import generate_state_token
from starlette.responses import RedirectResponse

from app.models import Users, RoleName
from app.common.config import JWT_SECRET
from app.libs.auth.oauth_clients import get_oauth_client
from app.models import SnsType
from app.models.enums import Permissions
from app.pages.exceptions import ForbiddenException



# fastapi에서는 wrapperㄹㄹ async로, func반환을 await로 중간에 해줘야한다.
def login_required(func):
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        if not request.state.user:
            # TODO: login 페이지 GET route가 생기면 그것으로 redirect
            response = RedirectResponse(f"{request.url_for('discord_home')}?next={request.url}")
            return response

        return await func(request, *args, **kwargs)

    return wrapper


def oauth_login_required(sns_type: SnsType, required_scopes: Optional[List[str]] = None):
    """
    required_scopes가 들어올 때, google요청시 refresh_token을 획득하고, authorization_url의 범위를 넓혀줄 required_scopes 추가
    + session을 이용하여 콜백라우터에서 추가scopes 단독처리 / 로그인 + 추가scopes 통합처리를 나눔.
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user: Users = request.state.user

            # 1. 통과 조건
            if user and user.get_oauth_access_token(sns_type):
                # required_scopes 없거나 있더라도 google이면서 그에 대한 creds + scopes를 가진 경우 통과
                if not required_scopes or (
                        sns_type == SnsType.GOOGLE and await user.has_google_creds_and_scopes(required_scopes)
                ):
                    return await func(request, *args, **kwargs)

            # 2. 로그인 안됬거나 구글계정 없어서, base_scopes로 로그인 url을 만들기 위해, 현재 url -> state + oauth_client 준비까지 해야하는데
            state_data = dict(next=str(request.url))
            state = generate_state_token(state_data, JWT_SECRET) if state_data else None
            oauth_client = get_oauth_client(sns_type)

            authorization_url_kwargs: dict = dict(
                redirect_uri=str(request.url_for('template_oauth_callback', sns_type=sns_type.value)),
                state=state
            )

            # 3. 통과못했다면, required_scopes가 없는 경우는 그냥 로그인 하면 된다.
            if not required_scopes:
                authorization_url: str = await oauth_client.get_authorization_url(**authorization_url_kwargs)
                return RedirectResponse(authorization_url)

            # (required_scopes가 있는 경우)
            # 4. required_scopes가 있는 경우에는, sns_type(구글 VS 비구글)에 따라 다르다.
            # 4-1) 구글에서 required_scope가 온 경우에는,
            #     4-1-1-1) 로그인 X or 계정정보 X -> 일단 [소셜로그인 + requires_scopes]가 [통합처리]되어야한다 -> 콜백라우터가 받을 [session에 for_sync =False]
            #     4-1-1-2) 로그인 & 계정정보 모두 있을 때만, [session for_sync = True] -> 콜백라우터가 소셜로그인없이 [required_scopes에 대해서만 sync 처리]한다.
            #      => 이에 따라, authorization_url의 scopes는   통합처리시에는 base_scopes+ required_scopes  /   sync처리시 requires_scopes만 주어져야한다.
            if sns_type == SnsType.GOOGLE:
                if user and user.get_oauth_account(SnsType.GOOGLE):
                    request.session['for_sync'] = True
                    authorization_url_kwargs.update({'scope': required_scopes})
                else:
                    request.session['for_sync'] = False
                    authorization_url_kwargs.update({'scope': oauth_client.base_scopes + required_scopes})

                # 4-1-2) 또한, requires_scope가 주어지면, 통합처리든 단일처리든, [콜백라우터에서 creds생성]을 위해 -> session에 'required_scopes'를 전달하여, creds생성시 scopes=required_scopes를 넣어줘야한다.
                request.session['required_scopes'] = required_scopes

                # 4-1-3) 또한, requires_scope가 주어지면, 통합처리든 단일처리든, [creds생성을 위한 refresh_token]을 받으려면 -> authorization_url 생성시 파라미터를 추가 신호인 for_sync=True를 인자로 줘야 동의화면 띄우고 전달한다.
                authorization_url_kwargs.update({'for_sync': True})

            # 4-2) 구글이 아닌 경우, requires_scopes가 주어졌따면, scopes를 추가해서 요청만 하면 된다.
            #     -> 단독처리 X -> session['for_sync'] X
            #     -> creds 생성X : session['required_scopes'] X
            #     -> refresh toekn 생성X: for_sync=True 신호 X
            else:
                authorization_url_kwargs.update({'scope': oauth_client.base_scopes + required_scopes})

            authorization_url: str = await oauth_client.get_authorization_url(**authorization_url_kwargs)

            return RedirectResponse(authorization_url)

        return wrapper

    return decorator


def permission_required(permission: Permissions):
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user: Users = request.state.user

            if not user.has_permission(permission):
                raise ForbiddenException(
                    message=f'{permission.name}에 대한 권한이 없음.',
                    detail=f'{permission.name}에 대한 권한이 없음.'
                )

            return await func(request, *args, **kwargs)

        return wrapper

    return decorator


def role_required(role_name: RoleName):
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user: Users = request.state.user

            # 내부에서 user.has_permission을 이용
            if not user.has_role(role_name):
                raise ForbiddenException(
                    message=f'{role_name.name}에 대한 권한이 없음.',
                    detail=f'{role_name.name}에 대한 권한이 없음.',
                )

            return await func(request, *args, **kwargs)

        return wrapper

    return decorator
