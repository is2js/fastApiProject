from typing import Optional, Tuple

import jwt
from fastapi_users.jwt import decode_jwt
from fastapi_users.router.oauth import STATE_TOKEN_AUDIENCE
from httpx_oauth.oauth2 import OAuth2Token
from starlette import status
from starlette.exceptions import HTTPException
from starlette.requests import Request

from app.common.config import JWT_SECRET, config
from app.libs.discord.oauth_client import DiscordClient, discord_client


class DiscordAuthorizeCallback:
    client: DiscordClient  # BaseOAuth2
    route_name: Optional[str]
    redirect_url: Optional[str]

    def __init__(
            self,
            client: DiscordClient,
            route_name: Optional[str] = None,
            redirect_url: Optional[str] = None,
    ):
        assert (route_name is not None and redirect_url is None) or (
                route_name is None and redirect_url is not None
        ), "You should either set route_name or redirect_url"
        self.client = client
        self.route_name = route_name
        self.redirect_url = redirect_url

    # dependency에 들어갈 객체용
    async def __call__(
            self,
            request: Request,
            code: Optional[str] = None,
            state: Optional[str] = None,
            error: Optional[str] = None,
    ) -> Tuple[OAuth2Token, Optional[str]]:

        if code is None or error is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error if error is not None else None,
            )

        if self.route_name:
            redirect_url = str(request.url_for(self.route_name))
        elif self.redirect_url:
            redirect_url = self.redirect_url

        access_token: OAuth2Token = await self.client.get_access_token(
            code=code, redirect_uri=redirect_url
        )

        # return access_token, state

        # 추가로 로직 -> state에 next=가 있으면 여기서 빼주기
        try:
            next_url = decode_jwt(state, JWT_SECRET, [STATE_TOKEN_AUDIENCE])['next'] if state \
                else config.HOST_MAIN
        except jwt.DecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

        return access_token, next_url


def get_discord_callback(redirect_url: Optional[str] = None, route_name: Optional[str] = None):
    return DiscordAuthorizeCallback(
        discord_client,  # client_id, secret + authorization_url 기본 포함. -> access_token을 받아냄.
        redirect_url=redirect_url,  # 2개 중 1개로 client가 access_token요청시 필요한 redirect_uri을 만듦
        route_name=route_name,
    )
