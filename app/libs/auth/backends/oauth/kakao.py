import json
from typing import cast, Dict, Any

from httpx_oauth.clients import kakao

from app.errors.exceptions import GetOAuthProfileError
from app.libs.auth.backends.oauth.base import OAuthBackend


class KakaoBackend(OAuthBackend):
    OAUTH_NAME = 'kakao'

    async def get_profile_info(self, access_token):
        async with self.get_httpx_client() as client:
            # https://developers.kakao.com/docs/latest/ko/kakaologin/rest-api#propertykeys
            PROFILE_ADDITIONAL_PROPERTIES = [
                "kakao_account.profile",
                "kakao_account.age_range",
                "kakao_account.birthday",
                "kakao_account.gender"
            ]

            response = await client.post(
                kakao.PROFILE_ENDPOINT,
                params={"property_keys": json.dumps(PROFILE_ADDITIONAL_PROPERTIES)},
                headers={**self.request_headers, "Authorization": f"Bearer {access_token}"},
            )

            if response.status_code >= 400:
                raise GetOAuthProfileError()

            data = cast(Dict[str, Any], response.json())
            # print(data)
            # {
            #     "id":xxx,
            #     "connected_at":"2023-09-26T11:46:32Z",
            #     "kakao_account":{
            #         "profile_nickname_needs_agreement":false,
            #         "profile_image_needs_agreement":false,
            #         "profile":{
            #             "nickname":"조재성",
            #             "thumbnail_image_url":"http://k.kakaocdn.net/dn/bLu5OM/btsqh2LkkN0/KR5dVHiRVIFfTC0uZCtWTk/img_110x110.jpg",
            #             "profile_image_url":"http://k.kakaocdn.net/dn/bLu5OM/btsqh2LkkN0/KR5dVHiRVIFfTC0uZCtWTk/img_640x640.jpg",
            #             "is_default_image":false
            #         },
            #         "has_age_range":true,
            #         "age_range_needs_agreement":false,
            #         "age_range":"30~39",
            #         "has_birthday":true,
            #         "birthday_needs_agreement":false,
            #         "birthday":"1218",
            #         "birthday_type":"SOLAR",
            #         "has_gender":true,
            #         "gender_needs_agreement":false,
            #         "gender":"male"
            #     }
            # }

            # 동의 안했을 수도 있으니, 키값을 확인해서 꺼내서 db에 맞게 넣는다.
            profile_info = dict()

            kakao_account = data['kakao_account']

            if profile := kakao_account.get('profile'):
                profile_info['profile_img'] = profile.get('thumbnail_image_url', None)
                if nickname := profile.get('nickname', None):
                    profile_info['nickname'] = nickname

            if kakao_account.get('birthday'):
                profile_info['birthday'] = kakao_account['birthday']

            if kakao_account.get('has_age_range'):
                # profile_info['birthday'] = kakao_account['age_range'] + profile_info['birthday']
                profile_info['age_range'] = kakao_account['age_range']

            if kakao_account.get('gender'):
                profile_info['gender'] = kakao_account['gender']

        # profile_info >> {
        # 'profile_img': 'http://k.kakaocdn.net/dn/bLu5OM/btsqh2LkkN0/KR5dVHiRVIFfTC0uZCtWTk/img_110x110.jpg',
        # 'birthday': '1218', 'age_range': '30~39', 'gender': 'male'
        # }

        return profile_info


# kakao_cookie_backend = KakaoBackend(
#     name="cookie",
#     transport=get_cookie_transport(),
#     get_strategy=get_jwt_strategy,
#     has_profile_callback=True,
# )
# kakao_bearer_backend = KakaoBackend(
#     name="bearer",
#     transport=get_bearer_transport(),
#     get_strategy=get_jwt_strategy,
#     has_profile_callback=True,
# )


