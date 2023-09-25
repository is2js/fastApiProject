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
        "https://www.googleapis.com/auth/userinfo.profile",  # 구글 클라우드에서 설정한 scope
        "https://www.googleapis.com/auth/userinfo.email",
        "openid"
    ])


def get_oauth_clients():
    return [
        google_oauth_client,
    ]