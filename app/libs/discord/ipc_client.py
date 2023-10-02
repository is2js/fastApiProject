from discord.ext.ipc import Client

from app.common.config import DISCORD_BOT_SECRET_KEY

discord_ipc_client = Client(secret_key=DISCORD_BOT_SECRET_KEY)
