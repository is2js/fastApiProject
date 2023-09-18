from fastapi import APIRouter, Depends
from fastapi.security import APIKeyHeader

from . import auth, users, services
from ...common.config import config

API_KEY_HEADER = APIKeyHeader(name='Authorization', auto_error=False)

router = APIRouter() # v1 router -> 상위 main router객체에 prefix
router.include_router(auth.router, prefix='/auth', tags=['Authentication'])
router.include_router(users.router, prefix='/users', tags=['Users'], dependencies=[Depends(API_KEY_HEADER)])
# DEBUG 모드일 땐, service를 access/secret key 없이 headers에서 jwt검사후 state.user 추출
if config.DEBUG:
    router.include_router(services.router, prefix='/services', tags=['Services'], dependencies=[Depends(API_KEY_HEADER)])
else:
    router.include_router(services.router, prefix='/services', tags=['Services'])
