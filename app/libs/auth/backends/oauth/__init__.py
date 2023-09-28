from app.libs.auth.strategies import get_jwt_strategy
from app.libs.auth.transports import get_cookie_transport, get_bearer_transport
from .discord import DiscordBackend
from .google import GoogleBackend
from .kakao import KakaoBackend


def get_google_backends():
    return [
        GoogleBackend(
            name="cookie",
            transport=get_cookie_transport(),
            get_strategy=get_jwt_strategy,
            has_profile_callback=True,
        ),
        GoogleBackend(
            name="bearer",
            transport=get_bearer_transport(),
            get_strategy=get_jwt_strategy,
            has_profile_callback=True,
        )
    ]


def get_kakao_backends():
    return [
        KakaoBackend(
            name="cookie",
            transport=get_cookie_transport(),
            get_strategy=get_jwt_strategy,
            has_profile_callback=True,
        ),
        KakaoBackend(
            name="bearer",
            transport=get_bearer_transport(),
            get_strategy=get_jwt_strategy,
            has_profile_callback=True,
        )
    ]


def get_discord_backends():
    return [
        DiscordBackend(
            name="cookie",
            transport=get_cookie_transport(),
            get_strategy=get_jwt_strategy,
            has_profile_callback=True,
        ),
        DiscordBackend(
            name="bearer",
            transport=get_bearer_transport(),
            get_strategy=get_jwt_strategy,
            has_profile_callback=True,
        )
    ]
