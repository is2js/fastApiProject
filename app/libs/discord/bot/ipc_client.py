from discord.ext.ipc import Client

from app.common.config import DISCORD_BOT_SECRET_KEY
from app.libs.discord.bot.exceptions import DiscordBotRequestException


# discord_ipc_client = Client(secret_key=DISCORD_BOT_SECRET_KEY)

class DiscordIPCWrapper:
    def __init__(self, secret_key):
        self.ipc_client = Client(secret_key=secret_key)

    async def request(self, request_type, *args, **kwargs):
        try:
            response = await self.ipc_client.request(request_type, **kwargs)
            return response
        except Exception as e:
            # "[Errno 10061] Connect call failed ('127.0.0.1', 20000)"
            # TODO: bot에 요청실패시 알려주기
            raise DiscordBotRequestException(
                message=f'Discord bot에 request 실패: {request_type} | {str(e)}',
                exception=e
            )


discord_ipc_client = DiscordIPCWrapper(secret_key=DISCORD_BOT_SECRET_KEY)
