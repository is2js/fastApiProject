import asyncio
from os import environ
from pathlib import Path

import discord
import ezcord

from discord.ext.ipc import Server, ClientPayload
from fastapi import FastAPI

from app.common.config import DISCORD_BOT_SECRET_KEY, DISCORD_BOT_TOKEN
from app.errors.exceptions import DiscordIpcError
from app.utils.auth_utils import update_query_string
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

    @Server.route()
    async def guild_ids(self, _):
        # Expected type Dict or string as response, got list instead!
        # return [guild.id for guild in self.guilds]
        # => 외부에서는 await 호출 -> .response로 받는데, 이 때 str or dict가 반환되어야한다.
        return dict(guild_ids=[guild.id for guild in self.guilds])

    @Server.route()
    async def guild_stats(self, data: ClientPayload):
        guild = self.get_guild(data.guild_id)
        # .get_guild -> Guild: https://discordpy.readthedocs.io/en/stable/api.html#discord.Guild
        # => .icon은 image url이 아닌 Asset 객체
        # .icon -> Asset: https://discordpy.readthedocs.io/en/stable/api.html#discord.Asset
        # Attributes
        # - key, url
        # => guild.icon(Asset).url 로 써야 이미지 경로가 나온다.

        if not guild:
            return {}  # 외부에서 .response는 때려야하므로 ...

        icon = guild.icon.url
        # icon : https://cdn.discordapp.com/icons/1156511536316174368/b56a15058665d945d28251148720f3b9.png?size=1024
        icon = update_query_string(icon, size=128)
        # icon = guild.icon.url.with_size(35)
        # print(f"icon >> {icon}")
        # icon >> https://cdn.discordapp.com/icons/1156511536316174368/b56a15058665d945d28251148720f3b9.png?size=55

        return {
            "id": data.guild_id,
            "name": guild.name,
            "member_count": guild.member_count,
            "icon": icon
        }

    @Server.route()
    async def leave_guild(self, data: ClientPayload):
        guild = self.get_guild(data.guild_id)
        if guild:
            try:
                await guild.leave()
                return {"success": True, "message": f"Bot has left the server {data.guild_id}."}
            except discord.Forbidden:
                return {"success": False, "message": "I do not have permission to leave the server."}
            except discord.HTTPException:
                return {"success": False, "message": "Failed to leave the server."}
        else:
            return {"success": False, "message": f"Guild {data.guild_id} not found."}

    def init_app(self, app: FastAPI):
        @app.on_event("startup")
        async def start_up_discord():
            # 연결에 실패하더라도, app은 돌아가도록
            try:
                self.load_cogs(Path(__file__).resolve().parent / 'cogs')
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
