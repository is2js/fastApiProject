from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.database.conn import db
from app.database.schema import Users

router = APIRouter()


# create가 포함된 route는 공용세션을 반드시 주입한다.
@router.get("/")
async def index(session: Session = Depends(db.session)):

    # user = Users(name='sdaf')
    # session.add(user)
    # session.commit()

    Users.create(session, auto_commit=True, name='조재성')

    current_time = datetime.utcnow()
    return Response(f"Notification API (UTC: {current_time.strftime('%Y.%m.%d %H:%M:%S')} )")
