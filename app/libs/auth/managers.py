# from typing import Optional
# from fastapi import  Request

from fastapi_users import IntegerIDMixin, BaseUserManager

from app.models import Users
from app.common.config import JWT_SECRET


class UserManager(IntegerIDMixin, BaseUserManager[Users, int]):
    reset_password_token_secret = JWT_SECRET
    verification_token_secret = JWT_SECRET

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

