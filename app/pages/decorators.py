from functools import wraps
from fastapi import Request
from fastapi_users.router.oauth import generate_state_token
from starlette.responses import RedirectResponse

from app.models import Users, RoleName
from app.common.config import JWT_SECRET
from app.errors.exceptions import NoSupportException
from app.libs.auth.oauth_clients import get_oauth_client
from app.models import SnsType
from app.models.enums import Permissions
from app.pages.exceptions import ForbiddenException


#####

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


def oauth_login_required(sns_type: SnsType):
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):

            state_data = dict(next=str(request.url))
            state = generate_state_token(state_data, JWT_SECRET) if state_data else None

            oauth_client = get_oauth_client(sns_type)

            # redirect_uri에 적을 callback route 만 달라진다.
            ## request.state.user가 차있는 로그인 상태라도, oauth_account에 discord 토큰이 없으면, oauth login required에 배반이다.
            user: Users = request.state.user
            if not user or not user.get_oauth_access_token(sns_type):
                if sns_type == SnsType.DISCORD:

                    authorization_url: str = await oauth_client.get_authorization_url(
                        redirect_uri=str(request.url_for('discord_callback')),
                        state=state
                    )

                    response = RedirectResponse(authorization_url)
                    return response

                else:
                    raise NoSupportException()
            else:
                return await func(request, *args, **kwargs)

        return wrapper

    return decorator


def permission_required(permission: Permissions):
    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user: Users = request.state.user

            if not user.has_permission(permission):
                # TODO: template error페이지
                # raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
                # raise ForbiddenException(status_code=status.HTTP_403_FORBIDDEN)
                raise ForbiddenException(detail=f'{permission.name}에 대한 권한이 없음.')
                # template_name = 'bot_dashboard/errors.html'
                # context = {"status_code": status.HTTP_403_FORBIDDEN}
                # return render(request, template_name, context=context)

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
                # TODO: template error 페이지
                # raise ForbiddenException(status_code=status.HTTP_403_FORBIDDEN)
                # raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

                raise ForbiddenException(
                    detail=f'{role_name.name}에 대한 권한이 없음.',
                )

                # template_name = 'bot_dashboard/errors.html'
                # context = {
                #     "status_code": status.HTTP_403_FORBIDDEN,
                #     "message": "권한이 없습니다."
                # }
                # return render(request, template_name, context=context)

            return await func(request, *args, **kwargs)
        return wrapper
    return decorator
