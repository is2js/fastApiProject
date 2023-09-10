from sqlalchemy import Column, Enum, String, Boolean, Integer, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship

from app.common.consts import MAX_API_KEY_COUNT
from app.errors.exceptions import MaxAPIKeyCountException

from app.models.base import BaseModel


class Users(BaseModel):
    status = Column(Enum("active", "deleted", "blocked"), default="active")
    email = Column(String(length=255), nullable=True, unique=True)
    pw = Column(String(length=2000), nullable=True)
    name = Column(String(length=255), nullable=True)
    phone_number = Column(String(length=20), nullable=True, unique=True)
    profile_img = Column(String(length=1000), nullable=True)
    sns_type = Column(Enum("FB", "G", "K"), nullable=True)
    marketing_agree = Column(Boolean, nullable=True, default=True)

    keys = relationship("ApiKeys", back_populates="user")


class ApiKeys(BaseModel):
    created_at = Column(DateTime, nullable=False, default=func.utc_timestamp())
    updated_at = Column(DateTime, nullable=False, default=func.utc_timestamp(), onupdate=func.utc_timestamp())

    access_key = Column(String(length=64), nullable=False, index=True)
    secret_key = Column(String(length=64), nullable=False)
    user_memo = Column(String(length=40), nullable=True)
    status = Column(Enum("active", "stopped", "deleted"), default="active")

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("Users", back_populates="keys",
                        foreign_keys=[user_id],
                        uselist=False,
                        )

    is_whitelisted = Column(Boolean, default=False)
    whitelists = relationship("ApiWhiteLists", back_populates="api_key")

    @classmethod
    async def check_max_count(cls, user, session=None):
        user_api_key_count = await cls.filter_by(session=session, user_id=user.id, status='active').count()
        if user_api_key_count >= MAX_API_KEY_COUNT:
            raise MaxAPIKeyCountException()


class ApiWhiteLists(BaseModel):
    ip_addr = Column(String(length=64), nullable=False)
    api_key_id = Column(Integer, ForeignKey("apikeys.id"), nullable=False)
    api_key = relationship("ApiKeys", back_populates="whitelists",
                           foreign_keys=[api_key_id],
                           uselist=False,
                           )
