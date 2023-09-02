import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.common.consts import EXCEPT_PATH_REGEX, EXCEPT_PATH_LIST
from app.errors.exception_handler import exception_handler
from app.errors.exceptions import APIException, NotFoundUserException, NotAuthorized
from app.schema import UserToken
from app.utils.auth_utils import url_pattern_check, decode_token
from app.utils.date_utils import D
from app.utils.loggers import app_logger


class AccessControl(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.req_time = D.datetime()  # 시작시간 로깅을 위해 datetime 저장
        # print(D.datetime())
        # print(D.date())
        # print(D.date_number())
        request.state.start = time.time()  # endpoint직전 마지막 미들웨어로서, 각 endpoint들 처리시간이 얼마나 걸리는지 확인을 위해
        request.state.inspect = None  # 핸들링 안되는 500 에러 -> 어떤 파일/function/몇번째 줄인지 확인하기 위해, 로깅용 변수 -> 나중에 sentry로 5000개까지 에러를 무료 활용할수 있다.
        request.state.service = None
        request.state.is_admin_access = None

        # 미들웨어 내에서 DB를 조회해서 user정보를 가져올 수 도 있지만, 안할 수 있다면 최대한 피한다.
        # - DB를 거치지 않고 user 인증 + 정보획득 하기 위해 jwt를 사용한다.
        # - 조회해야한다면 function(endpoint)레벨에서 하는게 좋다
        headers = request.headers
        cookies = request.cookies
        # print(headers)
        # print(cookies)

        request.state.user = None  # token 디코딩 후 나오는 user정보를 넣어줄 예정이다.
        # request.state.access_token = request.headers.get("Authorization")
        # print(request.state.access_token)

        # 로드밸런서를 거칠 때만 "x-forwarded-for", local에서는  request.client.host에서 추출
        ip = headers["x-forwarded-for"] if "x-forwarded-for" in headers.keys() else request.client.host
        request.state.ip = ip.split(",")[0] if "," in ip else ip
        # print(request.state.ip)

        url = request.url.path
        # print(url)

        try:
            # 통과(access) 검사 시작 ------------
            # (1) except_path url 검사 -> 해당시, token없이 접속가능(/docs, /api/auth ~ 등) -> token 검사 없이 바로 endpoint(await call_next(request)) 로
            if await url_pattern_check(url, EXCEPT_PATH_REGEX) or url in EXCEPT_PATH_LIST:
                response = await call_next(request)
                # 응답 전 logging -> except_path 중에서는 index를 제외하고 찍기
                if url != "/":
                    await app_logger.log(request=request, response=response)
                return response

            # (2) 토큰 검사 -> if api(/api시작)는 headers / else 템플릿은 cookie에서 검사
            # [1] api 접속 -> headers에 token정보 -> decode 후 user정보를 states.user에 심기
            if url.startswith('/api'):
                # api 검사1) api endpoint 접속은, 무조건 Authorization 키가 없으면 탈락
                request.state.access_token = headers.get("Authorization")
                if not request.state.access_token:
                    # return JSONResponse(status_code=401, content=dict(message="AUTHORIZATION_REQUIRED"))
                    raise NotAuthorized()
            # [2] 템플릿 레더링 -> cookies에서 token정보 -> decode 후 user정보를 states.user에 심기
            else:
                # 템플릿 쿠키 검사1) 키가 없으면 탈락

                # test ) 잘못된 토큰 박아서, decode_token 내부에러 확인하기
                cookies['Authorization'] = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MiwiZW1haWwiOiJ1c2VyQGV4YW1wbGUuY29tIiwibmFtZSI6bnVsbCwicGhvbmVfbnVtYmVyIjpudWxsLCJwcm9maWxlX2ltZyI6bnVsbCwic25zX3R5cGUiOm51bGx9.6cnlgT4xWyKh5JTXxhd2kN1hLT4fawhnyBsV3scvDzU'

                request.state.access_token = cookies.get("Authorization")
                if not request.state.access_token:
                    # return JSONResponse(status_code=401, content=dict(message="AUTHORIZATION_REQUIRED"))
                    raise NotAuthorized()

            # toekn -> request.state.access_token 저장 후 -> token decode -> user정보 추출 -> state.user 저장
            # - Authorization 키가 있을 때, Bearer를 떼어낸 순수 jwt token를 decode 했을 때의 user정보를 state.user에 담아준다.
            request.state.access_token = request.state.access_token.replace("Bearer ", "")
            user_token_info = await decode_token(request.state.access_token)
            # print(user_token_info)
            request.state.user = UserToken(**user_token_info)
            # print(request.state.user)

            # {'id': 26, 'email': 'user123@example.com', 'name': None, 'phone_number': None, 'profile_img': None, 'sns_type': None}
            #  id=26 email='user123@example.com' name=None phone_number=None profile_img=None sns_type=None
            response = await call_next(request)
            # 응답 전 logging
            await app_logger.log(request, response=response)

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
            await app_logger.log(request, error=error)

        return response
