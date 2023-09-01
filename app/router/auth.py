import bcrypt
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from app.database.conn import db
# from app.models.auth import Users
from app.models import Users
from app.schema import SnsType, UserRegister, Token, UserToken
from app.utils.auth_utils import create_access_token

"""
400 Bad Request
401 Unauthorized
403 Forbidden
404 Not Found
405 Method not allowed

500 Internal Error
502 Bad Gateway
504 Timeout

200 OK
201 Created
"""
router = APIRouter(prefix='/auth')

@router.post("/register/{sns_type}", status_code=201, response_model=Token)
async def register(sns_type: SnsType, user_register_info: UserRegister, session: Session = Depends(db.session)):
    """
    `회원가입 API`\n
    :param sns_type:
    :param user_register_info:
    :param session:
    :return:
    """
    if sns_type == SnsType.email:
        # 검증1) 모든 요소(email, pw)가 다들어와야한다.
        if not user_register_info.email or not user_register_info.pw:
            return JSONResponse(status_code=400, content=dict(message="Email and PW must be provided."))

        user = await Users.get_by_email(session, user_register_info.email)
        if user:
            return JSONResponse(status_code=400, content=dict(message="EMAIL_EXISTS"))

        # 비밀번호 해쉬 -> 해쉬된 비밀번호 + email -> user 객체 생성
        hash_pw = bcrypt.hashpw(user_register_info.pw.encode('utf-8'), bcrypt.gensalt())
        new_user = Users.create(session, auto_commit=True, pw=hash_pw, email=user_register_info.email)

        # user객체 -> new_user_data (dict by pydantic) -> create_access_token -> Token Schema용 dict 반환
        #   - v1: user_token = UserToken.from_orm(new_user).dict(exclude={'pw', 'marketing_agree'})
        new_user_data = UserToken.model_validate(new_user).model_dump(exclude={'pw', 'marketing_agree'})
        #   - {'id': 21, 'email': '5gr@example.com', 'name': None, 'phone_number': None, 'profile_img': None, 'sns_type': None}

        new_token = dict(
            Authorization=f"Bearer {await create_access_token(data=new_user_data)}"
        )
        return new_token

    return JSONResponse(status_code=400, content=dict(message="NOT_SUPPORTED"))


@router.post("/login/{sns_type}", status_code=200, response_model=Token)
async def login(sns_type: SnsType, user_info: UserRegister, session: Session = Depends(db.session)):
    """
    `로그인 API`\n
    :param sns_type:
    :param user_info:
    :return:
    """
    if sns_type == SnsType.email:
        # 검증1) 모든 요소(email, pw)가 다 들어와야한다.
        if not user_info.email or not user_info.pw:
            return JSONResponse(status_code=400, content=dict(message="Email and PW must be provided."))
        # 검증2) email이 존재 해야만 한다.
        user = await Users.get_by_email(session, user_info.email)
        if not user:
            return JSONResponse(status_code=400, content=dict(message="NO_MATCH_USER"))
        # 검증3)  [입력된 pw] vs email로 등록된 DB저장 [해쉬 pw]  동일해야한다.
        is_verified = bcrypt.checkpw(user_info.pw.encode('utf-8'), user.pw.encode('utf-8'))
        if not is_verified:
            return JSONResponse(status_code=400, content=dict(message="NO_MATCH_USER"))

        # 비번인증된 user객체 -> UserToken(dict) -> create_access_token -> Token모델용 token dict return
        token_data = UserToken.model_validate(user).model_dump(exclude={'pw', 'marketing_agree'})
        token = dict(
            Authorization=f"Bearer {await create_access_token(data=token_data)}"
        )
        return token

    return JSONResponse(status_code=400, content=dict(msg="NOT_SUPPORTED"))
