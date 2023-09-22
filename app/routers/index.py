import time
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import Response

from app.database.conn import db
from app.errors.exceptions import NotFoundUserException
from app.models import Users
from app.schemas import UserMe

router = APIRouter()


async def create_random_user(session=None, auto_commit=False, refresh=False):
    import random
    import string
    random_email = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    random_email += '@gmail.com'
    user = await Users.create(email=random_email, session=session, auto_commit=auto_commit, refresh=refresh)
    return user


# create가 포함된 route는 공용세션을 반드시 주입한다.
@router.get("/", response_model=UserMe)
async def index(session: AsyncSession = Depends(db.session)):
    """
    `ELB 상태 체크용 API` \n
    서버의 시각을 알려줍니다.
    """
    user = await Users.create(email='2@sdf.com', auto_commit=True, refresh=True)
    return user
@router.get("/test")
async def test(request: Request):
    try:
        user = await Users.create(email="abc@gmail.com", name='조재경', auto_commit=True)
        user.name = '2'
        await user.save(auto_commit=True)
    except Exception as e:
        from inspect import currentframe as frame

        request.state.inspect = frame()
        raise e

    current_time = datetime.utcnow()
    return Response(f"Notification API (UTC: {current_time.strftime('%Y.%m.%d %H:%M:%S')})")
