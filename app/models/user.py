from __future__ import annotations

import random
import string
from typing import List
from uuid import uuid4

from fastapi_users_db_sqlalchemy import (
    SQLAlchemyBaseUserTable,
    SQLAlchemyBaseOAuthAccountTable,
)
from sqlalchemy import Column, Enum, String, Boolean, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship, Mapped

from app.common.consts import MAX_API_KEY_COUNT, MAX_API_WHITE_LIST_COUNT
from app.errors.exceptions import MaxAPIKeyCountException, MaxWhiteListCountException, NoKeyMatchException

from app.models.base import BaseModel
from app.models.enums import UserStatus, ApiKeyStatus, SnsType, Gender


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
                            lazy=True
                            )

    def get_oauth_access_token(self, oauth_name: str):
        """
        lazy="joined"되어 session 없이, oauth_accounts 모델에서 특정 oauth의 access_token을 얻는 메서드
        """
        for existing_oauth_account in self.oauth_accounts:
            if existing_oauth_account.oauth_name == oauth_name:
                return existing_oauth_account.access_token

        return None


class OAuthAccount(BaseModel, SQLAlchemyBaseOAuthAccountTable[int]):
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user = relationship("Users", back_populates="oauth_accounts",
                        foreign_keys=[user_id],
                        uselist=False,
                        )


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
