from typing import Optional, ClassVar

from pydantic import BaseModel, EmailStr, field_validator, ConfigDict, SecretStr, root_validator, model_validator, \
    validator, Field

from typing import Any
from fastapi.params import Path as OrigPath, Undefined

from app.models import SnsType

from typing import Any, Dict, Optional

from fastapi.params import Path as OriginalParamsPath, Undefined


class ParamsPath(OriginalParamsPath):
    """Original ``Path`` in ``fastapi.params`` implementation discards ``default``

    See https://github.com/tiangolo/fastapi/issues/5019
    """

    def __init__(self, default: Any = Undefined, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if default is not Undefined:
            self.default = default


def Path(  # noqa: N802
        default: Any = Undefined,
        *,
        alias: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        gt: Optional[float] = None,
        ge: Optional[float] = None,
        lt: Optional[float] = None,
        le: Optional[float] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        regex: Optional[str] = None,
        example: Any = Undefined,
        examples: Optional[Dict[str, Any]] = None,
        deprecated: Optional[bool] = None,
        include_in_schema: bool = True,
        **extra: Any,
) -> Any:
    """Redefined version of Path from ``fastapi.param_functions``"""
    return ParamsPath(
        default=default,
        alias=alias,
        title=title,
        description=description,
        gt=gt,
        ge=ge,
        lt=lt,
        le=le,
        min_length=min_length,
        max_length=max_length,
        regex=regex,
        example=example,
        examples=examples,
        deprecated=deprecated,
        include_in_schema=include_in_schema,
        **extra,
    )


class UserRequest(BaseModel):
    # pip install "pydantic[email]"
    email: EmailStr = None
    password: str = None

    # @field_validator("email")
    @model_validator(mode='before')  # <- 모든 필드 일괄 검사시 but 아예 입력도 안되면 pydantic 422 에러에 걸린다.
    def validate_root(cls, values):
        return values


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
