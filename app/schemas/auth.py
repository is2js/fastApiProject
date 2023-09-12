from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator, ConfigDict


class SnsType(str, Enum):
    email: str = "email"
    facebook: str = "facebook"
    google: str = "google"
    kakao: str = "kakao"


class UserRequest(BaseModel):
    # pip install "pydantic[email]"
    email: EmailStr = None
    pw: str = None

    @field_validator("email", "pw")
    def check_required_fields(cls, value):
        if value is None:
            raise ValueError("필수 필드입니다.")
        return value


class Token(BaseModel):
    """
    로그인/회원가입 성공시, token을 응답한다.
    """
    Authorization: str = None


class UserToken(BaseModel):
    """
    1) decode token된 dict -> state.user에 박는 Schema객체
    user_token_info = await decode_token(request.state.access_token)
    request.state.user = UserToken(**user_token_info)

    2) create_token시 들어가는 dict를 만들어준다.
    new_user_data = UserToken.model_validate(new_user).model_dump(exclude={'pw', 'marketing_agree'})
    await create_access_token(data=new_user_data) -> Bearer xxx

    """
    model_config = ConfigDict(from_attributes=True)


    id: int
    email: EmailStr = None

    name: Optional[str] = None
    phone_number: Optional[str] = None
    profile_img: Optional[str] = None
    sns_type: Optional[str] = None

    # class Config:
    #     # orm_mode = True
    #     from_attributes = True # orm type을 python type으로 변환 -> 직접 변환시 .model_validate()로 Orm -> Schame변환
    #     strict = False # 지정한 type과 다른 것이 들어와도 허용
