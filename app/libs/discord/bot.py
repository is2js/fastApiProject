import asyncio
from os import environ

import discord
import ezcord

from discord.ext.ipc import Server
from fastapi import FastAPI

from app.common.config import DISCORD_BOT_SECRET_KEY, DISCORD_BOT_TOKEN
from app.errors.exceptions import DiscordIpcError
from app.utils.logger import app_logger


class DiscordBot(ezcord.Bot):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        # self.ipc = Server(self, secret_key="hani")  # test 이후 config로 변경
        self.ipc = Server(self, secret_key=DISCORD_BOT_SECRET_KEY)


    async def on_ready(self):
        await self.ipc.start()
        # print(f"{self.user} Application is online")
        app_logger.get_logger.info(f"{self.user} Application is online")

    async def on_ipc_error(self, endpoint: str, exc: Exception) -> None:
        raise DiscordIpcError(exception=exc)

    @Server.route()
    async def guild_count(self, _):
        # return len(self.guilds)
        # discord.ext.ipc.errors.InvalidReturn: ('guild_count', 'Expected type Dict or string as response, got int instead!')
        # => route라서, 외부에서 .response를 찍어 확인하며, 응답은 여느 http router처럼, str() or dict() ...
        return str(len(self.guilds))

    def init_app(self, app: FastAPI):
        @app.on_event("startup")
        async def start_up_discord():
            # 연결에 실패하더라도, app은 돌아가도록
            try:
                asyncio.create_task(self.start(DISCORD_BOT_TOKEN))
            except discord.LoginFailure:
                app_logger.get_logger.error('Discord bot 연결에 실패하였습니다.')

        @app.on_event("shutdown")
        async def shut_down_discord():
            # websocket 연결이 끊겼으면, close시키기
            if not self.is_closed():
                await self.close()


discord_bot = DiscordBot()

if __name__ == '__main__':
    bot = DiscordBot()

    # from app.common.config import DISCORD_BOT_TOKEN
    # token = environ.get(DISCORD_BOT_TOKEN, None)
    # => app이 로드되는 순간, config 생성없이 init.py도 불러와져서 에러남.

    from dotenv import load_dotenv

    load_dotenv()
    token = environ.get("DISCORD_BOT_TOKEN", None)

    bot.run(token)
