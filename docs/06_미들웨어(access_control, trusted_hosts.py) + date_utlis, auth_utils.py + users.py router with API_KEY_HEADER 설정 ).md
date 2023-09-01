### 미들 웨어

1. trusted_hosts -> 스탈렛에는 except_path가 없어서, AWS 로드밸런서가 헬스체크하기 위한 내부ip를 허용을 못해서 죽은 것으로 판단하게 되어 새로 정의
2. access_control -> 모든 요청에 대해서 token 검사
    - header에 있는 access_token을 검사한다
    - api가 아니라 template rendering시에는 endpoint 접속시에는 cookie에 있는 access_token을 검사한다
3. 전반적으로 3개의 미들웨어를 추가한다.
    - `AccessControl미들웨어`
    - `CORS미들웨어` -> 특정 도메인(abc.com)에서만 접속시킴. 개발중이라서 "*"로 열어놓는다. (어떤 method로 어떤header로든 접속가능)
        - 만약, 지정을 안한다면, front와 backend의 주소가 같아야만 요청할 수 있다.
    - `TrustedHost미들웨어`
    - **삽질포인트 -> add_middleware로 순서대로 추가시, stack을 채운 마지막의 미들웨어부터 작동**
        - 3번째 미들웨어 검사 -> 문제없으면 2번째 미들웨어 검사 -> 문제없으면 1번째 미들웨어 검사 -> endpoint view func으로 보냄
        - enpoint 응답결과 -> 1번째 -> 2번째 -> 3번째 미들웨어 -> 유저에게 응답
    - **이 때, 요청 전, 옵션을 1개 날리는데, access token을 가지고 있는 상태로서, `AccessControl`에 걸리기
      때문에, `AccessCotnrol 전에 CORS + allow_methods 등의 옵션`이 작동해야하며, 제일 먼저 `TrustedHost`가 작동해야하니**
        - **add순서는 `1. AccessControl -> 2. CORS 외 allowed옵션 -> 3. 가장 먼저 TrustedHost` 순으로 add한다.**

### 작성 시작

1. app > `middlewares`폴더를 만들고,  `access_control.py`를 만들고, `consts.py`에 `EXCEPT_PATH_LIST, EXCEPT_PATH_REGEX`를 정의해놓는다.
    - **`토큰을 안가져도 되는` index과, swagger관련 파일을 먼저 예외path로 걸어두고**
    - **뒤에 파라미터들이 붙는 것들은 regex으로, `토큰을 안가져도 되면서 & 해당 url로 시작`하는 path를 정의해둔다.**

```python
# consts.py
EXCEPT_PATH_LIST = ["/", "/openapi.json"]
EXCEPT_PATH_REGEX = "^(/docs|/redoc|/api/auth)"
```

2. **main.py add_router에 걸었던 `/auth` prefix를 router/auth.py 자체적으로 Router객체 생성시로, 옮기고 main.py에서는 `/api`로 prefix를 건다.**

```python
# main.py 

# route 등록
app.include_router(index.router)
app.include_router(auth.router, tags=["Authentication"], prefix="/api")
```

```python
# router/auth.py
router = APIRouter(prefix='/auth')
```

3. AccessControl 미들웨어에서 사용될 date관련 유틸을 app > `utils` > `date_utils.py`를 생성하여 정의한다.
    - **@classmethod들을 class D에 모아놓고, D.xxxx 로 사용하면 되며, `D객체 생성시 cls()로 내부에서 인스터싱 -> 생성자에서 현재시간 utc생성` 후 -> 메서드에  `diff`
      가 주어질 때, 그 차이**를 가져올 수 있게 한다.
    - datetime / date / int date 형태로 가져올 수 있게 3개의 메서드를 정의한다.

