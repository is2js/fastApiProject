# from typing import Optional
# from fastapi import  Request
import uuid
from typing import Optional

from fastapi_users import IntegerIDMixin, BaseUserManager, models
from starlette.requests import Request
from starlette.responses import Response

from app.models import Users
from app.common.config import JWT_SECRET
from app.utils.date_utils import D


class UserManager(IntegerIDMixin, BaseUserManager[Users, int]):
    reset_password_token_secret = JWT_SECRET
    verification_token_secret = JWT_SECRET

    async def on_after_login(self, user: models.UP, request: Optional[Request] = None,
                             response: Optional[Response] = None) -> None:
        await self.user_db.update(
            user, {"last_seen": D.datetime()}
        )

    # async def on_after_register(self, user: Users, request: Optional[Request] = None):
    #     print(f"User {user.id} has registered.")
    #
    # async def on_after_forgot_password(
    #         self, user: Users, token: str, request: Optional[Request] = None
    # ):
    #     print(f"User {user.id} has forgot their password. Reset token: {token}")
    #
    # async def on_after_request_verify(
    #         self, user: Users, token: str, request: Optional[Request] = None
    # ):
    #     print(f"Verification requested for user {user.id}. Verification token: {token}")
