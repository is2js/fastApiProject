import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from app import api, pages
from app.api.dependencies.auth import active_user
from app.common.config import Config, DISCORD_BOT_TOKEN
from app.database.conn import db
from app.libs.discord.bot import discord_bot
from app.middlewares.access_control import AccessControl
from app.middlewares.trusted_hosts import TrustedHostMiddleware
from app.models import Users
from app.schemas import UserRead, UserCreate
from app.utils.http_utils import CustomJSONResponse




def create_app(config: Config):
    """
    앱 함수 실행
    :return:
    """
    app = FastAPI(
        version=config.APP_VERSION,
        title=config.APP_TITLE,
        description=config.APP_DESCRIPTION,
        default_response_class=CustomJSONResponse,
    )

    # static
    static_directory = Path(__file__).resolve().parent / 'static'
    app.mount('/static', StaticFiles(directory=static_directory), name='static')

    # database
    db.init_app(app)

    # discord
    discord_bot.init_app(app)

    # 미들웨어 추가 (실행순서는 반대)
    app.add_middleware(AccessControl)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOWED_SITES,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.TRUSTED_HOSTS, except_path=["/health"])

    # route 등록
    app.include_router(pages.router)  # template or test
    app.include_router(api.router, prefix='/api')

    @app.get("/authenticated-route")
    async def authenticated_route(user: Users = Depends(active_user)):
        return dict(
            message=f"Hello, {user.id}"
        )

    return app
