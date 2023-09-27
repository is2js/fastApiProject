import json
from abc import abstractmethod
from datetime import date
from typing import AsyncContextManager, cast, Any, Dict

import httpx
from fastapi_users import models
from fastapi_users.authentication import AuthenticationBackend, Strategy, Transport
from fastapi_users.types import DependencyCallable
from httpx_oauth.clients import google, kakao
from httpx_oauth.clients.kakao import PROFILE_ENDPOINT
from starlette.responses import Response

from app.models import Users
from app.errors.exceptions import GetOAuthProfileError, OAuthProfileUpdateFailException
from app.libs.auth.strategies import get_jwt_strategy
from app.libs.auth.transports import get_cookie_transport, get_bearer_transport


class OAuthBackend(AuthenticationBackend):

    def __init__(
            self,
            name: str,
            transport: Transport,
            get_strategy: DependencyCallable[Strategy[models.UP, models.ID]],
            has_profile_callback: bool = False,  # 추가 프로필 요청 여부
    ):
        super().__init__(name, transport, get_strategy)
        self.has_profile_callback = has_profile_callback

        # 추가 정보요청을 위해 추가
        self.request_headers = {
            "Accept": "application/json",
        }

    # 추가정보 요청용 client
    @staticmethod
    def get_httpx_client() -> AsyncContextManager[httpx.AsyncClient]:
        return httpx.AsyncClient()

    # 등록완료/로그인완료된 user객체를 컨트롤 할 수 있다.
    # async def login(self, strategy: Strategy[models.UP, models.ID], user: models.UP) -> Response:
    async def login(self, strategy: Strategy[models.UP, models.ID], user: Users) -> Response:
        strategy_response = await super().login(strategy, user)

        # 프로필 정보 추가 요청
        if self.has_profile_callback and (access_token := self.get_access_token(user)):
            try:
                # 추가정보가 들어올 때만, user.update()
                if profile_info := await self.get_profile_info(access_token):
                    # 자체 session으로 업데이트
                    # await user.update(auto_commit=True, **profile_info)
                    await user.update(auto_commit=True, **profile_info, sns_type=self.get_oauth_name())
            except Exception as e:
                raise OAuthProfileUpdateFailException(obj=user, exception=e)

        return strategy_response

    async def get_profile_info(self, access_token):
        return dict()

    def get_access_token(self, user: Users):
        for oauth_account in user.oauth_accounts:
            if oauth_account.oauth_name == self.get_oauth_name():
                return oauth_account.access_token

        return None

    def calculate_age_range(self, year: [str, int], month: [str, int], day: [str, int]):
        if isinstance(year, str):
            year = int(year)
        if isinstance(month, str):
            month = int(month)
        if isinstance(day, str):
            day = int(day)

        # 1. age 계산 (month, day)를 tuple비교로, 지났으면 0(False), 안지났으면 -1(True) 빼준다.
        today = date.today()
        age = today.year - year - ((today.month, today.day) < (month, day))
        print(age)
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

    @abstractmethod
    def get_oauth_name(self):
        raise NotImplementedError


class GoogleBackend(OAuthBackend):
    OAUTH_NAME = 'google'

    def get_oauth_name(self):
        return self.OAUTH_NAME

    async def get_profile_info(self, access_token):
        async with self.get_httpx_client() as client:
            response = await client.get(
                # PROFILE_ENDPOINT,
                google.PROFILE_ENDPOINT,
                # params={"personFields": "emailAddresses"},
                params={"personFields": "photos,birthdays,genders,phoneNumbers"},
                headers={**self.request_headers, "Authorization": f"Bearer {access_token}"},
            )

            if response.status_code >= 400:
                # raise GetIdEmailError(response.json())
                raise GetOAuthProfileError()

            data = cast(Dict[str, Any], response.json())

            # user_id = data["resourceName"]
            profile_info = dict()
            for field in "photos,birthdays,genders,phoneNumbers".split(","):
                field_data_list = data.get(field)
                primary_data = next(
                    (field_data for field_data in field_data_list if field_data["metadata"]["primary"])
                    , None
                )
                if not primary_data:
                    continue
                # 'photos' primary_data >> {'metadata': {'primary': True, 'source': {'type': '', 'id': ''}}, 'url': 'https://lh3.googleusercontent.com/a/ACg8ocKn-HgWhuT191z-Xp6lq0Lud_nxcjMRLR1eJ0nMhMS1=s100', 'default': True}
                if field == 'photos':
                    # "url": "https://lh3.googleusercontent.com/a/ACg8ocKn-HgWhuT191z-Xp6lq0Lud_nxcjMRLR1eJ0nMhMS1=s100",
                    profile_info['profile_img'] = primary_data['url']

                if field == 'birthdays':
                    birthday_info = primary_data['date']
                    # "date": {
                    #              "year": 1900,
                    #              "month": 00,
                    #              "day": 00
                    #          }
                    # profile_info['birthday'] = str(birthday_info['year']) + str(birthday_info['month']) + str(
                    #     str(birthday_info['day']))
                    profile_info['birthyear'] = str(birthday_info['year'])
                    profile_info['birthday'] = str(birthday_info['month']) + str(birthday_info['day'])
                    profile_info['age_range'] = self.calculate_age_range(birthday_info['year'], birthday_info['month'], birthday_info['day'])

                if field == 'genders':
                    # "value": "male",
                    profile_info['gender'] = primary_data['value']

                if field == 'phoneNumbers':
                    # "value": "010-yyyy-xxxx",
                    profile_info['phone_number'] = primary_data['value']

            return profile_info


google_cookie_backend = GoogleBackend(
    name="cookie",
    transport=get_cookie_transport(),
    get_strategy=get_jwt_strategy,
    has_profile_callback=True,
)

google_bearer_backend = GoogleBackend(
    name="bearer",
    transport=get_bearer_transport(),
    get_strategy=get_jwt_strategy,
    has_profile_callback=True,
)


def get_google_backends():
    return [
        google_cookie_backend, google_bearer_backend
    ]


class KakaoBackend(OAuthBackend):
    OAUTH_NAME = 'kakao'

    def get_oauth_name(self):
        return self.OAUTH_NAME

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
                PROFILE_ENDPOINT,
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

            if kakao_account.get('profile'):
                profile_info['profile_img'] = kakao_account['profile'].get('thumbnail_image_url', None)
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


kakao_cookie_backend = KakaoBackend(
    name="cookie",
    transport=get_cookie_transport(),
    get_strategy=get_jwt_strategy,
    has_profile_callback=True,
)

kakao_bearer_backend = KakaoBackend(
    name="bearer",
    transport=get_bearer_transport(),
    get_strategy=get_jwt_strategy,
    has_profile_callback=True,
)


def get_kakao_backends():
    return [
        kakao_cookie_backend, kakao_bearer_backend
    ]
