import asyncio
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

import discord
from fastapi import FastAPI, Depends
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from app import api, pages
from app.api.dependencies.auth import current_active_user, request_with_fastapi_optional_user
from app.common.config import Config, DISCORD_BOT_TOKEN, JWT_SECRET
from app.database.conn import db
from app.libs.discord.bot.bot import discord_bot

from app.middlewares.access_control import AccessControl
from app.middlewares.trusted_hosts import TrustedHostMiddleware
from app.models import Users
from app.schemas import UserRead, UserCreate
from app.utils.http_utils import CustomJSONResponse
from app.utils.logger import app_logger


# https://gist.github.com/haykkh/49ed16a9c3bbe23491139ee6225d6d09?permalink_comment_id=4289183#gistcomment-4289183
# => 어떤 사람은 실패했지만 나는 잘 작동함.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the ML model

    # Load discord bot
    # try 일본사이트 참고: https://qiita.com/maguro-alternative/items/6f57d4cc6c9923ba6a1d
    try:
        asyncio.create_task(discord_bot.start(DISCORD_BOT_TOKEN))
    except discord.LoginFailure:
        app_logger.get_logger.error('Discord bot 로그인에 실패하였습니다.')
        # await discord_bot.close()
    except discord.HTTPException as e:
        # traceback.print_exc()
        app_logger.get_logger.info('Discord bot의 Http연결에 실패하였습니다.')
    except KeyboardInterrupt:
        app_logger.get_logger.info('Discord bot이 예상치 못하게 종료되었습니다.')
        await discord_bot.close()

    # lifespan이 request.staet.xxx로 사용 가능하다면, ipc_client도 여기서 만들어 반환해주고
    # -> 종료도 같이 종료되고, 필요한 route마다 빼서 쓸 수 있게 하자.
    # -> 지금은 app/api/dependencies/auth.py에서 depends 로 정의 -> discord route에서 아래와 같이 user주입과 동시에 주입
    # -> dependencies=[Depends(request_with_fastapi_optional_user_and_bot_guild_count)]
    #     try:
    #         server_response = await discord_ipc_client.request("guild_count")
    #         # <ServerResponse response=1 status=OK>
    #         # [Errno 10061] Connect call failed ('127.0.0.1', 20000)
    #         request.state.bot_guild_count = server_response.response
    #     except Exception as e:
    #         request.state.bot_guild_count = None


    # print(f"discord_bot.is_closed() in lifespan >> {discord_bot.is_closed()}")
    # => is_ready()로 확인하여 초기화한다.
    yield {
        'discord_bot': discord_bot if discord_bot.is_ready() else None
    }

    # Unload the ML model
    # Unload discord bot
    if discord_bot.is_closed():  # web socket 연결 중인지 확인
        await discord_bot.close()


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
        lifespan=lifespan,  # discord bot과 함께함.
    )

    # static
    static_directory = Path(__file__).resolve().parent / 'static'
    app.mount('/static', StaticFiles(directory=static_directory), name='static')

    # database
    db.init_app(app)

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

    # SessionMiddleware 추가 ( google oauth 데코레이터 - 추가 scopes 를 template_oauth_callback 라우터로 전달하여 creds 생성에 필요)
    app.add_middleware(SessionMiddleware, secret_key=JWT_SECRET)

    # route 등록
    app.include_router(pages.routers.router)  # template or test
    app.include_router(api.router, prefix='/api')

    @app.get("/authenticated-route")
    async def authenticated_route(user: Users = Depends(current_active_user)):
        return dict(
            message=f"Hello, {user.id}"
        )

    return app
