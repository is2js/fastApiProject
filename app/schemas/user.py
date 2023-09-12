from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class UserMe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr = None

    name: Optional[str] = None
    phone_number: Optional[str] = None
    profile_img: Optional[str] = None
    sns_type: Optional[str] = None


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
