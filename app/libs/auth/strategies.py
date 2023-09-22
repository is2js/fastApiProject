from fastapi_users.authentication import JWTStrategy

from app.common.consts import USER_AUTH_MAX_AGE, JWT_ALGORITHM
from app.common.config import JWT_SECRET


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=JWT_SECRET, algorithm=JWT_ALGORITHM, lifetime_seconds=USER_AUTH_MAX_AGE)