```python
from datetime import datetime, timedelta, date


class D:
    # class메서드들용으로서, 메서드 호출 -> 내부 cls() 인스터싱 -> 현재시각을 얻게 된다.
    def __init__(self) -> None:
        self.utc_now = datetime.utcnow()
        self.timedelta = 0

    @classmethod
    def datetime(cls, diff_hours: int = 0) -> datetime:
        # 차이시간이 0보다 크면 현재시각에 + / 음수면, 현재시각에서 - 한 datetime
        return cls().utc_now + timedelta(hours=diff_hours) if diff_hours > 0 else
        cls().utc_now - timedelta(hours=diff_hours)


# 위의 diff한 datetime을 date로 변환
@classmethod
def date(cls, diff_hours: int = 0) -> date:
    return cls.datetime(diff_hours=diff_hours).date()


# 위의 diff한 date를 문자열20220101로 변환 후 -> 정수 20220101로
@classmethod
def date_number(cls, diff_hours: int = 0) -> int:
    date_string = cls.date(diff_hours=diff_hours).strftime('%Y%m%d')
    return int(date_string)
```

4. 이제 main.py에서 미들웨어를 추가한다

```python
    # 미들웨어 추가
app.add_middleware(AccessControl)
```

5. middelwares > access_control.py에는 `starlette 내부의 BaseHTTPMiddleware`을 상속한 class여야한다.
    - **상속한 후, `async def dispatch`를 재정의해주면 된다.**

```python
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class AccessControl(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        pass
```

6. **일단 `request에 저장하고 싶은 값들을 None or 값으로 초기화`해서 변수로 선언해둔다.**
    - request.state.xxx에는 뭐든지 변수로 데이터를 저장할 수 있으며, endpoint view function에서도 사용할 수 있게 된다.
    - `return은 await로 call_next(request)`를 호출하면, 맨 마지막작동할 미드웨어니 endpoint로 갔다 올 것이다.

```python
from app.utils.date_utils import D


class AccessControl(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.req_time = D.datetime()  # 시작시간 로깅을 위해 datetime 저장
        print(D.datetime())
        print(D.date())
        print(D.date_number())
        request.state.start = time.time()  # endpoint직전 마지막 미들웨어로서, 각 endpoint들 처리시간이 얼마나 걸리는지 확인을 위해
        request.state.inspect = None  # 핸들링 안되는 500 에러 -> 어떤 파일/function/몇번째 줄인지 확인하기 위해, 로깅용 변수 -> 나중에 sentry로 5000개까지 에러를 무료 활용할수 있다.
        request.state.service = None
        request.state.is_admin_access = None

        request.state.user = None  # token 디코딩 후 나오는 user정보를 넣어줄 예정이다.
        # 미들웨어 내에서 DB를 조회해서 user정보를 가져올 수 도 있지만, 안할 수 있다면 최대한 피한다.
        # - DB를 거치지 않고 user 인증 + 정보획득 하기 위해 jwt를 사용한다.
        # - 조회해야한다면 function(endpoint)레벨에서 하는게 좋다
        headers = request.headers
        cookies = request.cookies
        print(headers, cookies)

        request.state.access_token = request.headers.get("Authorization")
        print(request.state.access_token)

        ip = request.headers["x-forwarded-for"] if "x-forwarded-for" in request.headers.keys() else request.client.host
        request.state.ip = ip.split(",")[0] if "," in ip else ip
        print(request.state.ip)

        url = request.url.path
        print(url)

        return await call_next(request)
```

7. **이상태로 create_app에 AcceesControl을dispatch에서 변수만 찍고 실행하면 -> 사이트 접속시 정보들이 print된다**
    - /docs에 접속시 미들웨어에서 받는 정보들

