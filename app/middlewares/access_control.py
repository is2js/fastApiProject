import time
from typing import Optional

from starlette.datastructures import Headers, QueryParams
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.common.config import config
from app.common.consts import EXCEPT_PATH_REGEX, EXCEPT_PATH_LIST, SERVICE_PATH_REGEX, API_PATH_REGEX
from app.database.conn import db
from app.errors.exception_handler import exception_handler
from app.errors.exceptions import APIException, NotFoundUserException, NotAuthorized, DBException, \
    InvalidServiceQueryStringException, InvalidServiceHeaderException, NoKeyMatchException, \
    InvalidServiceTimestampException
from app.models import ApiKeys
from app.schemas import UserToken
from app.utils.auth_utils import url_pattern_check, decode_token
from app.utils.date_utils import D
from app.utils.logger import app_logger, db_logger
from app.utils.param_utils import hash_query_string


class AccessControl(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        await self.init_state(request)

        headers = request.headers
        cookies = request.cookies
        query_params = request.query_params
        url = request.url.path

        try:
            # (1) token 검사(user정보) 없는 except_path -> endpoint로
            # if await url_pattern_check(url, EXCEPT_PATH_REGEX):
            #     ...
            # if url in EXCEPT_PATH_LIST:
            #     ...
            # (3) services router들로 들어오면, headers(secret[key]) and querystring([access]key + timestamp)
            # ->  UserToken을 state.user에 담아 endpoint로
            if await url_pattern_check(url, SERVICE_PATH_REGEX):
            # if await url_pattern_check(url, SERVICE_PATH_REGEX):

                # (4) local(DEBUG=True) swagger로 qs + secret로는 swagger 테스트가 안되니,
                # -> swagger에서 삽입한 Authorization으로 인증(user_token)하도록 non_service(headers-Authorization에 jwt access token)로 처리되게 한다.
                if config.DEBUG:
                    request.state.user = await self.extract_user_token_by_non_service(headers, cookies)
                    response = await call_next(request)
                    await app_logger.log(request=request, response=response)
                    return response
                # print("service")
                request.state.user = await self.extract_user_token_by_service(headers, query_params)

            # (2) service아닌 API or 템플릿 렌더링
            #  -> token 검사 후 (request 속 headers(서비스아닌api) or cookies(템플릿렌더링)) -> UserToken을 state.user에 담아 endpoint로
            # elif await url_pattern_check(url, API_PATH_REGEX):
            elif not await url_pattern_check(url, '/api/v[0-9]+/auth') and await url_pattern_check(url, API_PATH_REGEX):
                request.state.user = await self.extract_user_token_by_non_service(headers, cookies)

            #### 쿠기가 있어도, service(qs + headers -> user_token) /api접속(headers -> user_token)이 아닐시에만 -> 쿠키로그인(cookie -> route에서 주입user객체) 시에는 그냥 넘어간다.
            # elif "Authorization" in cookies.keys():
            #     pass
            #
            # else:
            #     raise NotAuthorized()

            response = await call_next(request)
            # 응답 전 logging
            if url != "/":
                await app_logger.log(request=request, response=response)

        except Exception as e:
            # handler를 통해 정의하지 않은 e라면 -> 기본 500의 APIException으로 변환되게 된다.
            error: APIException = await exception_handler(e)

            # JSONResponse의 content=로 넣을 error 객체를 dict로 변환한다.
            error_dict = dict(
                status=error.status_code,
                code=error.code,
                message=error.message,
                detail=error.detail,
            )

            response = JSONResponse(status_code=error.status_code, content=error_dict)
            # logging
            if isinstance(error, DBException):
                # APIException의 하위 DBException class부터 검사하여 해당하면 db_logger로 찍기
                await db_logger.log(request, error=error)
            else:
                await app_logger.log(request, error=error)
            return response

        else:
            return response

    @staticmethod
    async def init_state(request):
        request.state.req_time = D.datetime()  # 시작시간 로깅을 위해 datetime 저장
        request.state.start = time.time()  # endpoint직전 마지막 미들웨어로서, 각 endpoint들 처리시간이 얼마나 걸리는지 확인을 위해
        request.state.inspect = None  # 핸들링 안되는 500 에러 -> 어떤 파일/function/몇번째 줄인지 확인하기 위해, 로깅용 변수 -> 나중에 sentry로 5000개까지 에러를 무료 활용할수 있다.
        request.state.service = None
        request.state.is_admin_access = None
        request.state.user = None  # token 디코딩 후 나오는 user정보를 넣어줄 예정이다.
        # 로드밸런서를 거칠 때만 "x-forwarded-for", local에서는  request.client.host에서 추출
        ip = request.headers["x-forwarded-for"] if "x-forwarded-for" in request.headers.keys() else request.client.host
        request.state.ip = ip.split(",")[0] if "," in ip else ip

    @staticmethod
    async def extract_user_token_by_non_service(headers: Headers, cookies: dict[str, str]):
        # [1] api 접속 -> headers에 token정보
        # if "Authorization" in headers.keys():
        if "authorization" in headers.keys() or "Authorization" in headers.keys():
            token = headers.get("Authorization")
        # [2] 템플릿 레더링 -> cookies에서 token정보
        # elif "Authorization" in cookies.keys() or "authorization" in cookies.keys():
        # 템플릿 쿠키 검사1) 키가 없으면 탈락
        # cookies['Authorization'] = \
        #     'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MiwiZW1haWwiOiJ1c2VyQGV4YW1wbGUuY29tIiwibmFtZSI6bnVsbCwicGhvbmVfbnVtYmVyIjpudWxsLCJwcm9maWxlX2ltZyI6bnVsbCwic25zX3R5cGUiOm51bGx9.6cnlgT4xWyKh5JTXxhd2kN1hLT4fawhnyBsV3scvDzU'
        # token = cookies.get("Authorization")
        else:
            raise NotAuthorized()

        # updated_password
        user_token_info = await decode_token(token)
        # user_token_info = cookie_backend.get_strategy().read_token(token, fastapi_users.get_user_manager)

        return UserToken(**user_token_info)

    @staticmethod
    async def extract_user_token_by_service(headers: Headers, query_params: QueryParams,
                                            ):
        query_params_map: dict = dict(query_params)
        # key= & timestamp 모두 통과해야하는 조건 -> if not all (): raise
        if not all(query_key in ('key', 'timestamp') for query_key in query_params_map.keys()):
            raise InvalidServiceQueryStringException()

        # 2) secret_key를 headers의 'secret'으로 달고와야한다.
        if 'secret' not in headers.keys():
            raise InvalidServiceHeaderException()

        # 3) 이제 qs로 들어온 access_key를 db에서 조회해서 ApiKey객체 -> Onwer User객체를 가져온다
        # -> ApiKey객체는 headers로 들어온 secret(key)를 검증하기 위해 가져온다.
        # -> User객체는 최종 UserToken을 생성할 때 쓰이는 info고
        matched_api_key_with_owner = await AccessControl.get_api_key_with_owner(query_params_map)

        # 4) 프론트처럼 qs + db 속 secret key -> hashed secret을 만들어서 vs Headers 속 secret 과 비교한다
        # => front와 달리 request.query_params객체는 str(), dict()만으로 다 만들 수 있다.
        validating_secret = hash_query_string(
            str(query_params),
            matched_api_key_with_owner.secret_key,
        )
        # print("secret", headers['secret'], validating_secret)
        # secret DVQkg2OtwzhXumDTbgR2LCVosepCcOeE6nDmrWHPu0g= DVQkg2OtwzhXumDTbgR2LCVosepCcOeE6nDmrWHPu0g=
        if headers['secret'] != validating_secret:
            raise InvalidServiceHeaderException()

        # 5) 요청이 서버kst시간의 1분전 ~ 1분후 사이의 요청이어야한다.
        current_timestamp_kst = int(D.datetime(diff_hours=9).timestamp())
        if not (current_timestamp_kst - 60 < int(query_params_map["timestamp"]) < current_timestamp_kst + 60):
            raise InvalidServiceTimestampException()

        return UserToken.model_validate(matched_api_key_with_owner.user)

    # TODO: redis cache
    @staticmethod
    async def get_api_key_with_owner(query_params_map):

        # async with db.session() as session: # get_db가 async contextmanger일 때 -> db.session().__anext()__가 고장나버림
        # => asyncgenerator를 1개만 뽑아 쓰고 싶다면, async for를 쓰자.
        # async for session in db.session():

        async with db.scoped_session() as session:
            # print("session", session)

            matched_api_key: Optional[ApiKeys] = await ApiKeys.filter_by(
                session=session,
                access_key=query_params_map['key']
            ).first()

            # print("matched_api_key", matched_api_key)

            if not matched_api_key:
                raise NoKeyMatchException()

            # user객체는, relationship으로 가져온다. lazy인데, 2.0.4버전에서는 refresh로 relationship을 load할 수 있다.
            await session.refresh(matched_api_key, attribute_names=["user"])
            # print("matched_api_key.user", matched_api_key.user)

            if not matched_api_key.user:
                raise NotFoundUserException()

            return matched_api_key
