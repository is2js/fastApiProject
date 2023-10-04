from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import Response

from app.database.conn import db
from app.libs.discord.ipc_client import discord_ipc_client
from app.models import Users
from app.pages import templates

router = APIRouter()


@router.get("/")
async def index(request: Request, session: AsyncSession = Depends(db.session)):
    """
    `ELB 헬스 체크용`
    """
    return "ok"
    # context = {
    #     'request': request,  # 필수
    # }
    # return templates.TemplateResponse(
    #     "index.html",
    #     context
    # )

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
