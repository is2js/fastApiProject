from typing import Any, Optional, Literal
from fastapi import Request

from fastapi_users.authentication import CookieTransport, BearerTransport
from starlette import status
from starlette.responses import RedirectResponse

from app.common.config import config
from app.common.consts import USER_AUTH_MAX_AGE


# cookie_transport = CookieTransport(
#     cookie_name='Authorization',
#     cookie_max_age=3600,
#     cookie_httponly=True
# )

def get_cookie_transport():
    return CookieTransport(
        cookie_name='Authorization',
        cookie_max_age=USER_AUTH_MAX_AGE,
        # cookie_httponly=True,  # js요청 금지(default)
        # cookie_secure=True, # localhost 등 http 요청 금지(default)
    )


def get_bearer_transport():
    return BearerTransport(
        # tokenUrl='auth/jwt/login'  # fastapi-users에서 기본backend만들 때, token을 발급해주는 라우터?
        tokenUrl='/api/v1/auth/bearer/login'  # 최종 bearer방식의 login router
    )


# rediect되는 cookie transport
class CookieRedirectTransport(CookieTransport):
    ...
    redirect_url: str

    def __init__(self, redirect_url, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redirect_url = redirect_url

    async def get_login_response(self, token: str) -> Any:
        response = await super().get_login_response(token)

        response.status_code = status.HTTP_302_FOUND

        # 생성시, request.url_for('라우트명')을 입력할 시, URL객체가 들어와 에러나므로 str() 필수
        response.headers["Location"] = str(self.redirect_url) if not isinstance(self.redirect_url, str) \
            else self.redirect_url

        return response


def get_cookie_redirect_transport(redirect_url):
    return CookieRedirectTransport(
        redirect_url,
        cookie_name='Authorization',
        cookie_max_age=USER_AUTH_MAX_AGE,
        #### local + test환경에서 필수로 False해야지, redirect 가능해진다.
        # cookie_httponly=False,  # js요청 허용
        # cookie_secure=False, # local/test환경에서 http asyncClient요청 허용
    )