```shell
2023-08-31 17:26:29.059367
2023-08-31
20230831
Headers({'host': 'localhost:8010', 'connection': 'keep-alive', 'cache-control': 'max-age=0', 'sec-ch-ua': '"Chromium";v="116", "Not)A;Brand";v="24", "Google Chrome";v="116"', 'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"Windows"', 'upgrade-insecure-requests': '1', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36', 'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7', 'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'navigate', 'sec-fetch-user': '?1', 'sec-fetch-dest': 'document', 'accept-encoding': 'gzip, deflate, br', 'accept-language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7', 'cookie': 'Idea-43a2ccd8=e645287d-181f-4299-8928-915eab71aa99; Idea-43a2d097=3618530e-147c-4be9-a696-1e7ef177cec9; Pycharm-31d860e8=9e9eafe8-b981-463d-856c-aa547d42b500; Webstorm-ec31c39f=16fec2ba-b596-40b3-80b5-4f78706a7652; session=.eJwty8sKwjAQRuF3mXXxslBKViLoS4iEUH7CYGYaMilFxHd3Cm7P4fuQYo0Cs5RhFA4DNUxcGdopUGfN1t8Fx0uWxGU3zUID9WQvi6yxtjk3xxQeT8-QWlJH1CRwjY3sVxRXcLYY2n9dz7fxfqLvD5x7LOE.ZO3HHA.6IDkvMY2HFrKUXKBZof98fpDqs0'}) {'Idea-43a2ccd8': 'e645287d-181f-4299-8928-915eab71aa99', 'Idea-43a2d097': '3618530e-147c-4be9-a696-1e7ef177cec9', 'Pycharm-31d860e8': '9e9eafe8-b981-463d-856c-aa547d42b500', 'Webstorm-ec31c39f': '16fec2ba-b596-40b3-80b5-4f78706a7652', 'session': '.eJwty8sKwjAQRuF3mXXxslBKViLoS4iEUH7CYGYaMilFxHd3Cm7P4fuQYo0Cs5RhFA4DNUxcGdopUGfN1t8Fx0uWxGU3zUID9WQvi6yxtjk3xxQeT8-QWlJH1CRwjY3sVxRXcLYY2n9dz7fxfqLvD5x7LOE.ZO3HHA.6IDkvMY2HFrKUXKBZof98fpDqs0'}
None
172.25.0.1
/docs
INFO:     172.25.0.1:52456 - "GET /docs HTTP/1.1" 200 OK
2023-08-31 17:26:29.483442
2023-08-31
20230831
Headers({'host': 'localhost:8010', 'connection': 'keep-alive', 'sec-ch-ua': '"Chromium";v="116", "Not)A;Brand";v="24", "Google Chrome";v="116"', 'accept': 'application/json,*/*', 'sec-ch-ua-mobile': '?0', 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36', 'sec-ch-ua-platform': '"Windows"', 'sec-fetch-site': 'same-origin', 'sec-fetch-mode': 'cors', 'sec-fetch-dest': 'empty', 'referer': 'http://localhost:8010/docs', 'accept-encoding': 'gzip, deflate, br', 'accept-language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7', 'cookie': 'Idea-43a2ccd8=e645287d-181f-4299-8928-915eab71aa99; Idea-43a2d097=3618530e-147c-4be9-a696-1e7ef177cec9; Pycharm-31d860e8=9e9eafe8-b981-463d-856c-aa547d42b500; Webstorm-ec31c39f=16fec2ba-b596-40b3-80b5-4f78706a7652; session=.eJwty8sKwjAQRuF3mXXxslBKViLoS4iEUH7CYGYaMilFxHd3Cm7P4fuQYo0Cs5RhFA4DNUxcGdopUGfN1t8Fx0uWxGU3zUID9WQvi6yxtjk3xxQeT8-QWlJH1CRwjY3sVxRXcLYY2n9dz7fxfqLvD5x7LOE.ZO3HHA.6IDkvMY2HFrKUXKBZof98fpDqs0'}) {'Idea-43a2ccd8': 'e645287d-181f-4299-8928-915eab71aa99', 'Idea-43a2d097': '3618530e-147c-4be9-a696-1e7ef177cec9', 'Pycharm-31d860e8': '9e9eafe8-b981-463d-856c-aa547d42b500', 'Webstorm-ec31c39f': '16fec2ba-b596-40b3-80b5-4f78706a7652', 'session': '.eJwty8sKwjAQRuF3mXXxslBKViLoS4iEUH7CYGYaMilFxHd3Cm7P4fuQYo0Cs5RhFA4DNUxcGdopUGfN1t8Fx0uWxGU3zUID9WQvi6yxtjk3xxQeT8-QWlJH1CRwjY3sVxRXcLYY2n9dz7fxfqLvD5x7LOE.ZO3HHA.6IDkvMY2HFrKUXKBZof98fpDqs0'}
None
172.25.0.1
/openapi.json
```

