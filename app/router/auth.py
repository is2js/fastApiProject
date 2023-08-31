import datetime

import bcrypt
import jwt
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from app.common.consts import JWT_SECRET, JWT_ALGORITHM
from app.database.conn import db
from app.database.models import Users
from app.schema import SnsType, UserRegister, Token, UserToken

router = APIRouter()


async def exists_user_email(email: str):
    user = Users.get(email=email)
    return True if user else False


def create_access_token(*, data: dict = None, expires_delta: int = None):
    # 들어온 데이터dict 원본을 변화시키지 않도록 미연에 방지( token 만료기간 연장)
    to_encode_data = data.copy()

    # 복사데이터dict 만료시간 update
    if expires_delta:
        to_encode_data.update({"exp": datetime.utcnow() + datetime.timedelta(hours=expires_delta)})

    # pyjwt로 엔코딩 -> string 반환
    encoded_jwt = jwt.encode(to_encode_data, key=JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


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
        # 검증2) email이 이미 존재하면 안된다.
        exists_email = await exists_user_email(user_register_info.email)
        if exists_email:
            return JSONResponse(status_code=400, content=dict(message="EMAIL_EXISTS"))

        # 비밀번호 해쉬 -> 해쉬된 비밀번호 + email -> user 객체 생성
        hash_pw = bcrypt.hashpw(user_register_info.pw.encode('utf-8'), bcrypt.gensalt())
        new_user = Users.create(session, auto_commit=True, pw=hash_pw, email=user_register_info.email)

        # user객체 -> new_user_data (dict by pydantic) -> create_access_token -> Token Schema용 dict 반환
        #   - v1: user_token = UserToken.from_orm(new_user).dict(exclude={'pw', 'marketing_agree'})
        new_user_data = UserToken.model_validate(new_user).model_dump(exclude={'pw', 'marketing_agree'})
        #   - {'id': 21, 'email': '5gr@example.com', 'name': None, 'phone_number': None, 'profile_img': None, 'sns_type': None}

        new_token = dict(
            Authorization=f"Bearer {create_access_token(data=new_user_data)}"
        )
        return new_token

    return JSONResponse(status_code=400, content=dict(message="NOT_SUPPORTED"))
