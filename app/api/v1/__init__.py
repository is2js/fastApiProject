from fastapi import APIRouter, Depends
from fastapi.security import APIKeyHeader

from . import auth, user

API_KEY_HEADER = APIKeyHeader(name='Authorization', auto_error=False)

router = APIRouter() # v1 router -> 상위 main router객체에 prefix
router.include_router(auth.router, prefix='/auth', tags=['Authentication'])
router.include_router(user.router, prefix='/users', tags=['Users'], dependencies=[Depends(API_KEY_HEADER)])
