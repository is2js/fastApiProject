from __future__ import annotations

from datetime import datetime
from typing import Optional, Union

from fastapi_users.schemas import BaseUser, BaseUserCreate, BaseUserUpdate
from pydantic import BaseModel, ConfigDict, EmailStr, validator, field_validator, Field, root_validator, model_validator

from app.models import SnsType, Gender, UserStatus, RoleName, Roles


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

class RolesResponse(BaseModel):
    #  Input should be a valid dictionary or instance of Role [type=model_type, input_value=<Roles#1>, input_type=Roles]
    model_config = ConfigDict(from_attributes=True)
    name: str


class UserRead(BaseUser[int]):
    # model_config = ConfigDict(from_attributes=True) => 이미 BaseUser에 되어있음.
    name: Optional[str] = None
    phone_number: Optional[str] = None
    profile_img: Optional[str] = None
    sns_type: Optional[str] = None

    nickname: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    birthday: Optional[str] = None

    # role: RolesResponse
    # "role": {
    #       "name": "USER"
    #     }

    # 자동load relationship(role=, Roles)를
    # 1) @hybrid_property로 필요한 필드만 정의하고
    # 2) 모델의 Response Schema에 반환타입 함께 명시하면,
    # => relationship모델의 특정 필드만 반환시킬 수 있다.
    role_name: RoleName
    # "role_name": "user"


class UserCreate(BaseUserCreate):
    # model_config = ConfigDict(use_enum_values=True, )
    sns_type: Optional[SnsType] = "email"

    # Request 에서 type을 : Enum으로 해주면 -> front의 enum_value("user")입력을 -> Enum객체로 자동변환해준다.
    # : front "user" 입력 -> RoleName.USER 자동변환
    role_name: Optional[RoleName] = None # 내부에서 기본값 넣어주는 처리 됨.


class UserUpdate(BaseUserUpdate):
    # model_config = ConfigDict(use_enum_values=True, )
    name: Optional[str] = None
    phone_number: Optional[str] = None
    profile_img: Optional[str] = None

    nickname: Optional[str] = None
    age: Optional[int] = None
    birthday: Optional[str] = None

    marketing_agree: Optional[bool] = None

    sns_type: Optional[SnsType] = "email"
    gender: Optional[Gender] = "male"
    # status: Optional[UserStatus] = "active"

    role_name: Optional[RoleName] = None # 내부에서 기본값 넣어주는 처리 됨.


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
