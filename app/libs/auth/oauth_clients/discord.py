from typing import cast, Any, Dict

from httpx_oauth.clients import discord
from httpx_oauth.clients.discord import DiscordOAuth2, PROFILE_ENDPOINT

from app.common.config import DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET
from app.errors.exceptions import GetOAuthProfileError

GUILD_ENDPOINT = PROFILE_ENDPOINT + '/guilds'


class DiscordClient(DiscordOAuth2):

    async def get_guilds(self, token: str):
        async with self.get_httpx_client() as client:
            response = await client.get(
                GUILD_ENDPOINT,
                headers={**self.request_headers, 'Authorization': f"Bearer {token}"},
            )

            data = cast(Dict[str, Any], response.json())

            return data

    # 자체 콜백을 위해, backend에만 정의해놨던 것을, client에도
    async def get_profile_info(self, access_token):
        async with self.get_httpx_client() as client:
            response = await client.get(
                discord.PROFILE_ENDPOINT,
                # params={},
                headers={**self.request_headers, "Authorization": f"Bearer {access_token}"},
            )
            if response.status_code >= 400:
                raise GetOAuthProfileError()

            profile_dict = dict()

            data = cast(Dict[str, Any], response.json())
            if avatar_hash := data.get('avatar'):
                # profile_dict['profile_img'] = f"https://cdn.discordapp.com/avatars/{data['id']}/{avatar_hash}.png"
                profile_dict['profile_img'] = f"https://cdn.discordapp.com/avatars/{data['id']}/{avatar_hash}"
            if nickname := data.get('global_name'):
                profile_dict['nickname'] = nickname

        return profile_dict


def get_discord_client():
    return DiscordClient(
        client_id=DISCORD_CLIENT_ID,
        client_secret=DISCORD_CLIENT_SECRET,
        scopes=discord.BASE_SCOPES # + ['bot'],  # BASE_SCOPE ["identify", "email"]
    )