- **아직 미완성이지만, 일단 다른 cors 와 trushedhost미들웨어의 기초를 작성하러 간다.**

8. **endpoint 직전의 `access_control` 전에, `cors`미들웨어가 먼저 작동되므로, 그 밑에 추가한다.**
    - cors미들웨어 등록시 `allow_origins, allow_credentials, allow_methods, allow_headers`를 등록해준다.
    - allow_origins는, `config.py`에 정의한 `ALLOW_SITE = "[*]"` 로서, 일단 모든 환경에서 모든 도메인을 접속가능하게 한다.
        - 원래는 환경별로 달라야해서, Local, ProgCOnfig에 각각 입력해준다.

```python
@dataclass
class LocalConfig(Config):
    PROJ_RELOAD: bool = True

    # 도커 서비스 mysql + 도커자체port 3306으로 접속
    # - host에 연결시에는 localhost + 13306
    DB_URL: str = "mysql+pymysql://travis:travis@mysql:3306/notification_api?charset=utf8mb4"

    # CORS    
    ALLOW_SITE = ["*"]


@dataclass
class ProdConfig(Config):
    PROJ_RELOAD: bool = False

    # CORS    
    ALLOW_SITE = ["*"]
```

9. CORS 미들웨어는 스탈렛에 있는 것을 가져와서 등록해준다.
    - 추가로 4가지 옵션을 추가해준다.

```python
from starlette.middleware.cors import CORSMiddleware


def create_app():
    # 미들웨어 추가 (실행순서는 반대)
    app.add_middleware(AccessControl)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOW_SITE,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

10. 이제 TrustdHostMiddleware를 추가한 뒤, 정의까지 해줘야한다.
    - **이 때는, ALLOW_SITE가 아닌 `TRUSTED_HOSTS 로서, 도메인을 allowed_hosts=옵션으로 추가해줘야하는데, conf에` 정의해야한다.
      추가로 `except_path에는 health체크용 url`도 명시해준다.**

```python
@dataclass
class LocalConfig(Config):
    PROJ_RELOAD: bool = True

    # 도커 서비스 mysql + 도커자체port 3306으로 접속
    # - host에 연결시에는 localhost + 13306
    DB_URL: str = "mysql+pymysql://travis:travis@mysql:3306/notification_api?charset=utf8mb4"

    # CORS
    ALLOW_SITE = ["*"]
    # TRUSTED_HOST
    TRUSTED_HOSTS = ["*"]


@dataclass
class ProdConfig(Config):
    PROJ_RELOAD: bool = False

    # CORS
    ALLOW_SITE = ["*"]
    # TRUSTED_HOST
    TRUSTED_HOSTS = ["*"]
```

- 다음으로 middlewares > `trusted_hosts.py`를 만든 뒤, class로 정의해주고, creat_app에서 추가해준다.
    - **이 때, 스탈렛의 TrustedHostMiddleware에서 `except_path`로직만 추가한 것으로, 복붙해서 사용하면 된다.**

```python
import typing

from starlette.datastructures import URL, Headers
from starlette.responses import PlainTextResponse, RedirectResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

ENFORCE_DOMAIN_WILDCARD = "Domain wildcard patterns must be like '*.example.com'."


