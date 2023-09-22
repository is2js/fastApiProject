from fastapi_users.authentication import JWTStrategy

from app.common.consts import USER_AUTH_MAX_AGE
from app.common.config import JWT_SECRET


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=JWT_SECRET, lifetime_seconds=USER_AUTH_MAX_AGE)
