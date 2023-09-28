from httpx_oauth.clients import discord
from httpx_oauth.clients.discord import DiscordOAuth2

from app.common.config import DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET


# - BASE_SCOPE ["identify", "email"]
def get_discord_client():
    return DiscordOAuth2(
        client_id=DISCORD_CLIENT_ID,
        client_secret=DISCORD_CLIENT_SECRET,
        scopes=discord.BASE_SCOPES + ['bot']
    )
