import bcrypt
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_auth_routers, get_register_router
from app.database.conn import db
from app.errors.exceptions import (
    EmailAlreadyExistsException,
    NoSupportException,
    NoUserMatchException,
)
from app.models import Users
from app.schemas import SnsType, UserRequest, Token, UserToken
from app.utils.auth_utils import create_access_token

router = APIRouter()

# fastapi-users
for auth_router in get_auth_routers():
    router.include_router(
        router=auth_router['router'],
        prefix=f"/users/{auth_router['name']}",
    )

router.include_router(
    router=get_register_router(),
    prefix='/users'
)

from fastapi_users.password import PasswordHelper


# async def register(sns_type: SnsType, user_register_info: UserRegister, session: Session = Depends(db.session)):
@router.post("/register/{sns_type}", status_code=201, response_model=Token)
async def register(sns_type: SnsType, user_request: UserRequest, session: AsyncSession = Depends(db.session)):
    """
    `회원가입 API`\n
    :param sns_type:
    :param user_request:
    :param session:
    :return:
    """
    if sns_type == SnsType.email:
        # 검증1) 모든 요소(email, pw)가 다들어와야한다.
        if not user_request.email or not user_request.pw:
            # return JSONResponse(status_code=400, content=dict(message="Email and PW must be provided."))
            raise ValueError('이메일 혹은 비밀번호를 모두 입력해주세요.')

        # user = await Users.get_by_email(session, user_register_info.email)
        exists_user = await Users.filter_by(session=session, email=user_request.email).exists()
        if exists_user:
            # return JSONResponse(status_code=400, content=dict(message="EMAIL_EXISTS"))
            raise EmailAlreadyExistsException()

        # 비밀번호 해쉬 -> 해쉬된 비밀번호 + email -> user 객체 생성
        # hash_pw = bcrypt.hashpw(user_request.pw.encode('utf-8'), bcrypt.gensalt())
        hash_pw = PasswordHelper().hash(user_request.pw)

        # new_user = await Users.create(session=session, auto_commit=True, pw=hash_pw, email=user_request.email)
        new_user = await Users.create(session=session, auto_commit=True, hashed_password=hash_pw,
                                      email=user_request.email)

        # user객체 -> new_user_data (dict by pydantic) -> create_access_token -> Token Schema용 dict 반환
        new_user_data = UserToken.model_validate(new_user).model_dump(exclude={'pw', 'marketing_agree'})

        new_token = dict(
            Authorization=f"Bearer {await create_access_token(data=new_user_data)}"
        )
        return new_token

    # return JSONResponse(status_code=400, content=dict(message="NOT_SUPPORTED"))
    raise NoSupportException()


@router.post("/login/{sns_type}", status_code=200, response_model=Token)
async def login(sns_type: SnsType, user_request: UserRequest, session: AsyncSession = Depends(db.session)):
    """
    `로그인 API`\n
    :param sns_type:
    :param user_request:
    :return:
    """
    if sns_type == SnsType.email:
        # 검증1) 모든 요소(email, pw)가 다 들어와야한다.
        if not user_request.email or not user_request.pw:
            # return JSONResponse(status_code=400, content=dict(message="Email and PW must be provided."))
            raise ValueError('이메일 혹은 비밀번호를 모두 입력해주세요.')

        # 검증2) email이 존재 해야만 한다.
        # user = await Users.get_by_email(session, user_info.email)
        user = await Users.filter_by(session=session, email=user_request.email).first()
        if not user:
            # return JSONResponse(status_code=400, content=dict(message="NO_MATCH_USER"))
            raise NoUserMatchException()

        # 검증3)  [입력된 pw] vs email로 등록된 DB저장 [해쉬 pw]  동일해야한다.
        # is_verified = bcrypt.checkpw(user_request.pw.encode('utf-8'), user.pw.encode('utf-8'))
        is_verified = PasswordHelper().verify_and_update(user_request.pw, user.hashed_password)

        if not is_verified:
            # return JSONResponse(status_code=400, content=dict(message="NO_MATCH_USER"))
            raise NoUserMatchException()

        # 비번인증된 user객체 -> UserToken(dict) -> create_access_token -> Token모델용 token dict return
        token_data = UserToken.model_validate(user).model_dump(exclude={'pw', 'marketing_agree'})
        token = dict(
            Authorization=f"Bearer {await create_access_token(data=token_data)}"
        )
        return token

    # return JSONResponse(status_code=400, content=dict(msg="NOT_SUPPORTED"))
    raise NoSupportException()