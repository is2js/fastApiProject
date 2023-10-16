# from typing import Optional
# from fastapi import  Request
import uuid
from typing import Optional, Generic

from fastapi_users import IntegerIDMixin, BaseUserManager, models, schemas, exceptions
from fastapi_users.db import BaseUserDatabase
from fastapi_users.password import PasswordHelperProtocol
from starlette.requests import Request
from starlette.responses import Response

from app.models import Users, Roles, RoleName
from app.common.config import JWT_SECRET, config
from app.utils.date_utils import D


class UserManager(IntegerIDMixin, BaseUserManager[Users, int]):
    reset_password_token_secret = JWT_SECRET
    verification_token_secret = JWT_SECRET

    def __init__(self, user_db: BaseUserDatabase[models.UP, models.ID],
                 password_helper: Optional[PasswordHelperProtocol] = None):
        super().__init__(user_db, password_helper)

    async def create(self, user_create: schemas.UC, safe: bool = False, request: Optional[Request] = None) -> models.UP:
        """
        Users 생성시, role 추가를 위해 재정의(user_dict)
        """
        # return await super().create(user_create, safe, request)
        await self.validate_password(user_create.password, user_create)

        existing_user = await self.user_db.get_by_email(user_create.email)
        if existing_user is not None:
            raise exceptions.UserAlreadyExists()

        user_dict = (
            user_create.create_update_dict()
            if safe
            else user_create.create_update_dict_superuser()
        )
        password = user_dict.pop("password")
        user_dict["hashed_password"] = self.password_helper.hash(password)

        #### 가입시 추가필드 입력 ####

        if user_dict['email'] == config.ADMIN_EMAIL:
            # 관리자 메일과 동일하면, 관리자 Role로 등록
            user_dict["role"] = await Roles.filter_by(name=RoleName.ADMINISTRATOR).first()
        else:
            role_name: RoleName = user_dict.pop("role_name", None)
            if not role_name:
                user_dict["role"] = await Roles.filter_by(default=True).first()
            else:
                user_dict["role"] = await Roles.filter_by(name=role_name).first()
        ############################

        created_user = await self.user_db.create(user_dict)

        await self.on_after_register(created_user, request)

        return created_user

    async def oauth_callback(self: "BaseUserManager[models.UOAP, models.ID]", oauth_name: str, access_token: str,
                             account_id: str, account_email: str, expires_at: Optional[int] = None,
                             refresh_token: Optional[str] = None, request: Optional[Request] = None, *,
                             associate_by_email: bool = False, is_verified_by_default: bool = False) -> models.UOAP:
        """
        Users 생성시, role 추가를 위해 재정의(user_dict)
        """
        oauth_account_dict = {
            "oauth_name": oauth_name,
            "access_token": access_token,
            "account_id": account_id,
            "account_email": account_email,
            "expires_at": expires_at,
            "refresh_token": refresh_token,
        }

        try:
            user = await self.get_by_oauth_account(oauth_name, account_id)
        except exceptions.UserNotExists:
            try:
                # Associate account
                user = await self.get_by_email(account_email)
                if not associate_by_email:
                    raise exceptions.UserAlreadyExists()
                user = await self.user_db.add_oauth_account(user, oauth_account_dict)
            except exceptions.UserNotExists:
                # Create account
                password = self.password_helper.generate()

                user_dict = {
                    "email": account_email,
                    "hashed_password": self.password_helper.hash(password),
                    "is_verified": is_verified_by_default,
                }

                #### 추가 필드 처리 ####
                # 관리자 메일과 동일하면, 관리자 Role로 등록
                if user_dict['email'] == config.ADMIN_EMAIL:
                    user_dict["role"] = await Roles.filter_by(name=RoleName.ADMINISTRATOR).first()

                # 아니라면, oauth로그인으로 인한 가입은 기본 Roles("user") 배정
                else:
                    user_dict["role"] = await Roles.filter_by(default=True).first()
                ######################

                user = await self.user_db.create(user_dict)
                user = await self.user_db.add_oauth_account(user, oauth_account_dict)
                await self.on_after_register(user, request)
        else:
            # Update oauth
            for existing_oauth_account in user.oauth_accounts:
                if (
                        existing_oauth_account.account_id == account_id
                        and existing_oauth_account.oauth_name == oauth_name
                ):
                    user = await self.user_db.update_oauth_account(
                        user, existing_oauth_account, oauth_account_dict
                    )

        return user

    async def update(self, user_update: schemas.UU, user: models.UP, safe: bool = False,
                     request: Optional[Request] = None) -> models.UP:
        # return await super().update(user_update, user, safe, request)
        if safe:
            updated_user_data = user_update.create_update_dict()
        else:
            updated_user_data = user_update.create_update_dict_superuser()

        #### 추가 필드 처리 ####
        role_name: RoleName = updated_user_data.pop("role_name", None)

        if role_name:
            updated_user_data["role"] = await Roles.filter_by(name=role_name).first()
        ########################

        updated_user = await self._update(user, updated_user_data)

        await self.on_after_update(updated_user, updated_user_data, request)
        return updated_user

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
