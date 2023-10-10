import json
from typing import cast, Dict, Any

from httpx_oauth.clients import kakao
from httpx_oauth.clients.kakao import KakaoOAuth2

from app.common.config import KAKAO_CLIENT_ID, KAKAO_CLIENT_SECRET
from app.errors.exceptions import GetOAuthProfileError


# - BASE_SCOPE ["profile_nickname", "account_email"]
# - profile_image, gender, age_range, birthday

class KakaoClient(KakaoOAuth2):

    # 자체 콜백을 위해, backend에만 정의해놨던 것을, client에도
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
        return profile_info


def get_kakao_client():
    # return KakaoOAuth2(
    return KakaoClient(
        client_id=KAKAO_CLIENT_ID,  # 앱 - RESPT API 키
        client_secret=KAKAO_CLIENT_SECRET,  # 앱 > 보안 > CLIENT_SECRET
        scopes=kakao.BASE_SCOPES + ['profile_image', 'gender', 'age_range', 'birthday']
    )
