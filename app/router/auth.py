import bcrypt
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession


from app.database.conn import db
from app.errors.exceptions import NotFoundException, EmailAlreadyExistsException, NoSupportException, \
    NoUserMatchException
# from app.models.auth import Users
from app.models import Users
from app.schemas import SnsType, UserRegister, Token, UserToken
from app.utils.auth_utils import create_access_token

router = APIRouter(prefix='/auth')


# async def register(sns_type: SnsType, user_register_info: UserRegister, session: Session = Depends(db.session)):
@router.post("/register/{sns_type}", status_code=201, response_model=Token)
async def register(sns_type: SnsType, user_register_info: UserRegister, session: AsyncSession = Depends(db.session)):
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
            # return JSONResponse(status_code=400, content=dict(message="Email and PW must be provided."))
            raise ValueError('이메일 혹은 비밀번호를 모두 입력해주세요.')

        user = await Users.get_by_email(session, user_register_info.email)
        if user:
            # return JSONResponse(status_code=400, content=dict(message="EMAIL_EXISTS"))
            raise EmailAlreadyExistsException()

        # 비밀번호 해쉬 -> 해쉬된 비밀번호 + email -> user 객체 생성
        hash_pw = bcrypt.hashpw(user_register_info.pw.encode('utf-8'), bcrypt.gensalt())
        # new_user = Users.create(session, auto_commit=True, pw=hash_pw, email=user_register_info.email)
        new_user = await Users.create(session, auto_commit=True, pw=hash_pw, email=user_register_info.email)
        # user객체 -> new_user_data (dict by pydantic) -> create_access_token -> Token Schema용 dict 반환
        new_user_data = UserToken.model_validate(new_user).model_dump(exclude={'pw', 'marketing_agree'})
        # new_user_data = UserToken(new_user).model_dump(exclude={'pw', 'marketing_agree'})

        new_token = dict(
            Authorization=f"Bearer {await create_access_token(data=new_user_data)}"
        )
        return new_token

    # return JSONResponse(status_code=400, content=dict(message="NOT_SUPPORTED"))
    raise NoSupportException()


@router.post("/login/{sns_type}", status_code=200, response_model=Token)
async def login(sns_type: SnsType, user_info: UserRegister, session: AsyncSession = Depends(db.session)):
    """
    `로그인 API`\n
    :param sns_type:
    :param user_info:
    :return:
    """
    if sns_type == SnsType.email:
        # 검증1) 모든 요소(email, pw)가 다 들어와야한다.
        if not user_info.email or not user_info.pw:
            # return JSONResponse(status_code=400, content=dict(message="Email and PW must be provided."))
            raise ValueError('이메일 혹은 비밀번호를 모두 입력해주세요.')

        # 검증2) email이 존재 해야만 한다.
        user = await Users.get_by_email(session, user_info.email)
        if not user:
            # return JSONResponse(status_code=400, content=dict(message="NO_MATCH_USER"))
            raise NoUserMatchException()
        # 검증3)  [입력된 pw] vs email로 등록된 DB저장 [해쉬 pw]  동일해야한다.
        is_verified = bcrypt.checkpw(user_info.pw.encode('utf-8'), user.pw.encode('utf-8'))
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
