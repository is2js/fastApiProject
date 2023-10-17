from datetime import date
from typing import AsyncContextManager

import httpx
from fastapi_users import models
from fastapi_users.authentication import AuthenticationBackend, Transport, Strategy
from fastapi_users.types import DependencyCallable
from starlette.responses import Response

from app.models import Users
from app.errors.exceptions import OAuthProfileUpdateFailException


class OAuthBackend(AuthenticationBackend):
    OAUTH_NAME = ""

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
                # raise OAuthProfileUpdateFailException(obj=user, exception=e)
                raise e

        return strategy_response

    async def get_profile_info(self, access_token):
        return dict()

    def get_access_token(self, user: Users):
        for oauth_account in user.oauth_accounts:
            if oauth_account.oauth_name == self.get_oauth_name():
                return oauth_account.access_token

        return None

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

    def get_oauth_name(self):
        return self.OAUTH_NAME
