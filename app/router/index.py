from datetime import datetime

from fastapi import APIRouter
from starlette.responses import Response

from app.database.models import Users

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
