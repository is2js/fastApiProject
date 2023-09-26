from httpx_oauth.clients.google import GoogleOAuth2

from app.common.config import (
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
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


def get_oauth_clients():
    return [
        google_oauth_client,
    ]
