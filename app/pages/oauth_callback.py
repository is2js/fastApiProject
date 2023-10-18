from typing import Optional, Tuple

import jwt
from fastapi_users.jwt import decode_jwt
from fastapi_users.router.oauth import STATE_TOKEN_AUDIENCE
from httpx_oauth.oauth2 import OAuth2Token, BaseOAuth2
from starlette import status
from starlette.exceptions import HTTPException
from starlette.requests import Request

from app.common.config import JWT_SECRET
from app.errors.exceptions import StateDecodeException
from app.libs.auth.oauth_clients import get_oauth_client
from app.models import SnsType
from app.pages.exceptions import OAuthDeniedException


class DiscordAuthorizeCallback:
    client: BaseOAuth2  # BaseOAuth2
    route_name: Optional[str]
    redirect_url: Optional[str]

    def __init__(
            self,
            client: BaseOAuth2,
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
            state_data = decode_jwt(state, JWT_SECRET, [STATE_TOKEN_AUDIENCE])
            next_url = state_data['next'] if state_data.get('next', None) \
                else '/'
        except jwt.DecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

        return access_token, next_url


def get_discord_callback(redirect_url: Optional[str] = None, route_name: Optional[str] = None):
    return DiscordAuthorizeCallback(
        # discord_client,  # client_id, secret + authorization_url 기본 포함. -> access_token을 받아냄.
        get_oauth_client(SnsType.DISCORD),  # client_id, secret + authorization_url 기본 포함. -> access_token을 받아냄.
        redirect_url=redirect_url,  # 2개 중 1개로 client가 access_token요청시 필요한 redirect_uri을 만듦
        route_name=route_name,
    )


class OAuthAuthorizeCallback:
    # client: BaseOAuth2
    route_name: Optional[str]
    redirect_url: Optional[str]

    def __init__(
            self,
            # client: BaseOAuth2,
            route_name: Optional[str] = None,
            redirect_url: Optional[str] = None,
    ):
        assert (route_name is not None and redirect_url is None) or (
                route_name is None and redirect_url is not None
        ), "You should either set route_name or redirect_url"
        # self.client = client
        self.route_name = route_name
        self.redirect_url = redirect_url

    # dependency에 들어갈 객체용
    async def __call__(
            self,
            request: Request,
            sns_type: SnsType,  # 추가
            code: Optional[str] = None,
            state: Optional[str] = None,
            error: Optional[str] = None,
    ) -> Tuple[OAuth2Token, Optional[str]]:

        # 사용자가 인증 [계속] 대신 [취소]를 통해 거부한 경우
        if error:
            error_message = "인증이 취소되어, 더이상 진행할 수 없습니다."
            raise OAuthDeniedException(message=error_message, detail=error)

        if code is None or error is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error if error is not None else None,
            )

        if self.route_name:
            if sns_type:
                redirect_url = str(request.url_for(self.route_name, sns_type=sns_type.value))
            else:
                redirect_url = str(request.url_for(self.route_name))

        elif self.redirect_url:
            redirect_url = self.redirect_url

        oauth_client = get_oauth_client(sns_type)
        access_token: OAuth2Token = await oauth_client.get_access_token(
            code=code, redirect_uri=redirect_url
        )

        # return access_token, state

        # 추가로 로직 -> state에 next=가 있으면 여기서 빼주기
        next_url = '/'
        if state:
            try:
                state_data = decode_jwt(state, JWT_SECRET, [STATE_TOKEN_AUDIENCE])
                if next_url_ := state_data.get('next', None):
                    next_url = next_url_
            except jwt.DecodeError:
                # raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
                raise StateDecodeException()

        return access_token, next_url


def get_oauth_callback(redirect_url: Optional[str] = None, route_name: Optional[str] = None):
    return OAuthAuthorizeCallback(
        # client=get_oauth_client(sns_type),  # client_id, secret + authorization_url 기본 포함. -> access_token을 받아냄.
        # => sns_type을 현재 모르므로, 디펜던시 (call)부분에서 path를 받도록 수정
        redirect_url=redirect_url,  # 2개 중 1개로 client가 access_token요청시 필요한 redirect_uri을 만듦
        route_name=route_name,
    )
