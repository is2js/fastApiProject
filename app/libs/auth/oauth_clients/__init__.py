from app.common.config import (
    GOOGLE_CLIENT_SECRET, GOOGLE_CLIENT_ID,
    KAKAO_CLIENT_ID, KAKAO_CLIENT_SECRET,
    DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET
)
from .discord import get_discord_client
from .google import get_google_client
from .kakao import get_kakao_client


def get_oauth_clients():
    clients = []

    if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
        clients.append(get_google_client())

    if KAKAO_CLIENT_ID and KAKAO_CLIENT_SECRET:
        clients.append(get_kakao_client())

    if DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET:
        clients.append(get_discord_client())

    return clients
