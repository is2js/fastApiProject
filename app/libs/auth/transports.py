from fastapi_users.authentication import CookieTransport

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
        # cookie_httponly=True,  # js요청 금지
    )