class TrustedHostMiddleware:
    def __init__(
            self,
            app: ASGIApp,
            allowed_hosts: typing.Sequence[str] = None,
            except_path: typing.Sequence[str] = None,
            www_redirect: bool = True,
    ) -> None:
        if allowed_hosts is None:
            allowed_hosts = ["*"]
        if except_path is None:
            except_path = []
        for pattern in allowed_hosts:
            assert "*" not in pattern[1:], ENFORCE_DOMAIN_WILDCARD
            if pattern.startswith("*") and pattern != "*":
                assert pattern.startswith("*."), ENFORCE_DOMAIN_WILDCARD
        self.app = app
        self.allowed_hosts = list(allowed_hosts)
        self.allow_any = "*" in allowed_hosts
        self.www_redirect = www_redirect
        self.except_path = list(except_path)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.allow_any or scope["type"] not in ("http", "websocket",):  # pragma: no cover
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        host = headers.get("host", "").split(":")[0]
        is_valid_host = False
        found_www_redirect = False
        for pattern in self.allowed_hosts:
            if (
                    host == pattern
                    or (pattern.startswith("*") and host.endswith(pattern[1:]))
                    or URL(scope=scope).path in self.except_path
            ):
                is_valid_host = True
                break
            elif "www." + host == pattern:
                found_www_redirect = True

        if is_valid_host:
            await self.app(scope, receive, send)
        else:
            if found_www_redirect and self.www_redirect:
                url = URL(scope=scope)
                redirect_url = url.replace(netloc="www." + url.netloc)
                response = RedirectResponse(url=str(redirect_url))  # type: Response
            else:
                response = PlainTextResponse("Invalid host header", status_code=400)

            await response(scope, receive, send)

```

```python
# 미들웨어 추가 (실행순서는 반대)
app.add_middleware(AccessControl)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOW_SITE,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.TRUSTED_HOSTS, except_path=["/health"])
```

### 본격 auth_utils.py -> access_control 작성하기

#### utils / auth_utils.py

1. 기본 access_control에서 **except_path들은 token정보없이 바로 endpoint로 보내기 위해 먼저 검사하는데,**
    - `url_patter_check` 등의 기능이 추가되서 재정의하는 것인데, **나중에 decode_token()도 해야하니, 묶어서 넣을 `auth_utils.py`를 생성한다**

```python
# utils/auth_utils.py
import re


async def url_pattern_check(path, pattern):
    result = re.match(pattern, path)
    return True if result else False

# EXCEPT_PATH_REGEX = "^(/docs|/redoc|/api/auth)"
# if await url_pattern_check(url, EXCEPT_PATH_REGEX) or url in EXCEPT_PATH_LIST:
```

2. 이것과 별개로 **decode_token을 통해 user정보를 추출도 해야하므로, `async def decode_token()`도 미리 정의한다.**
    - 호출되는 곳에서 Bearer를 땐 token 문자열을 보내줄 것이다.
    - jwt + consts의 상수들을 이용한다.

```python
# utils/auth_utils.py
async def decode_token(token: str):
    """
    :param token:
    :return:
    """
    try:
        payload = jwt.decode(token, key=JWT_SECRET, algorithms=JWT_ALGORITHM)
        return payload
    except jwt.ExpiredSignatureError:
        raise Exception("ExpiredSignature Error")
    except jwt.InvalidTokenError:
        raise Exception("InvalidToken Error")
```

3. 기존에 auth.py에 정의해둔 `create_access_token 메서드`도 auth_utils.py로 옮겨준다.
    - async로 만들고, 호출되는 곳에서 await를 적어 비동기로 만든다.

4. **auth.py에 있던 조회쿼리 exists_user_email 메서드도 Users 모델로 옮기자.**
    - 2.0 버전으로 일단 작성해놓고, async도 달아준다.
    - **조회메서드를 `일단은 session은 필수로 주입`하도록 만들어놓는다.**
    - 기존

```python
async def exists_user_email(email: str):
    user = Users.get(email=email)
    return True if user else False


# 검증2) email이 이미 존재하면 안된다.
exists_email = await exists_user_email(user_register_info.email)
if exists_email:
    return JSONResponse(status_code=400, content=dict(message="EMAIL_EXISTS"))
```

- 변경

```python
class Users(BaseModel):
    # ... 
    @classmethod
    async def get_by_email(cls, session: Session, email: str):
        return session.scalars(
            select(cls)
            .where(cls.email == email)
        ).first()
```

```python
# 검증2) email이 존재 해야만 한다.
user = await Users.get_by_email(session, user_info.email)
if not user:
    return JSONResponse(status_code=400, content=dict(message="NO_MATCH_USER"))

