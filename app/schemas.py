from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator
from pydantic.networks import EmailStr


# request model
class SnsType(str, Enum):
    email: str = "email"
    facebook: str = "facebook"
    google: str = "google"
    kakao: str = "kakao"


# request model
class UserRegister(BaseModel):
    # pip install "pydantic[email]"
    email: EmailStr = None
    pw: str = None

    @field_validator("email", "pw")
    def check_required_fields(cls, value):
        if value is None:
            raise ValueError("필수 필드입니다.")
        return value


# resopnse model
class Token(BaseModel):
    Authorization: str = None


# for Token - create_access_token
class UserToken(BaseModel):
    id: int
    email: str = None

    name: Optional[str] = None
    phone_number: Optional[str] = None
    profile_img: Optional[str] = None
    sns_type: Optional[str] = None

    class Config:
        # orm_mode = True
        from_attributes = True
        strict=False


class UserMe(BaseModel):
    id: int
    email: str = None

    name: Optional[str] = None
    phone_number: Optional[str] = None
    profile_img: Optional[str] = None
    sns_type: Optional[str] = None

    class Config:
        # orm_mode = True
        from_attributes = True
