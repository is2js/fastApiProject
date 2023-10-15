from __future__ import annotations

import random
import string
from uuid import uuid4

from fastapi_users_db_sqlalchemy import (
    SQLAlchemyBaseUserTable,
    SQLAlchemyBaseOAuthAccountTable,
)
from sqlalchemy import Column, Enum, String, Boolean, Integer, ForeignKey, DateTime, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, Mapped

from app.common.consts import MAX_API_KEY_COUNT, MAX_API_WHITE_LIST_COUNT
from app.errors.exceptions import MaxAPIKeyCountException, MaxWhiteListCountException, NoKeyMatchException

from app.models.base import BaseModel
from app.models.enums import UserStatus, ApiKeyStatus, SnsType, Gender, RoleName, RolePermissions, Permissions


# class Users(BaseModel):
class Users(BaseModel, SQLAlchemyBaseUserTable[int]):
    status = Column(Enum(UserStatus), default=UserStatus.ACTIVE)
    # email = Column(String(length=255), nullable=True, unique=True)
    # pw = Column(String(length=2000), nullable=True)
    name = Column(String(length=255), nullable=True)
    phone_number = Column(String(length=20), nullable=True, unique=True)
    profile_img = Column(String(length=1000), nullable=True)
    # sns_type = Column(Enum("FB", "G", "K"), nullable=True,)
    sns_type = Column(Enum(SnsType), nullable=True, )
    marketing_agree = Column(Boolean, nullable=True, default=True)

    sns_token = Column(String(length=64), nullable=True, unique=True)
    nickname = Column(String(length=30), nullable=True)
    gender = Column(Enum(Gender), nullable=True)

    # age = Column(Integer, nullable=True, default=0)
    # birthday = Column(String(length=20), nullable=True)
    # kakao age_range(연령대)
    # 1~9: 1세 이상 10세 미만
    # 10~14: 10세 이상 15세 미만
    # 15~19: 15세 이상 20세 미만
    # 20~29: 20세 이상 30세 미만
    # 80~89: 80세 이상 90세 미만
    # 90~: 90세 이상
    age_range = Column(String(length=5), nullable=True)  # 카카오 형식인데, 구글 등에서 변환하길.
    birthyear = Column(String(length=4), nullable=True)  # kakao는 '출생연도'가 비즈니스 아니면 동의화면 권한없음. 구글에서는 'year'로 바로 들어옴
    birthday = Column(String(length=4), nullable=True)  # 1218. 구글에서는 'month', 'day'를 합해서 넣기

    # last_seen = Column(DateTime, server_default=func.now(), nullable=True)
    # => db서버의 시간대(KST)로 들어가버림.
    last_seen = Column(DateTime, default=func.utc_timestamp(), nullable=True)

    oauth_accounts = relationship(
        "OAuthAccount", lazy="joined",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    api_keys = relationship("ApiKeys", back_populates="user",
                            cascade="all, delete-orphan",
                            lazy=True  # 'select'로서 자동load아님. fastapi-users에서는 내부 join후 처리함.
                            )

    # 1. many에 fk를 CASCADE or 안주고 달아준다.
    # role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)

    # 2. many.one 을 단수로 쓰기 위해 uselist=false로 relation을 생성한다.
    # 3. lazy 전략 선택
    # => 추가쿼리를 날리기위한 Query객체 반환 dynamic(안씀) VS eagerload용 default 'select' VS 자동load용 'subquery', 'selectin', 'joined'
    # => 자동load시 대상이 1) many-> 'joined', 2) one -> 'subquery' or 'selectin' 선택
    role = relationship("Roles",  # back_populates="user",
                        foreign_keys=[role_id],
                        uselist=False,
                        lazy='subquery',  # lazy: _LazyLoadArgumentType = "select",
                        )

    def get_oauth_access_token(self, sns_type: SnsType):
        """
        lazy="joined"되어 session 없이, oauth_accounts 모델에서 특정 oauth의 access_token을 얻는 메서드
        """
        for existing_oauth_account in self.oauth_accounts:
            if existing_oauth_account.oauth_name == sns_type.value:
                return existing_oauth_account.access_token

        return None

    @hybrid_property
    def role_name(self) -> RoleName:
        """
        lazy='subquery' 되어 자동 load되는 Roles객체의 name(Enum-RoleName)을 바로 조회하여
        -> User Response Schema (UserRead)에 Roles-name필드 type(RoleName)으로 정의할 수 있게 된다.
        """
        return self.role.name

    def has_permission(self, permission: Permissions) -> bool:
        """
        lazy='subquery' 되어 자동 load되는 Roles객체의 total_permission 합을 조회하여, 단독 Permission과 int비교
        @permission_required( ) 에서 사용될 예정.
        """
        #  9 > Permissions.CLEAN # True # int Enum은 int와 비교 가능하다.(자동 value로 비교)
        return self.role.permission >= permission

    def has_role(self, role_name: RoleName) -> bool:
        """
        lazy='subquery' 되어 자동 load되는 Roles객체의 permission을 조회하여,
        @role_required( ) 에서 사용될 예정.
        """
        return self.has_permission(role_name.max_permission)


class OAuthAccount(BaseModel, SQLAlchemyBaseOAuthAccountTable[int]):
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user = relationship("Users", back_populates="oauth_accounts",
                        foreign_keys=[user_id],
                        uselist=False,
                        )


class Roles(BaseModel):
    name = Column(Enum(RoleName), default=RoleName.USER, unique=True, index=True)
    default = Column(Boolean, default=False, index=True)
    permission = Column(Integer, default=0)

    @classmethod
    async def insert_roles(cls, session: AsyncSession = None):
        """
        app 구동시, 미리 DB 삽입 하는 메서드
        """
        for role_name in RoleName:

            if await cls.filter_by(name=role_name).exists():
                continue

            await cls.create(
                session=session,
                auto_commit=True,
                name=role_name,
                permission=role_name.total_permission,
                default=(role_name == RoleName.USER)
            )

    def has_permission(self, permission):
        # self.perm == perm의 확인은, (중복int를 가지는 Perm도 생성가능하다고 생각할 수 있다)
        return self.permission >= permission

    # def _add_permission(self, total_permission):
    #     # 6) 해당 perm(같은int)을 안가지고 잇을때만 추가한다다
    #     if not self.has_role(total_permission):
    #         print(f"total_permission >> {total_permission}")
    #
    #         self.total_permission += total_permission


class ApiKeys(BaseModel):
    created_at = Column(DateTime, nullable=False, default=func.utc_timestamp())
    updated_at = Column(DateTime, nullable=False, default=func.utc_timestamp(), onupdate=func.utc_timestamp())

    access_key = Column(String(length=64), nullable=False, index=True)
    secret_key = Column(String(length=64), nullable=False)
    user_memo = Column(String(length=40), nullable=True)
    status = Column(Enum(ApiKeyStatus), default=ApiKeyStatus.ACTIVE)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user = relationship("Users", back_populates="api_keys",
                        foreign_keys=[user_id],
                        uselist=False,
                        )

    is_whitelisted = Column(Boolean, default=False)
    whitelists = relationship("ApiWhiteLists", back_populates="api_key",
                              cascade="all, delete-orphan"
                              )

    @classmethod
    async def check_max_count(cls, user, session=None):
        user_api_key_count = await cls.filter_by(session=session, user_id=user.id, status='active').count()
        if user_api_key_count >= MAX_API_KEY_COUNT:
            raise MaxAPIKeyCountException()

    @classmethod
    async def create(cls, session=None, user=None, **kwargs):
        # secret_key(랜덤40글자) 생성 by alnums + random
        alnums = string.ascii_letters + string.digits
        secret_key = ''.join(random.choices(alnums, k=40))

        # access_key( uuid4 끝 12개 + uuid4 전체)
        access_key = None
        while not access_key:
            access_key_candidate = f"{str(uuid4())[:-12]}{str(uuid4())}"
            exists_api_key = await cls.filter_by(session=session, access_key=access_key_candidate).exists()
            if not exists_api_key:
                access_key = access_key_candidate

        new_api_key = await super().create(session=session, auto_commit=True,
                                           user_id=user.id,
                                           secret_key=secret_key,
                                           access_key=access_key,
                                           **kwargs)
        return new_api_key

    @classmethod
    async def check_key_owner(cls, id_, user, session=None):
        """
        하위도메인 Apikey가 상위도메인 user에 속해있는지 확인
        -> 하위도메인에서 상위도메인의 fk를 이용해서 필터링해서 조회하여 있으면 해당됨.
        """
        exists_user_api_key = await cls.filter_by(session=session, id=id_, user_id=user.id).exists()
        if not exists_user_api_key:
            raise NoKeyMatchException()


class ApiWhiteLists(BaseModel):
    ip_address = Column(String(length=64), nullable=False)

    api_key_id = Column(Integer, ForeignKey("apikeys.id", ondelete="CASCADE"), nullable=False)
    api_key = relationship("ApiKeys", back_populates="whitelists",
                           foreign_keys=[api_key_id],
                           uselist=False,
                           )

    @classmethod
    async def check_max_count(cls, api_key_id, session=None):
        user_api_key_count = await cls.filter_by(session=session, api_key_id=api_key_id).count()
        if user_api_key_count >= MAX_API_WHITE_LIST_COUNT:
            raise MaxWhiteListCountException()