```

#### AcccesControl

1. 기본적으로 acccess_control의 첫번째 로직은, `EXCEPT_PATH_XXXX`에 대한 url 체크를 했을 때, **허용되는 범위에 있을 때는 token정보
   추출없이 `response = await call_next(request)`로 `에러내지않고 requests.state에 데이터 담은 체 return`한다**
    - **즉, early return 검사를 한다.**

```python
class AccessControl(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # ...
        url = request.url.path
        # 통과(access) 검사 시작 ------------
        # (1) except_path url 검사 -> 해당시, token없이 접속가능(/docs, /api/auth ~ 등) -> token 검사 없이 바로 endpoint(await call_next(request)) 로
        if await url_pattern_check(url, EXCEPT_PATH_REGEX) or url in EXCEPT_PATH_LIST:
            response = await call_next(request)
            # 나중에 로그 찍기
            return response
```

4. except path로서 url이 통과되었다면, **token**검사를 해야한다.
    - **`api`인 경우, `headers`에 token을 확인하고, `템플릿 렌더링`의 경우, `cookies`에서 token을 확인해야한다.**
    - **2가지 경우 모두, token decode를 해야하니, token 추출부분의 출저만 `url에 prefix '/api'`로 시작하는지 검사해서 구분한다**
    - cookies에서 심을 front가 없으니 임시로 심을 준비를 한다.
    - **2가지 경우 모두, `request.state.accees_token`에 Bearer ~ 토큰을 심어놓는다. 만약 키가 없다면 에러를 낸다.**

```python
# (2) 토큰 검사 -> if api(/api시작)는 headers / else 템플릿은 cookie에서 검사
# [1] api 접속 -> headers에 token정보 -> decode 후 user정보를 states.user에 심기
if url.startswith('/api'):
    print('api request')
    # api 검사1) api endpoint 접속은, 무조건 Authorization 키가 없으면 탈락
    request.state.access_token = headers.get("Authorization")
    if not request.state.access_token:
        # raise
        return JSONResponse(status_code=401, content=dict(message="AUTHORIZATION_REQUIRED"))
# [2] 템플릿 레더링 -> cookies에서 token정보 -> decode 후 user정보를 states.user에 심기
else:
    print('not api(template 등) request')
    cookies["Authorization"] =
    "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MjYsImVtYWlsIjoidXNlcjEyM0BleGFtcGxlLmNvbSIsIm5hbWUiOm51bGwsInBob25lX251bWJlciI6bnVsbCwicHJvZmlsZV9pbWciOm51bGwsInNuc190eXBlIjpudWxsfQ.jT1uIVJtcywC_VxUDLmkT6jorf7E-dgtXu12S_JdSiw"

# 템플릿 쿠키 검사1) 키가 없으면 탈락
request.state.access_token = cookies.get("Authorization")
if not request.state.access_token:
    # raise
    return JSONResponse(status_code=401, content=dict(message="AUTHORIZATION_REQUIRED"))
```

5. 이후 `request.state.access_token`에 달린 Bearer를 뗀 token을 `decode_token()`에 넣어주는데,
    - **토큰 유효성 / 만료가 확인되면 내부에서 error에 raise되므로, `try/except`를 씌우고, 에러가 발생하면, `str(e)`로 raise Exception시 적어준 메세지를 띄워줄 수
      있다.**
    - 현재는 토큰에러만 내부에서 작동하므로 401 status_code로 내려보내준다.
    - **decode_token이 성공하면, user_token_info dictionary가 반환되는데, 이것을 `UserToken` Schema의 생성자에 넣어서, `request.state.user`에
      저장해준다.**

```python
# (2) 토큰 검사 -> if api(/api시작)는 headers / else 템플릿은 cookie에서 검사
try:
    # [1] api 접속 -> headers에 token정보 -> decode 후 user정보를 states.user에 심기
    if url.startswith('/api'):
    # ...
    # [2] 템플릿 레더링 -> cookies에서 token정보 -> decode 후 user정보를 states.user에 심기
    else:
    # ...

    # toekn -> request.state.access_token 저장 후 -> token decode -> user정보 추출 -> state.user 저장
    # - Authorization 키가 있을 때, Bearer를 떼어낸 순수 jwt token를 decode 했을 때의 user정보를 state.user에 담아준다.
    request.state.access_token = request.state.access_token.replace("Bearer ", "")
    user_token_info = await decode_token(request.state.access_token)
    print(user_token_info)
    request.state.user = UserToken(**user_token_info)
    print(request.state.user)

    response = await call_next(request)
    # 나중에 응답 전 log
    return response
except Exception as e:
    return JSONResponse(status_code=401, content=dict(message=f"{str(e)}"))
```

#### access control 테스트

1. 현재 index 나 docs 나 `/api/auth의 router들`에 들어가면, `except_path`에 포함되서 token추출없이 바로 응답되는지 확인한다.
    - docs에서 `email/pw를 기억해서 token`을 받아두면서, `except_path 검사`에 걸리는지 확인한다.

```python
{
    "email": "test@example.com",
    "pw": "test"
}

{
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MSwiZW1haWwiOiJ0ZXN0QGV4YW1wbGUuY29tIiwibmFtZSI6bnVsbCwicGhvbmVfbnVtYmVyIjpudWxsLCJwcm9maWxlX2ltZyI6bnVsbCwic25zX3R5cGUiOm51bGx9.tQXBiz35NPed9bsxZkuPGe6vRoKEY-wjWeY3_CfSx-k"
}

# except path - no url check
```

2. 이제 except_path에 안걸리면서( not /docs, /api/auth ), `1) /api`로 시작하지 않는, `2) 템플릿 - 쿠키에서 토근 추출`을 하는지 확인하기 위해
    1. `/api`로 시작하지 않는 index.py의 `/test`라우트를 하나 만들고, request.state.user를 추출을 시도해보자. /docs에서 접속한다.
        - **api가 아니므로 템플릿 구간으로 넘어가며, cookie에서 authorization key가 없으므로 JsonResponse`AUTHORIZATION_REQUIRED`가 반환되어야한다.**
        ```python
        @router.get("/test")
        async def test(request: Request):
         
            print("request.state.user", request.state.user)
         
            current_time = datetime.utcnow()
            return Response(f"Notification API (UTC: {current_time.strftime('%Y.%m.%d %H:%M:%S')})")
        ```
        ```
        # not api(template �벑) request
 
        {
           "message": "AUTHORIZATION_REQUIRED"
         }
        ```
    2. register test@example.com/test의 `토큰`을 `access_control cookie 진입시`코드에 미리 박아두고, user정보를 추출하게 해본다.
        ```python
        if url.startswith('/api'):
            print('api request')
        else:
            print('not api(template 등) request')
            # test를 위해 Authorization 키에 토큰 박아두기 -> 아직 /api/auth가 아닌 /api 시작 endpoint가 없기 때문에,
            cookies["Authorization"] = \
                "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MSwiZW1haWwiOiJ0ZXN0QGV4YW1wbGUuY29tIiwibmFtZSI6bnVsbCwicGhvbmVfbnVtYmVyIjpudWxsLCJwcm9maWxlX2ltZyI6bnVsbCwic25zX3R5cGUiOm51bGx9.tQXBiz35NPed9bsxZkuPGe6vRoKEY-wjWeY3_CfSx-k"
        ```
    3. 다시 docs에서 /test로 접속해본다.
         ```
         # not api(template �벑) request
         request.state.user id=1 email='test@example.com' name=None phone_number=None profile_img=None sns_type=None
         ```
    4. 이제 token을 엉뚱한 값으로 넣어주면 -> decode_token()메서드에서 에러를 발생시켜 -> 바깥 exceptino에서 잡혀야한다.
        ```
        # not api(template �벑) request
        {
          "message": "InvalidToken Error"
        }
        ```
    5. **api로 시작하는 endpoint가 더이상 없기 때문에, api쪽 테스트는 임시보류하고 쿠키 심은 것을 삭제한다.**

### user router 추가 및 swagger의 Authorization 달기

1. router폴더에 `user.py`를 만들고 response_model을 UserMe schema로 준다.
    - **incoming parameter로 `request`를 받아, 미들웨어에서 token -> UserToken으로 만든 데이터를 가져온 뒤, `id`만 이용해서 `User.get()`으로 user객체를
      받아온다.**
    - **이 때, 1개 모델 단순조회시(`create없고, 여러개 조회가 아님`)에는 route에서 session을 안받아도 된다?!**
    - schema의 UserMe에는 `user 객체`가 들어갈 예정이므로 그에 맞게 정의해준다. UserToken정보와 완전 동일하다?!

```python
# router > user.py
from fastapi import APIRouter
from starlette.requests import Request

