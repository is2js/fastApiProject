from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.api.dependencies.auth import get_users_router
from app.database.conn import db
from app.errors.exceptions import NoKeyMatchException, NoWhiteListMatchException
from app.models import Users, ApiKeys, ApiWhiteLists
from app.schemas import UserMe, ApiKeyRequest, ApiKeyResponse, ApiKeyFirstTimeResponse, SuccessMessage, \
    ApiWhiteListRequest, ApiWhiteListResponse
from app.utils.auth_utils import check_ip_format

# /api/v1/users + @
router = APIRouter()

# fastapi-users
router.include_router(
    router=get_users_router(),
    # prefix=''  # /me(get) + me(patch)  + {id}(get) + {id}(patch) + {id}(delete)
)

# @router.get('/me', response_model=UserMe)
# async def get_user(request: Request, session: AsyncSession = Depends(db.session)):
#     """
#     get my info
#     :param request:
#     :return:
#     """
#     user_token = request.state.user
#     user = await Users.get(session=session, id=user_token.id)
#     return user


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


@router.get('/apikeys', response_model=List[ApiKeyResponse])
async def get_api_key(request: Request, session: AsyncSession = Depends(db.session)):
    """
    현재 User의 모든 API KEY 조회
    :param request:
    :param session:
    :return:
    """
    user = request.state.user
    api_keys = await ApiKeys.filter_by(session=session, user_id=user.id).all()

    return api_keys


@router.put('/apikeys/{key_id}', response_model=ApiKeyResponse)
async def update_api_key(
        request: Request,
        api_key_request: ApiKeyRequest,
        key_id: int,
        session: AsyncSession = Depends(db.session)
):
    """
    User의 특정 API KEY의 user_memo 수정
    :param request:
    :param api_key_request:
    :param key_id:
    :param session:
    :return:
    """
    user = request.state.user

    # target_api_key = await ApiKeys.get(id=key_id)
    # # 해당 id의 key가 존재하는지 & 해당key의 상위도메인(user)이 일치하는지
    # if not target_api_key or target_api_key.user_id != user.id:
    #     raise NoKeyMatchException()

    target_api_key = await ApiKeys.filter_by(session=session, id=key_id, user_id=user.id).first()
    if not target_api_key:
        raise NoKeyMatchException()

    additional_info = api_key_request.model_dump()

    return await target_api_key.update(session=session, auto_commit=True, **additional_info)


@router.delete('/apikeys/{key_id}')
async def delete_api_key(
        request: Request,
        key_id: int,
        access_key: str,
        session: AsyncSession = Depends(db.session)
):
    """
    User의 특정 API KEY를 삭제

    :param request: 
    :param key_id: 
    :param access_key: 
    :param session: 
    :return: 
    """
    user = request.state.user

    target_api_key = await ApiKeys.filter_by(session=session, id=key_id, user_id=user.id, access_key=access_key).first()
    if not target_api_key:
        raise NoKeyMatchException()

    await target_api_key.delete(session=session, auto_commit=True)

    return SuccessMessage()


@router.post('/apikeys/{key_id}/whitelists', status_code=201, response_model=ApiWhiteListResponse)
async def create_api_white_list(
        request: Request,
        key_id: int,
        white_list_request: ApiWhiteListRequest,
        session: AsyncSession = Depends(db.session)
):
    """
    API White List 생성
    :param request:
    :param key_id:
    :param white_list_request:
    :param session:
    :return:

    """
    user = request.state.user
    # 상위도메인인 api_key부터, 최상위 user것인지 확인한다.
    await ApiKeys.check_key_owner(key_id, user, session=session)

    # ip 형식 확인
    ip_address = white_list_request.ip_address
    await check_ip_format(ip_address)

    # max count 확인
    await ApiWhiteLists.check_max_count(key_id, session=session)

    # 생성전 존재 검증(unique필드 대신 직접 exists확인)
    # -> (자동생성이라서) 이미 존재하면 return해준다.
    duplicated_white_list = await ApiWhiteLists.filter_by(session=session, api_key_id=key_id,
                                                          ip_address=ip_address).first()
    if duplicated_white_list:
        return duplicated_white_list

    new_white_list = await ApiWhiteLists.create(session=session, auto_commit=True,
                                                api_key_id=key_id, ip_address=ip_address)

    return new_white_list


@router.get('/apikeys/{key_id}/whitelists', response_model=List[ApiWhiteListResponse])
async def get_api_white_list(
        request: Request,
        key_id: int,
        session: AsyncSession = Depends(db.session)
):
    """
    API White List 생성
    :param request:
    :param key_id:
    :param session:
    :return:
    """
    # 상위도메인인 api_key부터, 최상위 user것인지 확인한다.
    user = request.state.user
    await ApiKeys.check_key_owner(key_id, user, session=session)

    # 상위도메인으로 딸린 모든 현재 도메인을 조회한다.
    white_lists = await ApiWhiteLists.filter_by(api_key_id=key_id).all()

    return white_lists


@router.delete("/apikeys/{key_id}/whitelists/{list_id}")
async def delete_api_white_list(
        request: Request,
        key_id: int,
        list_id: int,
        session: AsyncSession = Depends(db.session)
):
    # 상위도메인인 api_key부터, 최상위 user것인지 확인한다.
    user = request.state.user
    await ApiKeys.check_key_owner(key_id, user, session=session)

    target_white_list = await ApiWhiteLists.filter_by(id=list_id, api_key_id=key_id).first()
    if not target_white_list:
        raise NoWhiteListMatchException()

    await target_white_list.delete(session=session, auto_commit=True)

    return SuccessMessage()
