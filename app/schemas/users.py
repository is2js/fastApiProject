from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi_users.schemas import BaseUser, BaseUserCreate, BaseUserUpdate
from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas import SnsType


class UserMe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr = None

    name: Optional[str] = None
    phone_number: Optional[str] = None
    profile_img: Optional[str] = None
    sns_type: Optional[str] = None


####################
#  fastapi-users   #
####################

class UserRead(BaseUser[int]):
    name: Optional[str] = None
    phone_number: Optional[str] = None
    profile_img: Optional[str] = None
    sns_type: Optional[str] = None

    nickname: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    birthday: Optional[str] = None


class UserCreate(BaseUserCreate):
    pass


class UserUpdate(BaseUserUpdate):
    name: Optional[str] = None
    phone_number: Optional[str] = None
    profile_img: Optional[str] = None
    sns_type: Optional[str] = None

    nickname: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    birthday: Optional[str] = None

    marketing_agree: Optional[bool] = None


##############
#  ApiKeys   #
##############

class ApiKeyRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_memo: Optional[str] = None


class ApiKeyResponse(ApiKeyRequest):
    id: int
    access_key: str
    created_at: datetime


class ApiKeyFirstTimeResponse(ApiKeyResponse):
    secret_key: str


###################
#  ApiWhiteList   #
###################

class ApiWhiteListRequest(BaseModel):
    ip_address: str


class ApiWhiteListResponse(ApiWhiteListRequest):
    model_config = ConfigDict(from_attributes=True)

    id: int
