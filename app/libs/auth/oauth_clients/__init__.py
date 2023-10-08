from app.common.config import (
    GOOGLE_CLIENT_SECRET, GOOGLE_CLIENT_ID,
    KAKAO_CLIENT_ID, KAKAO_CLIENT_SECRET,
    DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET
)
from app.errors.exceptions import NoSupportException
from app.models import SnsType
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


def get_oauth_client(sns_type: SnsType):
    if not sns_type:
        raise Exception(f'get_oauth_clients() 호출시 sns_type 입력해주세요: {sns_type}')

    if sns_type not in SnsType:
        raise NoSupportException()

    if sns_type == SnsType.GOOGLE:
        if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
            raise Exception('환경 변수에 구글 ID, SECRET 설정이 안되었습니다.')
        return get_google_client()

    if sns_type == SnsType.DISCORD:
        if not (DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET):
            raise Exception('환경 변수에 DISCORD ID, SECRET 설정이 안되었습니다.')
        return get_discord_client()

    if sns_type == SnsType.KAKAO:
        if not (KAKAO_CLIENT_ID and KAKAO_CLIENT_SECRET):
            raise Exception('환경 변수에 KAKAO ID, SECRET 설정이 안되었습니다.')
        return get_kakao_client()
