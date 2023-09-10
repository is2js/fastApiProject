import random
import string
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.database.conn import db
from app.models import Users, ApiKeys
from app.schemas import UserMe, ApiKeyRequest, ApiKeyResponse, ApiKeyFirstTimeResponse

# /api/v1/users + @
router = APIRouter()


@router.get('/me', response_model=UserMe)
async def get_user(request: Request):
    """
    get my info
    :param request:
    :return:
    """
    user_token = request.state.user
    user = Users.get(id=user_token.id)

    return user


@router.post('/apikeys', status_code=201, response_model=ApiKeyFirstTimeResponse)
async def create_api_key(request: Request, api_key_request: ApiKeyRequest, session: AsyncSession = Depends(db.session)):
    """
    API KEY 생성
    :param request:
    :param api_key_request:
    :param session:
    :return:
    """
    user = request.state.user

    # api max count 확인
    await ApiKeys.check_max_count(user, session=session)

    # secret_key(랜덤40글자) 생성 by alnums + random
    # ex> ''.join(random.choice(alnums) for _ in range(40)) -> 'JYx5Ww7h7l6q8cPut1ODLgCoVaqVz3R8owExnsLO'
    alnums = string.ascii_letters + string.digits
    secret_key = ''.join(random.choices(alnums, k=40))

    # access_key( uuid4 끝 12개 + uuid4 전체)
    # ex> f"{str(uuid4())[:-12]}{str(uuid4())}" -> 'b485bb0e-d5eb-4e09-8076-e170bf05-935d-431f-a0ec-21d5b084db6f'
    # => 빈값(None) 가변변수로 채워질 때까지(while not 가변변수)로 무한반복, 조건만족시 가변변수 채우기
    access_key = None
    while not access_key:
        access_key_candidate = f"{str(uuid4())[:-12]}{str(uuid4())}"
        exists_api_key = await ApiKeys.filter_by(session=session, access_key=access_key_candidate).exists()
        if not exists_api_key:
            access_key = access_key_candidate

    # request schema정보를 -> .model_dump()로 dict로 변환하여 **를 통해 키워드로 입력하여 create한다.
    additional_info = api_key_request.model_dump()

    new_api_key = await ApiKeys.create(session=session, auto_commit=True,
                                       user_id=user.id,
                                       secret_key=secret_key,
                                       access_key=access_key,
                                       **additional_info)

    return new_api_key


