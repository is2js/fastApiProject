from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import Response

from app.database.conn import db
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

    # print("3", await Users.get(3)) # 3 None
    # print("77", await Users.get(77))  # <app.models.auth.Users object at 0x7fa3696fd610>
    # print("77 78", await Users.get(77, 78))  # <app.models.auth.Users object at 0x7fa3696fd610>
    # # print("999999, 77", await Users.get(999999, 77)) # 유효하지 않은 id or 중복된 id가 포함되어 있습니다.
    # print("9999", await Users.get(999999))  # "'<class \\'app.models.auth.Users\\'> with id \"999999\" was not found'"
    # print("get keyword", await Users.get(id=77)) # keyword <app.models.auth.Users object at 0x7faed13e4190>
    # print("filter_by", await Users.filter_by(id=1).first())
    # print("filter_by", await Users.filter_by(id=1).filter_by(id__ne=None).first())
    print("order_by", await Users.order_by("id").first())
    print("order_by", await Users.order_by("id", "-id").first())


    current_time = datetime.utcnow()
    return Response(f"Notification API (UTC: {current_time.strftime('%Y.%m.%d %H:%M:%S')})")


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
