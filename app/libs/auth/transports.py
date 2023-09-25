from typing import Any, Optional, Literal
from fastapi import Request

from fastapi_users.authentication import CookieTransport
from starlette.responses import RedirectResponse
from starlette.requests import Request

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
        # cookie_httponly=False,  # js요청 금지
    )


# rediect되는 cookie transport
class CookieRedirectTransport(CookieTransport):
    ...

    async def get_login_response(self, token: str) -> Any:
        response = RedirectResponse(config.FRONTEND_URL, 302)
        self._set_login_cookie(response, token)
        return response

    async def get_login_response(self, token: str) -> Any:
        redirect_url = config.FRONTEND_URL

        response = await super().get_login_response(token)

        response.status_code = 302
        response.headers["Location"] = redirect_url

        return response


def get_cookie_redirect_transport():
    return CookieRedirectTransport(
        cookie_name='Authorization',
        cookie_max_age=USER_AUTH_MAX_AGE,
        # cookie_httponly=False,  # js요청 허용
        # cookie_secure=False, # local/test환경에서 http asyncClient요청 허용
    )
