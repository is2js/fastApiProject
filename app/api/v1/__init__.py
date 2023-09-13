from fastapi import APIRouter, Depends
from fastapi.security import APIKeyHeader

from . import auth, users, services

API_KEY_HEADER = APIKeyHeader(name='Authorization', auto_error=False)

router = APIRouter() # v1 router -> 상위 main router객체에 prefix
router.include_router(auth.router, prefix='/auth', tags=['Authentication'])
router.include_router(users.router, prefix='/users', tags=['Users'], dependencies=[Depends(API_KEY_HEADER)])
router.include_router(services.router, prefix='/services', tags=['Services'], dependencies=[Depends(API_KEY_HEADER)])