from app.models import Users

router = APIRouter(prefix='/user')


@router.get('/me', response_model=UserMe)
async def get_user(request: Request):
    """
    get my info
    :param request:
    :return:
    """
    user_token = request.state.user
    user = Users.get(id=user_token.id)
    return user
```

```python
# schema.py
class UserMe(BaseModel):
    id: int
    email: str = None

    name: Optional[str] = None
    phone_number: Optional[str] = None
    profile_img: Optional[str] = None
    sns_type: Optional[str] = None

    class Config:
        # orm_mode = True
        from_attributes = True
```

2. `main.py`에 `API_KEY_HEADER` 상수를 fastapi.security의 APIKeyHeader를 import해서 추가하고
    - 헤더의 인증 키값인 `Authorization`을 `name=` 옵션에 준다.
    - 추가로 `auto_error=False`를 추가옵션으로 줘야한다. default True는, **해당 name=에 준 key가 headers에 없을 때, 403에러를 자동으로 raise하지만, `우리는 이미 access_control에서 Authorization없으면 custom에러를 낼 것`이다.**
    - **이후 user.py의 router를 등록할 때, `dependencies=[]`에 `Depends(API_KEY_HEADER)`를 추가하면 된다.**

```python
from fastapi.security import APIKeyHeader

KEY_HEADER = APIKeyHeader(name='Authorization', auto_error=False)


