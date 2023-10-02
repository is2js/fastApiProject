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
    `ELB 상태 체크용 API` \n
    서버의 시각을 알려줍니다.
    """
    # bot에 연결된 server.route에 요청
    guild_count = await discord_ipc_client.request("guild_count")

    print("guild_count", guild_count)
    # guild_count <ServerResponse response=1 status=OK>
    print("guild_count.response", guild_count.response)
    # guild_count.response 1

    context = {
        'request': request,  # 필수
        'count': guild_count.response,  # 커스텀 데이터
    }
    return templates.TemplateResponse(
        "index.html",
        context
    )


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
