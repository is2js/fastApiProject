from fastapi_users.authentication import AuthenticationBackend

from app.libs.auth.strategies import get_jwt_strategy
from app.libs.auth.transports import get_cookie_transport, get_cookie_redirect_transport

cookie_auth_backend = AuthenticationBackend(
    # name="jwt",
    name="cookie",
    transport=get_cookie_transport(),
    # transport=get_cookie_redirect_transport(),
    get_strategy=get_jwt_strategy,
)


def get_auth_backends():
    return [
        cookie_auth_backend,
    ]