def create_app():
# ...
```

3. /docs에 들어가면, Authorize버튼 + Users endpoint들에게 좌물쇠가 생겨있다.
![img.png](../images/7.png)
4. 좌물쇠 endpoint나 좌물쇠버튼을 눌러서, **꼼쳐둔 token을 Bearer 부터 복붙하면 로그인 된다.**
    - **기본예시로 회원가입 -> 로그인 후 token 복사해도 된다.**
    ```
   # test@example.com / test
   Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MSwiZW1haWwiOiJ0ZXN0QGV4YW1wbGUuY29tIiwibmFtZSI6bnVsbCwicGhvbmVfbnVtYmVyIjpudWxsLCJwcm9maWxlX2ltZyI6bnVsbCwic25zX3R5cGUiOm51bGx9.tQXBiz35NPed9bsxZkuPGe6vRoKEY-wjWeY3_CfSx-k
   ```
   - 요청하면, User객체를 조회한 뒤, UserMe schema에 맞게 반환된다.
   ```python
    {
      "id": 1,
      "email": "test@example.com",
      "name": null,
      "phone_number": null,
      "profile_img": null,
      "sns_type": null
    }
    ```
### 도커 명령어

1. (`패키지 설치`시) `pip freeze` 후 `api 재실행`

```shell
pip freeze > .\requirements.txt

docker-compose build --no-cache api; docker-compose up -d api;
```

2. (init.sql 재작성시) `data폴더 삭제` 후, `mysql 재실행`

```shell
docker-compose build --no-cache mysql; docker-compose up -d mysql;
```

```powershell
docker --version
docker-compose --version

docker ps
docker ps -a 

docker kill [전체이름]
docker-compose build --no-cache
docker-compose up -d 
docker-compose up -d [서비스이름]
docker-compose kill [서비스이름]

docker-compose build --no-cache [서비스명]; docker-compose up -d [서비스명];

```

- 참고
    - 이동: git clone 프로젝트 커밋id 복사 -> `git reset --hard [커밋id]`
    - 복구: `git reflog` -> 돌리고 싶은 HEAD@{ n } 복사 -> `git reset --hard [HEAD복사부분]`