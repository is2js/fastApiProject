from abc import abstractmethod
from typing import AsyncContextManager, cast, Any, Dict

import httpx
from fastapi_users import models
from fastapi_users.authentication import AuthenticationBackend, Strategy, Transport
from fastapi_users.types import DependencyCallable
from httpx_oauth.clients import google, kakao
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
                    await user.update(auto_commit=True, **profile_info)
            except Exception as e:
                raise OAuthProfileUpdateFailException(obj=user, exception=e)

        return strategy_response

    def get_profile_info(self, access_token):
        return dict()

    def get_access_token(self, user: Users):
        for oauth_account in user.oauth_accounts:
            if oauth_account.oauth_name == self.get_oauth_name():
                return oauth_account.access_token

        return None

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
                    profile_info['birthday'] = str(birthday_info['year']) + str(birthday_info['month']) + str(
                        str(birthday_info['day']))

                if field == 'genders':
                    # "value": "male",
                    profile_info['gender'] = primary_data['value']

                if field == 'phoneNumbers':
                    # "value": "010-4600-6243",
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
