from typing import cast, Dict, Any

from httpx_oauth.clients import discord

from app.errors.exceptions import GetOAuthProfileError
from app.libs.auth.backends.oauth.base import OAuthBackend


class DiscordBackend(OAuthBackend):
    OAUTH_NAME = 'discord'

    async def get_profile_info(self, access_token):
        async with self.get_httpx_client() as client:
            response = await client.get(
                discord.PROFILE_ENDPOINT,
                # params={},
                headers={**self.request_headers, "Authorization": f"Bearer {access_token}"},
            )
            # print("response.json()", response.json())
            # {
            #     "id":"ㅌㅌㅌ",
            #     "username":"tingstyle1",
            #     "avatar":"62705e264ab2d60adf3e947f07049c39", # 지정안했다면 None으로 들어가있다.
            #     "discriminator":"0",
            #     "public_flags":0,
            #     "flags":0,
            #     "banner":"None",
            #     "accent_color":"None",
            #     "global_name":"돌범",
            #     "avatar_decoration_data":"None",
            #     "banner_color":"None",
            #     "mfa_enabled":false,
            #     "locale":"ko",
            #     "premium_type":0,
            #     "email":"tingstyle1@gmail.com",
            #     "verified":true
            # }
            if response.status_code >= 400:
                raise GetOAuthProfileError()

            profile_dict = dict()

            data = cast(Dict[str, Any], response.json())
            if avatar_hash := data.get('avatar'):
                profile_dict['profile_img'] = f"https://cdn.discordapp.com/avatars/{data['id']}/{avatar_hash}.png"
            if nickname := data.get('global_name'):
                profile_dict['nickname'] = nickname

        return profile_dict


# discord_cookie_backend = DiscordBackend(
#     name="cookie",
#     transport=get_cookie_transport(),
#     get_strategy=get_jwt_strategy,
#     has_profile_callback=True,
# )
# discord_bearer_backend = DiscordBackend(
#     name="bearer",
#     transport=get_bearer_transport(),
#     get_strategy=get_jwt_strategy,
#     has_profile_callback=True,
# )


