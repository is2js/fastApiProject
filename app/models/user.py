from __future__ import annotations

import json
import random
import string
from typing import Optional, List
from uuid import uuid4

from fastapi_users_db_sqlalchemy import (
    SQLAlchemyBaseUserTable,
    SQLAlchemyBaseOAuthAccountTable,
)
from google.auth import exceptions
from google.auth.transport import requests as google_auth_requests
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy import Column, Enum, String, Boolean, Integer, ForeignKey, DateTime, func, JSON
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from app.common.consts import MAX_API_KEY_COUNT, MAX_API_WHITE_LIST_COUNT
from app.errors.exceptions import MaxAPIKeyCountException, MaxWhiteListCountException, NoKeyMatchException

from app.models.base import BaseModel
from app.models.enums import UserStatus, ApiKeyStatus, SnsType, Gender, RoleName, Permissions
from app.utils.date_utils import D


# class Users(BaseModel):
class Users(BaseModel, SQLAlchemyBaseUserTable[int]):
    status = Column(Enum(UserStatus), default=UserStatus.ACTIVE)
    # email = Column(String(length=255), nullable=True, unique=True)
    # pw = Column(String(length=2000), nullable=True)
    name = Column(String(length=255), nullable=True)
    phone_number = Column(String(length=20), nullable=True, unique=True)
    profile_img = Column(String(length=1000), nullable=True)
    # sns_type = Column(Enum("FB", "G", "K"), nullable=True,)
    sns_type = Column(Enum(SnsType), nullable=True, )
    marketing_agree = Column(Boolean, nullable=True, default=True)

    sns_token = Column(String(length=64), nullable=True, unique=True)
    nickname = Column(String(length=30), nullable=True)
    gender = Column(Enum(Gender), nullable=True)

    # age = Column(Integer, nullable=True, default=0)
    # birthday = Column(String(length=20), nullable=True)
    # kakao age_range(연령대)
    # 1~9: 1세 이상 10세 미만
    # 10~14: 10세 이상 15세 미만
    # 15~19: 15세 이상 20세 미만
    # 20~29: 20세 이상 30세 미만
    # 80~89: 80세 이상 90세 미만
    # 90~: 90세 이상
    age_range = Column(String(length=5), nullable=True)  # 카카오 형식인데, 구글 등에서 변환하길.
    birthyear = Column(String(length=4), nullable=True)  # kakao는 '출생연도'가 비즈니스 아니면 동의화면 권한없음. 구글에서는 'year'로 바로 들어옴
    birthday = Column(String(length=4), nullable=True)  # 1218. 구글에서는 'month', 'day'를 합해서 넣기

    # last_seen = Column(DateTime, server_default=func.now(), nullable=True)
    # => db서버의 시간대(KST)로 들어가버림.
    last_seen = Column(DateTime, default=func.utc_timestamp(), nullable=True)

    oauth_accounts = relationship(
        "OAuthAccount", lazy="joined",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    api_keys = relationship("ApiKeys", back_populates="user",
                            cascade="all, delete-orphan",
                            lazy=True  # 'select'로서 자동load아님. fastapi-users에서는 내부 join후 처리함.
                            )

    # 1. many에 fk를 CASCADE or 안주고 달아준다.
    # role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)

    # 2. many.one 을 단수로 쓰기 위해 uselist=false로 relation을 생성한다.
    # 3. lazy 전략 선택
    # => 추가쿼리를 날리기위한 Query객체 반환 dynamic(안씀) VS eagerload용 default 'select' VS 자동load용 'subquery', 'selectin', 'joined'
    # => 자동load시 대상이 1) many-> 'joined', 2) one -> 'subquery' or 'selectin' 선택
    role = relationship("Roles",  # back_populates="user",
                        foreign_keys=[role_id],
                        uselist=False,
                        lazy='subquery',  # lazy: _LazyLoadArgumentType = "select",
                        )

    def get_oauth_access_token(self, sns_type: SnsType):
        """
        lazy="joined"되어 session 없이, oauth_accounts 모델에서 특정 oauth의 access_token을 얻는 메서드
        """
        for existing_oauth_account in self.oauth_accounts:
            if existing_oauth_account.oauth_name == sns_type.value:
                return existing_oauth_account.access_token

        return None

    def get_oauth_account(self, sns_type: SnsType) -> Optional[OAuthAccount]:
        """
        lazy="joined"되어 session 없이, oauth_accounts 모델에서 특정 oauth의 access_token을 얻는 메서드
        """
        for existing_oauth_account in self.oauth_accounts:
            if existing_oauth_account.oauth_name == sns_type.value:
                return existing_oauth_account

        return None

    @hybrid_property
    def role_name(self) -> RoleName:
        """
        lazy='subquery' 되어 자동 load되는 Roles객체의 name(Enum-RoleName)을 바로 조회하여
        -> User Response Schema (UserRead)에 Roles-name필드 type(RoleName)으로 정의할 수 있게 된다.
        """
        return self.role.name

    def has_permission(self, permission: Permissions) -> bool:
        """
        lazy='subquery' 되어 자동 load되는 Roles객체의 total_permission 합을 조회하여, 단독 Permission과 int비교
        @permission_required( ) 에서 사용될 예정.
        """
        #  9 > Permissions.CLEAN # True # int Enum은 int와 비교 가능하다.(자동 value로 비교)
        return self.role.permission >= permission

    def has_role(self, role_name: RoleName) -> bool:
        """
        lazy='subquery' 되어 자동 load되는 Roles객체의 permission을 조회하여,
        @role_required( ) 에서 사용될 예정.
        """
        return self.has_permission(role_name.max_permission)

    async def get_google_creds(self) -> Optional[Credentials]:
        """
        lazy='joined' 되어 자동 load되는 OAuthAccount 중 google정보 인 google_creds_json에서 creds를 Credentials객체로 추출
        -> 만약 유효하지 않거나 refresh까지 실패한다면, None을 반환
        """
        google_account: OAuthAccount = self.get_oauth_account(SnsType.GOOGLE)
        if not (google_account and (creds := google_account.google_creds_json)):
            return None

        stored_creds = json.loads(creds)

        # to_json()으로 들어갔떤 것을 다시 load하면 datetime으로 복구가 안된 상태임  => 미리 빼서 저장해놨던 필드를 사용하여 덮어씀.
        # Get expirery so we can figure out if we need a refresh
        if google_account.google_creds_expiry is not None:
            stored_creds["expiry"] = google_account.google_creds_expiry
        else:
            stored_creds["expiry"] = D.datetime()

        # for test
        # stored_creds["expiry"] = D.datetime()

        # Drop timezone info
        # stored_creds['expiry'] = stored_creds['expiry'].replace(tzinfo=None)

        creds = Credentials(**stored_creds)

        if creds.expired:
            try:
                http_request = google_auth_requests.Request()  # google.auth.transport의 패키지(not module) requests(모듈)
                creds.refresh(http_request)

                # for test
                # raise exceptions.RefreshError()

                # 성공하면, 변화된 expity와 .to_json() 및 last_refreshed를 업데이트해야한다.
                await google_account.update(
                    auto_commit=True,
                    google_creds_json=creds.to_json(),
                    google_creds_expiry=creds.expiry,
                    google_creds_last_refreshed=D.datetime(),
                )

            except exceptions.RefreshError:
                # refresh 실패했다면, 해당 creds.token을 revoke 시키고, db에서도 google_creds_json만 None으로(나머지2개는 기록)
                # -> get_google_creds()를 return None이 되어버린다.

                revoke = requests.post(
                    'https://oauth2.googleapis.com/revoke',
                    params={'token': creds.token},
                    headers={'content-type': 'application/x-www-form-urlencoded'}
                )

                await google_account.update(
                    auto_commit=True,
                    google_creds_json=None,
                    # google_creds_expiry=None, # early return None의 기준이 google_creds_json필드여서, 실패 기록을 남겨둔다.
                    # google_creds_last_refreshed=None, # 실패 기록을 남겨둔다.
                )

                return None

        return creds

    @property
    async def google_creds_scopes(self) -> Optional[List[str]]:
        """
        lazy='joined' 되어 자동 load되는 OAuthAccount 중 google정보 인 google_creds_json에서 scopes를 확인한다.
        """
        creds = await self.get_google_creds()
        return creds.scopes if creds else None

    async def has_google_creds_and_scopes(self, google_scopes: List[str]) -> bool:
        """
        lazy='joined' 되어 자동 load되는 OAuthAccount 중 google정보 인 google_creds_json에서 scopes를 확인한다.
        @aouth_required(SnsType.GOOGLE, scopes= ) 에서 사용될 예정 이미 요청하여 creds를 가지고 있는지 확인용
        """
        if creds_scopes := await self.google_creds_scopes:
            has_scopes = all(scope in creds_scopes for scope in google_scopes)
            return has_scopes

        return False

    async def get_google_service(self, service_name: str, api_version: str = 'v3'):
        creds = await self.get_google_creds()

        if not creds:
            return None

        service = build(service_name, api_version, credentials=creds)

        return service


class OAuthAccount(BaseModel, SQLAlchemyBaseOAuthAccountTable[int]):
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user = relationship("Users", back_populates="oauth_accounts",
                        foreign_keys=[user_id],
                        uselist=False,
                        )

    # 추가 additional_scope 에 대한요청 -> 콜백 -> usermanager로 들어옴 -> creds 생성후 관련정보 저장
    google_creds_json = Column(JSON,
                               nullable=True)  # 결국엔 to_json()은 json.dump( dict )로 변환된 string을 받는 것 -> 꺼낼 땐 json.load( string_dict )필요
    google_creds_expiry = Column(DateTime, nullable=True)
    google_creds_last_refreshed = Column(DateTime, nullable=True)


class Roles(BaseModel):
    name = Column(Enum(RoleName), default=RoleName.USER, unique=True, index=True)
    default = Column(Boolean, default=False, index=True)
    permission = Column(Integer, default=0)

    @classmethod
    async def insert_roles(cls, session: AsyncSession = None):
        """
        app 구동시, 미리 DB 삽입 하는 메서드
        """
        for role_name in RoleName:

            if await cls.filter_by(name=role_name).exists():
                continue

            await cls.create(
                session=session,
                auto_commit=True,
                name=role_name,
                permission=role_name.total_permission,
                default=(role_name == RoleName.USER)
            )

    def has_permission(self, permission):
        # self.perm == perm의 확인은, (중복int를 가지는 Perm도 생성가능하다고 생각할 수 있다)
        return self.permission >= permission

    # def _add_permission(self, total_permission):
    #     # 6) 해당 perm(같은int)을 안가지고 잇을때만 추가한다다
    #     if not self.has_role(total_permission):
    #         print(f"total_permission >> {total_permission}")
    #
    #         self.total_permission += total_permission


class ApiKeys(BaseModel):
    created_at = Column(DateTime, nullable=False, default=func.utc_timestamp())
    updated_at = Column(DateTime, nullable=False, default=func.utc_timestamp(), onupdate=func.utc_timestamp())

    access_key = Column(String(length=64), nullable=False, index=True)
    secret_key = Column(String(length=64), nullable=False)
    user_memo = Column(String(length=40), nullable=True)
    status = Column(Enum(ApiKeyStatus), default=ApiKeyStatus.ACTIVE)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user = relationship("Users", back_populates="api_keys",
                        foreign_keys=[user_id],
                        uselist=False,
                        )

    is_whitelisted = Column(Boolean, default=False)
    whitelists = relationship("ApiWhiteLists", back_populates="api_key",
                              cascade="all, delete-orphan"
                              )

    @classmethod
    async def check_max_count(cls, user, session=None):
        user_api_key_count = await cls.filter_by(session=session, user_id=user.id, status='active').count()
        if user_api_key_count >= MAX_API_KEY_COUNT:
            raise MaxAPIKeyCountException()

    @classmethod
    async def create(cls, session=None, user=None, **kwargs):
        # secret_key(랜덤40글자) 생성 by alnums + random
        alnums = string.ascii_letters + string.digits
        secret_key = ''.join(random.choices(alnums, k=40))

        # access_key( uuid4 끝 12개 + uuid4 전체)
        access_key = None
        while not access_key:
            access_key_candidate = f"{str(uuid4())[:-12]}{str(uuid4())}"
            exists_api_key = await cls.filter_by(session=session, access_key=access_key_candidate).exists()
            if not exists_api_key:
                access_key = access_key_candidate

        new_api_key = await super().create(session=session, auto_commit=True,
                                           user_id=user.id,
                                           secret_key=secret_key,
                                           access_key=access_key,
                                           **kwargs)
        return new_api_key

    @classmethod
    async def check_key_owner(cls, id_, user, session=None):
        """
        하위도메인 Apikey가 상위도메인 user에 속해있는지 확인
        -> 하위도메인에서 상위도메인의 fk를 이용해서 필터링해서 조회하여 있으면 해당됨.
        """
        exists_user_api_key = await cls.filter_by(session=session, id=id_, user_id=user.id).exists()
        if not exists_user_api_key:
            raise NoKeyMatchException()


class ApiWhiteLists(BaseModel):
    ip_address = Column(String(length=64), nullable=False)

    api_key_id = Column(Integer, ForeignKey("apikeys.id", ondelete="CASCADE"), nullable=False)
    api_key = relationship("ApiKeys", back_populates="whitelists",
                           foreign_keys=[api_key_id],
                           uselist=False,
                           )

    @classmethod
    async def check_max_count(cls, api_key_id, session=None):
        user_api_key_count = await cls.filter_by(session=session, api_key_id=api_key_id).count()
        if user_api_key_count >= MAX_API_WHITE_LIST_COUNT:
            raise MaxWhiteListCountException()
