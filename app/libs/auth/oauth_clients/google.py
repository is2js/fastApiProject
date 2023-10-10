from typing import cast, Dict, Any

from httpx_oauth.clients import google
from httpx_oauth.clients.google import GoogleOAuth2

from app.common.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from app.errors.exceptions import GetOAuthProfileError


# BASE_SCOPES = [
#     "https://www.googleapis.com/auth/userinfo.profile",
#     "https://www.googleapis.com/auth/userinfo.email",
# ]

class GoogleClient(GoogleOAuth2):

    # 자체 콜백을 위해, backend에만 정의해놨던 것을, client에도

    async def get_profile_info(self, access_token):
        async with self.get_httpx_client() as client:
            response = await client.get(
                # PROFILE_ENDPOINT,
                google.PROFILE_ENDPOINT,
                # params={"personFields": "emailAddresses"},
                # params={"personFields": "photos,birthdays,genders,phoneNumbers"},
                params={"personFields": "photos,birthdays,genders,phoneNumbers,names,nicknames"},
                headers={**self.request_headers, "Authorization": f"Bearer {access_token}"},
            )

            if response.status_code >= 400:
                raise GetOAuthProfileError()

            data = cast(Dict[str, Any], response.json())

            profile_info = dict()
            # for field in "photos,birthdays,genders,phoneNumbers,names,nicknames".split(","):
            for field in "photos,birthdays,genders,phoneNumbers,names,nicknames".split(","):
                field_data_list = data.get(field)
                primary_data = next(
                    (field_data for field_data in field_data_list if field_data["metadata"]["primary"])
                    , None
                )
                if not primary_data:
                    continue
                # 'photos' primary_data >> {'metadata': {'primary': True, 'source': {'type': '', 'id': ''}}, 'url': 'https://lh3.googleusercontent.com/a/ACg8ocKn-HgWhuT191z-Xp6lq0Lud_nxcjMRLR1eJ0nMhMS1=s100', 'default': True}
                if field == 'photos' and (profile_img := primary_data.get('url')):
                    # "url": "https://lh3.googleusercontent.com/a/ACg8ocKn-HgWhuT191z-Xp6lq0Lud_nxcjMRLR1eJ0nMhMS1=s100",
                    profile_info['profile_img'] = profile_img

                if field == 'birthdays' and (date := primary_data.get('date')):
                    birthday_info = date
                    # "date": {
                    #              "year": 1900,
                    #              "month": 00,
                    #              "day": 00
                    #          }
                    # profile_info['birthday'] = str(birthday_info['year']) + str(birthday_info['month']) + str(
                    #     str(birthday_info['day']))
                    profile_info['birthyear'] = str(birthday_info['year'])
                    profile_info['birthday'] = str(birthday_info['month']) + str(birthday_info['day'])
                    profile_info['age_range'] = self.calculate_age_range(birthday_info['year'], birthday_info['month'],
                                                                         birthday_info['day'])

                if field == 'genders' and (gender := primary_data.get('value')):
                    # "value": "male",
                    profile_info['gender'] = gender

                if field == 'phoneNumbers' and (phone_number := primary_data.get('value')):
                    # "value": "010-yyyy-xxxx",
                    profile_info['phone_number'] = phone_number

                if field == 'names' and (name := primary_data.get('displayName')):
                    # "displayName":"조재성",
                    profile_info['nickname'] = name

                # if field == 'nicknames' and (nickname:=primary_data['value']):
                #     # "value":"부부한의사",
                #     profile_info['nickname'] = nickname

            return profile_info


# scope 선택 (backend.login()에서 재요청할 것이므로 굳이 여기서 안해도 될듯 하긴 함.)
def get_google_client():
    # return GoogleOAuth2(
    return GoogleClient(
        GOOGLE_CLIENT_ID,
        GOOGLE_CLIENT_SECRET,
        scopes=google.BASE_SCOPES + [
            "openid",
            "https://www.googleapis.com/auth/user.birthday.read",  # 추가 액세스 요청 3개 (전부 people api)
            "https://www.googleapis.com/auth/user.gender.read",
            "https://www.googleapis.com/auth/user.phonenumbers.read",
        ])
