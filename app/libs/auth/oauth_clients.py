from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.clients.kakao import KakaoOAuth2, BASE_SCOPES

from app.common.config import (
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, KAKAO_CLIENT_ID, KAKAO_CLIENT_SECRET
)

# BASE_SCOPES = [
#     "https://www.googleapis.com/auth/userinfo.profile",
#     "https://www.googleapis.com/auth/userinfo.email",
# ]

google_oauth_client = GoogleOAuth2(
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    scopes=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.profile",  # 구글 클라우드 - 동의에서 설정한 범위
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/user.birthday.read",  # 추가 액세스 요청 3개 (전부 people api)
        "https://www.googleapis.com/auth/user.gender.read",
        "https://www.googleapis.com/auth/user.phonenumbers.read",
    ])

# scope 선택 (backend.login()에서 재요청할 것이므로 굳이 여기서 안해도 될듯 하긴 함.)
# - BASE_SCOPE ["profile_nickname", "account_email"]
# - profile_image, gender, age_range, birthday
kakao_oauth_client = KakaoOAuth2(
    client_id=KAKAO_CLIENT_ID,
    client_secret=KAKAO_CLIENT_SECRET,
    scopes=BASE_SCOPES + ['profile_image', 'gender', 'age_range', 'birthday']
)


def get_oauth_clients():
    return [
        google_oauth_client, kakao_oauth_client
    ]
