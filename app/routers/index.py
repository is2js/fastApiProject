import time
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import Response

from app.database.conn import db
from app.models import Users

router = APIRouter()


async def create_random_user():
    import random
    import string
    random_email = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    random_email += '@gmail.com'
    user = await Users.create(email=random_email)
    return user


# create가 포함된 route는 공용세션을 반드시 주입한다.
@router.get("/")
async def index(session: AsyncSession = Depends(db.session)):
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
    # print("order_by", await Users.order_by("id").first())
    # print("order_by", await Users.order_by("id", "-id").first())
    # create시 외부공용sess없는 상태에서, auto_commit해주지 않으면, 해당객체가 session을 계속 물고 있게 된다.
    # -> user.update()시에는
    # user = await Users.create(email='abc@gmail.com')
    # await user.delete(auto_commit=True)

    # user = await Users.create(email='abc@gmail.com', auto_commit=True)
    # print("user", user)
    # print(await user.update(email='new_1_' + user.email))
    # # print(await user.update(email='new_1_' + user.email))
    # # is_filled False -> None
    # # print(await user.update(email='new_2_' + user.email, auto_commit=True))
    # print(await user.update(email='new_2_' + user.email, auto_commit=True))
    # # is_fillled True -> Users객체
    #
    # user = await Users.get(id=user.id)
    # print(await user.update(email='get_1_' + user.email))
    # print(await user.update(email='get_2_' + user.email, auto_commit=True))
    #
    # user = await create_random_user()
    # user = await Users.get(user.id, session=session)
    # print(user)
    # await user.delete(session=session, auto_commit=True)
    user = await Users.create(email='abcd')
    user = await Users.create(email='abcde')

    # user = await create_random_user()
    # user = await Users.filter_by(id=user.id).first()
    # await user.delete(auto_commit=True)


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
