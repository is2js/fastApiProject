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

    # request schema정보를 -> .model_dump()로 dict로 변환하여 **를 통해 키워드로 입력하여 create한다.
    additional_info = api_key_request.model_dump()

    new_api_key = await ApiKeys.create(session=session, user=user, **additional_info)

    return new_api_key


