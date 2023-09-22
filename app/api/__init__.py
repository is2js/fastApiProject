from fastapi import APIRouter

from . import v1
from .custom_response import CustomJSONResponse

router = APIRouter(default_response_class=CustomJSONResponse)
router.include_router(v1.router, prefix="/v1")