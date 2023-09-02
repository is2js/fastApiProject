from datetime import datetime

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import Response

# from app.models.auth import Users
from app.models import Users

router = APIRouter()


# create가 포함된 route는 공용세션을 반드시 주입한다.
@router.get("/")
async def index():
    """
    `ELB 상태 체크용 API` \n
    서버의 시각을 알려줍니다.
    """
    # user = Users(name='sdaf')
    # session.add(user)
    # session.commit()

    # Users.create(session, auto_commit=True, name='조재성')

    user = Users.get(name='조재성')
    print(user)

    current_time = datetime.utcnow()
    return Response(f"Notification API (UTC: {current_time.strftime('%Y.%m.%d %H:%M:%S')})")

from inspect import currentframe as frame
@router.get("/test")
async def test(request: Request):

    # try:
    #     a = 1/0
    # except Exception as e:
    #     request.state.inspect = frame()
    #     raise e

    current_time = datetime.utcnow()
    return Response(f"Notification API (UTC: {current_time.strftime('%Y.%m.%d %H:%M:%S')})")