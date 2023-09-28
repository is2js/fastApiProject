from httpx_oauth.clients import kakao
from httpx_oauth.clients.kakao import KakaoOAuth2

from app.common.config import KAKAO_CLIENT_ID, KAKAO_CLIENT_SECRET


# - BASE_SCOPE ["profile_nickname", "account_email"]
# - profile_image, gender, age_range, birthday

def get_kakao_client():
    return KakaoOAuth2(
        client_id=KAKAO_CLIENT_ID,  # 앱 - RESPT API 키
        client_secret=KAKAO_CLIENT_SECRET,  # 앱 > 보안 > CLIENT_SECRET
        scopes=kakao.BASE_SCOPES + ['profile_image', 'gender', 'age_range', 'birthday']
    )
