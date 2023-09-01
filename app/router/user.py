from fastapi import APIRouter
from starlette.requests import Request

from app.models import Users
from app.schema import UserMe

router = APIRouter(prefix='/user')


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
