from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.responses import Response

from app.api.dependencies.auth import get_auth_routers, get_register_router, get_password_helper, get_oauth_routers
from app.database.conn import db
from app.errors.exceptions import (
    NoSupportException,
    NoUserMatchException, RequestError,
)
from app.models import Users
from app.schemas import UserRequest, Token, UserToken
from app.models.enums import SnsType
from app.utils.auth_utils import create_access_token
from app.utils.date_utils import D

router = APIRouter()

# fastapi-users
for oauth_router in get_auth_routers():
    router.include_router(
        router=oauth_router['router'],
        prefix=f"/{oauth_router['name']}",
    )
    # /api/v1/auth/cookie/login + logout

router.include_router(
    router=get_register_router(),
)  # /api/v1/auth/register

# /api/v1/auth/google/cookie or bearer/authorize
# /api/v1/auth/google/cookie or bearer/callback
for oauth_router in get_oauth_routers():
    router.include_router(
        router=oauth_router['router'],
        prefix=f"/{oauth_router['name']}",
    )


@router.post("/login/email", status_code=200, response_model=Token)
async def login(
        user_request: UserRequest,
        session: AsyncSession = Depends(db.session),
        password_helper=Depends(get_password_helper)
):
    """
    `로그인 API`\n
    :param user_request:
    :param session:
    :param password_helper:
    :return:
    """
    # 검증1) 모든 요소(email, pw)가 다 들어와야한다.
    if not user_request.email or not user_request.password:
        # return JSONResponse(status_code=400, content=dict(message="Email and PW must be provided."))
        raise RequestError('이메일와 비밀번호를 모두 입력해주세요.')

    # 검증2) email이 존재 해야만 한다.
    # user = await Users.get_by_email(session, user_info.email)
    user = await Users.filter_by(session=session, email=user_request.email).first()
    if not user:
        # return JSONResponse(status_code=400, content=dict(message="NO_MATCH_USER"))
        raise NoUserMatchException()

    # 검증3)  [입력된 pw] vs email로 등록된 DB저장 [해쉬 pw]  동일해야한다.
    # is_verified = bcrypt.checkpw(user_request.password.encode('utf-8'), user.password.encode('utf-8'))
    # is_verified = verify_password(user.hashed_password, user_request.password)
    is_verified, updated_hashed_password = password_helper.verify_and_update(
        user_request.password,
        user.hashed_password
    )

    if not is_verified:
        raise NoUserMatchException()

    if updated_hashed_password:
        await user.update(session=session, hashed_password=updated_hashed_password)

    await user.update(session=session, auto_commit=True, last_seen=D.datetime())

    token_data = UserToken.model_validate(user).model_dump(exclude={'hashed_password', 'marketing_agree'})
    token = dict(
        Authorization=f"Bearer {await create_access_token(data=token_data)}"
    )
    return token


@router.post("/login/{sns_type}", status_code=200, response_model=Token)
async def login_sns(sns_type: SnsType):
    """
    `소셜 로그인 API`\n
    - 개별 /api/v1/auth/{sns_type}/bearer/authorize로 redirect 됩니다.
    :param sns_type: 
    :return: 
    """

    if sns_type in SnsType:
        return Response(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": f'/api/v1/auth/{sns_type}/bearer/authorize'}
        )
    raise NoSupportException()
