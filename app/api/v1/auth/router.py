import asyncio
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from starlette.responses import Response, RedirectResponse

from app.api.dependencies.auth import get_auth_routers, get_register_router, get_password_helper, get_oauth_routers
from app.database.conn import db
from app.errors.exceptions import (
    EmailAlreadyExistsException,
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
    # /cookie/login + logout

router.include_router(
    router=get_register_router(),
)  # /register

# /api/v1/auth/users/jwt/google/cookie/authorize
# /api/v1/auth//users/jwt/google/cookie/callback
# router.include_router(
#     router=get_oauth_router(),
#     prefix='/users/jwt/google'
# )

# /api/v1/auth/google/cookie or bearer/authorize
# /api/v1/auth/google/cookie or bearer/callback
for oauth_router in get_oauth_routers():
    router.include_router(
        router=oauth_router['router'],
        prefix=f"/{oauth_router['name']}",
    )


# @router.post("/register/{sns_type}", status_code=201, response_model=Token)
# async def register(sns_type: SnsType, user_request: UserRequest, session: AsyncSession = Depends(db.session),
#                    password_helper=Depends(get_password_helper)):
#     """
#     `회원가입 API`\n
#     :param sns_type:
#     :param user_request:
#     :param session:
#     :return:
#     """
#     if sns_type == SnsType.EMAIL:
#         # 검증1) 모든 요소(email, pw)가 다들어와야한다.
#         if not user_request.email or not user_request.password:
#             # return JSONResponse(status_code=400, content=dict(message="Email and PW must be provided."))
#             raise ValueError('이메일 혹은 비밀번호를 모두 입력해주세요.')
#
#         # user = await Users.get_by_email(session, user_register_info.email)
#         exists_user = await Users.filter_by(session=session, email=user_request.email).exists()
#         if exists_user:
#             # return JSONResponse(status_code=400, content=dict(message="EMAIL_EXISTS"))
#             raise EmailAlreadyExistsException()
#
#         # 비밀번호 해쉬 -> 해쉬된 비밀번호 + email -> user 객체 생성
#         # hashed_password = await hash_password(user_request.password)
#         hashed_password = password_helper.hash(user_request.password)
#
#         # new_user = await Users.create(session=session, auto_commit=True, pw=hash_pw, email=user_request.email)
#         new_user = await Users.create(session=session, auto_commit=True, hashed_password=hashed_password,
#                                       email=user_request.email)
#
#         # user객체 -> new_user_data (dict by pydantic) -> create_access_token -> Token Schema용 dict 반환
#         new_user_data = UserToken.model_validate(new_user).model_dump(exclude={'password', 'marketing_agree'})
#
#         new_token = dict(
#             Authorization=f"Bearer {await create_access_token(data=new_user_data)}"
#         )
#         return new_token
#
#     # return JSONResponse(status_code=400, content=dict(message="NOT_SUPPORTED"))
#     raise NoSupportException()


# def get_user_request_for_sns_type(sns_type: SnsType) -> [UserRequest, None]:
#     print(f"sns_type >> {sns_type}") # SnsType.EMAIL
#
#     if sns_type == SnsType.EMAIL:
#         return UserRequest()
#     else:
#         return

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
