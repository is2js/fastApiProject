from datetime import date
from typing import cast, Dict, Any, Optional, List

from httpx_oauth.clients import google
from httpx_oauth.clients.google import GoogleOAuth2
from httpx_oauth.oauth2 import T

from app.common.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, config, ProdConfig
from app.errors.exceptions import GetOAuthProfileError

# BASE_SCOPES = [
#     "https://www.googleapis.com/auth/userinfo.profile",
#     "https://www.googleapis.com/auth/userinfo.email",
# ]

# 달력 조정 추가
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.calendarlist"
]

service_name_and_scopes_map = dict(
    calendar=CALENDAR_SCOPES,
)


def google_scopes_to_service_name(google_scopes: List[str]):
    for service_name, mapped_scopes in service_name_and_scopes_map.items():
        if all(scope in mapped_scopes for scope in google_scopes):
            return service_name
    return None


class GoogleClient(GoogleOAuth2):

    # 자체 콜백을 위해, backend에만 정의해놨던 것을, client에도 1
    @staticmethod
    def calculate_age_range(year: [str, int], month: [str, int], day: [str, int]):
        if isinstance(year, str):
            year = int(year)
        if isinstance(month, str):
            month = int(month)
        if isinstance(day, str):
            day = int(day)

        # 1. age 계산 (month, day)를 tuple비교로, 지났으면 0(False), 안지났으면 -1(True) 빼준다.
        today = date.today()
        age = today.year - year - ((today.month, today.day) < (month, day))
        # print(age)
        # 2. age로 kakao양식의 age_range 반환해주기
        if 1 <= age < 10:
            age_range = "1~9"
        elif 10 <= age < 15:
            age_range = "10~14"
        elif 15 <= age < 20:
            age_range = "15~19"
        elif 20 <= age < 30:
            age_range = "20~29"
        elif 30 <= age < 40:
            age_range = "30~39"
        elif 40 <= age < 50:
            age_range = "40~49"
        elif 50 <= age < 60:
            age_range = "50~59"
        elif 60 <= age < 70:
            age_range = "60~69"
        elif 70 <= age < 80:
            age_range = "70~79"
        elif 80 <= age < 90:
            age_range = "80~89"
        else:
            age_range = "90~"

        return age_range

    # 자체 콜백을 위해, backend에만 정의해놨던 것을, client에도 2
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
                field_data_list = data.get(field, None)
                if not field_data_list:
                    continue

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

    async def get_authorization_url(self, redirect_uri: str, state: Optional[str] = None,
                                    scope: Optional[List[str]] = None, extras_params: Optional[T] = None,
                                    for_sync: bool = False,  # google refresh 토큰을 지속 얻기 위한 query params 추가
                                    ) -> str:
        """
        구글 로그인 성공시 refresh token을 받기 위해, authroization_url에 파라미터를 추가하기 위해 재정의

        """
        # https://hyeonic.github.io/woowacourse/dallog/google-refresh-token.html#%E1%84%8B%E1%85%A5%E1%86%B7%E1%84%80%E1%85%A7%E1%86%A8%E1%84%92%E1%85%A1%E1%86%AB-google
        # "access_type=offline"

        # 운영 환경: Refresh Token 발급을 위해 accept_type을 offline으로 설정한다. 단 최초 로그인에만 Refresh Token을 발급 받기 위해
        #  - prompt는 명시하지 않는다.
        # 개발 환경: 개발 환경에서는 매번 DataBase가 초기화 되기 때문에 Refresh Token을 유지하여 관리할 수 없다. 테스트를 위한 추가적인 Google Cloud Project를 생성한 뒤, accept_type을 offline으로,
        #  - prompt는 consent로 설정하여 매번 새롭게 Refresh Token을 받도록 세팅한다.
        # #정리

        if extras_params is None:
            extras_params = {}

        if for_sync:
            refresh_token_params = {
                'access_type': 'offline',  # 이 옵션을 추가하면, browser 최초 로그인시에만 refresh token을 최초 1회만 발급해준다.
                'prompt': 'consent',  # 최초1회 발급하는 refresh token -> 동의화면을 띄워 매번 받게 함. -> Prod환경 아닌경우만 적용 (X, 취소) -> for_sync인 경우 항상!!
                # 'include_granted_scopes': 'true',  # 기존 동의받은 scope를 재확인 + application의 모든 권한을 요구한다.
            }

            # 운영환경이 아닐 때만, 매번 동의화면 띄워서 -> 동의화면 띄우기 -> 매번 refresh 토큰 받도록 설정
            # => &prompt=consent 옵션이 사라지는 순간, 로그아웃 후, 직접 로그인창을 통해 로그인해야 refresh token이 access_type=offline 하에 발급된다.
            # => 즉, 브라우저 자동 로그인 기간동안에는, 동의화면 없이, 넘어가서 refresh token이 발급안된다.
            # 테스트 결과 이미 browser에 로그인되어 인증정보가 박힌 상태로서 -> 로그인 및 동의화면 안 뜰 때, refresh 토큰 발급이 안된다.
            # => sync를 위한 경우 무조건 refresh token이 발급되어야하므로, Prod 환경에서도 추가해준다.
            # if not isinstance(config, ProdConfig):
            #     refresh_token_params = refresh_token_params | {'prompt': 'consent'}

            extras_params = {**extras_params, **refresh_token_params}

        authorization_url = await super().get_authorization_url(redirect_uri, state, scope, extras_params)

        # {
        #   "data": {
        #     "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?~~access_type=offline&prompt=consent"
        #   },
        #   "version": "1.0.0"
        # }

        return authorization_url


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
            # 달력 조정 추가
            # "https://www.googleapis.com/auth/calendar",
            # "https://www.googleapis.com/auth/calendar.events",
        ])
