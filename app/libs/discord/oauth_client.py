from typing import AsyncContextManager, Optional, List, Dict, cast, Any, Tuple

import httpx
from fastapi_users.router.oauth import generate_state_token
from httpx_oauth.errors import GetIdEmailError
from httpx_oauth.oauth2 import GetAccessTokenError, OAuth2Token

from app.common.config import DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, JWT_SECRET, DISCORD_GENERATED_AUTHORIZATION_URL
from app.errors.exceptions import GetOAuthProfileError
from app.utils.auth_utils import update_query_string

AUTHORIZE_ENDPOINT = "https://discord.com/api/oauth2/authorize"
ACCESS_TOKEN_ENDPOINT = "https://discord.com/api/oauth2/token"
REVOKE_TOKEN_ENDPOINT = "https://discord.com/api/oauth2/token/revoke"
# BASE_SCOPES = ["identify", "email"]
BASE_SCOPES = ["identify", "guilds"]
PROFILE_ENDPOINT = "https://discord.com/api/users/@me"
GUILD_ENDPOINT = PROFILE_ENDPOINT + '/guilds'


class DiscordClient:
    client_id: str
    client_secret: str
    authorization_url: str
    request_headers: Dict[str, str]

    access_token_endpoint: str
    refresh_token_endpoint: str
    revoke_token_endpoint: str

    def __init__(self, client_id: str, client_secret: str, authorization_url: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorization_url = authorization_url
        self.request_headers = {
            "Accept": "application/json",
        }

        self.access_token_endpoint = ACCESS_TOKEN_ENDPOINT
        self.refresh_token_endpoint = ACCESS_TOKEN_ENDPOINT
        self.revoke_token_endpoint = REVOKE_TOKEN_ENDPOINT

    async def get_access_token(self, code: str, redirect_uri: str):
        async with self.get_httpx_client() as client:
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }

            response = await client.post(
                ACCESS_TOKEN_ENDPOINT,
                data=data,
                headers=self.request_headers,
            )

            data = cast(Dict[str, Any], response.json())

            if response.status_code >= 400:
                raise GetAccessTokenError(data)

            return OAuth2Token(data)

    async def get_guilds(self, token: str):
        async with self.get_httpx_client() as client:
            response = await client.get(
                GUILD_ENDPOINT,
                headers={**self.request_headers, 'Authorization': f"Bearer {token}"},
            )

            data = cast(Dict[str, Any], response.json())

            return data

    async def get_id_email(self, token: str) -> Tuple[str, Optional[str]]:
        async with self.get_httpx_client() as client:
            response = await client.get(
                PROFILE_ENDPOINT,
                headers={**self.request_headers, "Authorization": f"Bearer {token}"},
            )

            if response.status_code >= 400:
                raise GetIdEmailError(response.json())

            data = cast(Dict[str, Any], response.json())

            user_id = data["id"]
            user_email = data.get("email")

            return user_id, user_email

    async def get_profile_info(self, access_token):
        async with self.get_httpx_client() as client:
            response = await client.get(
                PROFILE_ENDPOINT,
                # params={},
                headers={**self.request_headers, "Authorization": f"Bearer {access_token}"},
            )
            if response.status_code >= 400:
                raise GetOAuthProfileError()

            profile_dict = dict()

            data = cast(Dict[str, Any], response.json())
            if avatar_hash := data.get('avatar'):
                profile_dict['profile_img'] = f"https://cdn.discordapp.com/avatars/{data['id']}/{avatar_hash}.png"
            if nickname := data.get('global_name'):
                profile_dict['nickname'] = nickname

        return profile_dict

    @staticmethod
    def get_httpx_client() -> AsyncContextManager[httpx.AsyncClient]:
        return httpx.AsyncClient()

    async def get_authorization_url(
            self,
            redirect_uri: str,
            state_data: Dict[str, str] = None,
    ) -> str:

        self.authorization_url = update_query_string(
            self.authorization_url,
            redirect_uri=redirect_uri,
            state=generate_state_token(state_data, JWT_SECRET) if state_data else None
        )

        return self.authorization_url


discord_client = DiscordClient(
    client_id=DISCORD_CLIENT_ID,
    client_secret=DISCORD_CLIENT_SECRET,
    authorization_url=DISCORD_GENERATED_AUTHORIZATION_URL,
)
