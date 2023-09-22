import random
import string
from uuid import uuid4

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable
from sqlalchemy import Column, Enum, String, Boolean, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship

from app.common.consts import MAX_API_KEY_COUNT, MAX_API_WHITE_LIST_COUNT
from app.errors.exceptions import MaxAPIKeyCountException, MaxWhiteListCountException, NoKeyMatchException

from app.models.base import BaseModel
from app.models.enums import UserStatus, ApiKeyStatus


# class Users(BaseModel):
class Users(BaseModel, SQLAlchemyBaseUserTable[int]):
    status = Column(Enum(UserStatus), default=UserStatus.active)
    # email = Column(String(length=255), nullable=True, unique=True)
    # pw = Column(String(length=2000), nullable=True)
    name = Column(String(length=255), nullable=True)
    phone_number = Column(String(length=20), nullable=True, unique=True)
    profile_img = Column(String(length=1000), nullable=True)
    sns_type = Column(Enum("FB", "G", "K"), nullable=True)
    marketing_agree = Column(Boolean, nullable=True, default=True)

    sns_token = Column(String(length=64), nullable=True, unique=True)
    nickname = Column(String(length=30), nullable=True)
    gender = Column(Enum("male", "female"), nullable=True)
    age = Column(Integer, nullable=True, default=0)
    birthday = Column(String(length=20), nullable=True)

    api_keys = relationship("ApiKeys", back_populates="user",
                            cascade="all, delete-orphan",
                            lazy=True
                            )


class ApiKeys(BaseModel):
    created_at = Column(DateTime, nullable=False, default=func.utc_timestamp())
    updated_at = Column(DateTime, nullable=False, default=func.utc_timestamp(), onupdate=func.utc_timestamp())

    access_key = Column(String(length=64), nullable=False, index=True)
    secret_key = Column(String(length=64), nullable=False)
    user_memo = Column(String(length=40), nullable=True)
    status = Column(Enum(ApiKeyStatus), default=ApiKeyStatus.active)

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
