### secret key 다루기

- **`api/v1/services`라는 url로 들어올 때만, 미들웨어에서 jwt/cookie가 아닌 api key를 가지고 인증하게 한다**
    - api호출만 하는게 아니라, 하나의 api서버로서, ui제공 뿐만 아니라 backend서버에 backend를 제공한다.
    - rest는 원래 상태가 없다(jwt도) -> `로그인 된 상태`라는 것이 없다.

#### api/v1/services 처리 전, access_control 정리

1. request.state.xxx = None으로 초기화하는 부분을 `staticmethod메서드`(self.xx필드가 사용되지 않는 input-output)로 뺀다.

```python
class AccessControl(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        await self.init_state(request)

        headers = request.headers
        cookies = request.cookies
        url = request.url.path

        # ...

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

```

2. except_path_regex와 except_path_list를 분리해줘서 나중에 처리할 수 있게 한다.
    - early return 속 if `or`는 elif로 나눈다.
    - 응답코드를 아래쪽 `api or 템플릿`상황과 통합할 수 있게 한다.
    ```python
    try:
        # 통과(access) 검사 시작 ------------
        # (1) except_path url 검사 -> 해당시, token없이 접속가능(/docs, /api/auth ~ 등) -> token 검사 없이 바로 endpoint(await call_next(request)) 로
        if await url_pattern_check(url, EXCEPT_PATH_REGEX):
            # ...
            response = await call_next(request)
            # 응답 전 logging -> except_path 중에서는 index를 제외하고 찍기
            if url != "/":
                await app_logger.log(request=request, response=response)
            return response
        elif url in EXCEPT_PATH_LIST:
            # ...
            response = await call_next(request)
            # 응답 전 logging -> except_path 중에서는 index를 제외하고 찍기
            if url != "/":
                await app_logger.log(request=request, response=response)
            return response
    ```
    ```python
    try:
        # (1) token 검사 없이 (except_path) -> endpoint로 
        if await url_pattern_check(url, EXCEPT_PATH_REGEX):
            ...
        elif url in EXCEPT_PATH_LIST:
            ...
        # (2) token 검사 후 (request 속 headers or cookies) -> endpoint로
        # -> if api(/api시작)는 headers / else 템플릿은 cookie에서 검사
        else:
            # [1] api 접속 -> headers에 token정보
            if url.startswith('/api'):
                # api 검사1) api endpoint 접속은, 무조건 Authorization 키가 없으면 탈락
                request.state.access_token = headers.get("Authorization")
                if not request.state.access_token:
                    # return JSONResponse(status_code=401, content=dict(message="AUTHORIZATION_REQUIRED"))
                    raise NotAuthorized()
            # [2] 템플릿 레더링 -> cookies에서 token정보
            else:
                # 템플릿 쿠키 검사1) 키가 없으면 탈락
                # test ) 잘못된 토큰 박아서, decode_token 내부에러 확인하기
                cookies[
                    'Authorization'] = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MiwiZW1haWwiOiJ1c2VyQGV4YW1wbGUuY29tIiwibmFtZSI6bnVsbCwicGhvbmVfbnVtYmVyIjpudWxsLCJwcm9maWxlX2ltZyI6bnVsbCwic25zX3R5cGUiOm51bGx9.6cnlgT4xWyKh5JTXxhd2kN1hLT4fawhnyBsV3scvDzU'
                request.state.access_token = cookies.get("Authorization")
                if not request.state.access_token:
                    # return JSONResponse(status_code=401, content=dict(message="AUTHORIZATION_REQUIRED"))
                    raise NotAuthorized()

            # toekn -> request.state.access_token 저장 후 -> token decode -> user정보 추출 -> state.user 저장
            # - Authorization 키가 있을 때, Bearer를 떼어낸 순수 jwt token를 decode 했을 때의 user정보를 state.user에 담아준다.
            request.state.access_token = request.state.access_token.replace("Bearer ", "")
            user_token_info = await decode_token(request.state.access_token)
            request.state.user = UserToken(**user_token_info)

        response = await call_next(request)
        # 응답 전 logging
        if url != "/":
            await app_logger.log(request=request, response=response)
        return response
    ```

3. api 접속(headers) vs 렌더링 접속(cookies)의 구분을 url.startswith('/api')로 하지말고, **headers or cookies에 `Authorization` 키(
   Bearer~) 존재 여부로 판단한다.**
    - 또한, request.state.access_token은 굳이 삽입할 필요없는 중간변수이므로 삭제한다.
    - headers, cookies 둘다 없으면 인증에러를 raise한다.
    ```python
    try:
        # (1) token 검사 없이 (except_path) -> endpoint로
        if await url_pattern_check(url, EXCEPT_PATH_REGEX):
            ...
        elif url in EXCEPT_PATH_LIST:
            ...
        # (2) token 검사 후 (request 속 headers or cookies) -> endpoint로
        # -> if api(/api시작)는 headers / else 템플릿은 cookie에서 검사
        else:
            # [1] api 접속 -> headers에 token정보
            # if url.startswith('/api'):
            if "Authorization" in headers.keys():
                token = headers.get("Authorization")
            # [2] 템플릿 레더링 -> cookies에서 token정보
            # else:
            elif "Authorization" in cookies.keys():
                # 템플릿 쿠키 검사1) 키가 없으면 탈락
                # test ) 잘못된 토큰 박아서, decode_token 내부에러 확인하기
                cookies[
                    'Authorization'] = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MiwiZW1haWwiOiJ1c2VyQGV4YW1wbGUuY29tIiwibmFtZSI6bnVsbCwicGhvbmVfbnVtYmVyIjpudWxsLCJwcm9maWxlX2ltZyI6bnVsbCwic25zX3R5cGUiOm51bGx9.6cnlgT4xWyKh5JTXxhd2kN1hLT4fawhnyBsV3scvDzU'
                token = headers.get("Authorization")
            else:
                raise NotAuthorized()
    
            # toekn -> request.state.token 저장 후 -> token decode -> user정보 추출 -> state.user 저장
            # - Authorization 키가 있을 때, Bearer를 떼어낸 순수 jwt token를 decode 했을 때의 user정보를 state.user에 담아준다.
            token = token.replace("Bearer ", "")
            user_token_info = await decode_token(token)
            request.state.user = UserToken(**user_token_info)
    ```

4. Bearer 떼는 작업을 decode_token 유틸 내부로 이동시킨다.
5. 응답하는 코드(return response)는 try except의 `else`문에서 except없이 try를 마칠 경우 응답하도록 해준다.
    - **참고) await call_next(request)도 else로 옮겨버리면, except에 endpoint 에러를 잡을 수 없게 됨.**
    ```python
    try:
        # ...
        response = await call_next(request)
    except Exception as e:
        # ...
        response = JSONResponse(status_code=error.status_code, content=error_dict)
        # logging
        if isinstance(error, DBException):
            # APIException의 하위 DBException class부터 검사하여 해당하면 db_logger로 찍기
            await db_logger.log(request, error=error)
        else:
            await app_logger.log(request, error=error)
        return response
    else:
        # 응답 전 logging
        if url != "/":
            await app_logger.log(request=request, response=response)
        return response
    ```

6. `headers나 cookies -> token -> decode한 User정보` -> UserToken(from dict)가 아니라
    - `querystring으로 넘어오는 access_key + timestamp -> 검증 -> User객체` -> UserToken(from user객체.to_dict())을 만드므로
    - **user_token_info를 반환받는 방식이 달라지므로, `headers + cookies`의 방식(`non_service`)을 따로 구분하는 메서드를 추출 후 -> UserToken생성에 필요한
      정보를 반환하도록 한다.**
    ```python
    try:
        # (1) token 검사 없이 (except_path) -> endpoint로
        if await url_pattern_check(url, EXCEPT_PATH_REGEX):
            ...
        elif url in EXCEPT_PATH_LIST:
            ...
        # (2) token 검사 후 (request 속 headers or cookies) -> endpoint로
        # -> if api(/api시작)는 headers / else 템플릿은 cookie에서 검사
        else:
            request.state.user = await self.extract_user_token_by_non_service(cookies, headers)
    
    ```
    ```python
    @staticmethod
    async def extract_user_token_by_non_service(headers: Headers, cookies: dict[str, str]):
        # [1] api 접속 -> headers에 token정보
        if "Authorization" in headers.keys():
            token = headers.get("Authorization")
        # [2] 템플릿 레더링 -> cookies에서 token정보
        elif "Authorization" in cookies.keys():
            # 템플릿 쿠키 검사1) 키가 없으면 탈락
            cookies['Authorization'] = \
                'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MiwiZW1haWwiOiJ1c2VyQGV4YW1wbGUuY29tIiwibmFtZSI6bnVsbCwicGhvbmVfbnVtYmVyIjpudWxsLCJwcm9maWxlX2ltZyI6bnVsbCwic25zX3R5cGUiOm51bGx9.6cnlgT4xWyKh5JTXxhd2kN1hLT4fawhnyBsV3scvDzU'
            token = headers.get("Authorization")
        else:
            raise NotAuthorized()
    
        user_token_info = await decode_token(token)
    
        return UserToken(**user_token_info)
    ```

### 본격 api/v1/services 개발

1. **except_path가 아닌, api일반접속(headers or cookies에 auth)
   과 `apikey(querystring-key=access_key&timestamp=, headers-secret) + 를 가지고 접속하는 api service접속`을 구분하는 것을**
    - url에서 `api/v[0-9]/services`로 시작하는지로 판단하기 위해 상수로 정의후 -> 앞에 정의했던 url_pattern_check 유틸을 사용한다
    - re.match(pattern, string)으로 사용되며, 해당객체가 존재하면 True로 매칭되는 것이다.
    ```python
    SERVICE_PATH_REGEX = "^(/api/v[0-9]+/services)"
    ```
    ```python
    query_params = request.query_params

    # (1) token 검사 없이 (except_path) -> endpoint로
    if await url_pattern_check(url, EXCEPT_PATH_REGEX):
        ...
    elif url in EXCEPT_PATH_LIST:
        ...
    # (3) services router들로 들어오면, headers(secret[key]) and querystring([access]key + timestamp) ->  UserToken을 state.user에 담아 endpoint로
    elif await url_pattern_check(url, SERVICE_PATH_REGEX):
        request.state.user = await self.extract_user_token_by_service(headers, query_params)
    # (2) token 검사 후 (request 속 headers or cookies) -> UserToken을 state.user에 담아 endpoint로
    else:
        request.state.user = await self.extract_user_token_by_non_service(headers, cookies)
    
    ```
    ```python
    @staticmethod
    async def extract_user_token_by_service(headers: Headers, query_params: QueryParams):
        pass
    
    ```
2. 이제 extract_user_token_by_service를 정의해주고, 로직을 작성한다.
    - request.query_params를 dict()만 씌우면 dictionary로 쓸수 있다.
    ```python
    url="/api/v2/services/sadf" 
    True if re.match("^(/api/v[0-9]+/services)", url) else False
    # True
    ```
    - dict로 변환된 상태에서 **access_key를 의미하는 `key`와 현재시간을 초로 바꾼 `timestamp`가 포함됫는지 확인한다.**
    - **`if not` all(모두통과해야하는조건) `: raise`를 사용해서, key/timestamp가 query_string의 key로 포함되는지 확인하고**
        - 하나라도 통과하면 되는 조건은 `if not any` (하나만 통과해도 되는 조건) `: raise`을 써야함.
   ```python
    @staticmethod
    async def extract_user_token_by_service(headers: Headers, query_params: QueryParams):
        query_params_map: dict = dict(query_params)
        # 1) access_key를 key=로 달고오며, 현재시간을 timestamp=로 달고와야한다.
        # key= & timestamp 모두 통과해야하는 조건 -> if not all : raise
        if not all(query_key in ('key', 'timestamp') for query_key in query_params_map.keys()):
            raise InvalidServiceQueryStringException()

        # 2) secret_key를 headers의 'secret'으로 달고와야한다.
        if 'secret' not in headers.keys():
            raise InvalidServiceHeaderException()
    ```
    ```python
    class InvalidServiceQueryStringException(BadRequestException):
        def __init__(self, exception: Exception = None):
            super().__init__(
                code_number=11,
                detail=f"서비스 요청시 query string key=, timestamp= 2개를 모두 입력해주세요.",
                exception=exception
            )
    
    
    class InvalidServiceHeaderException(BadRequestException):
        def __init__(self, exception: Exception = None):
            super().__init__(
                code_number=12,
                detail=f"서비스 요청시 Header에 secret(key)가 필요합니다.",
                exception=exception
            )
    ```

3. 크롬의 url에 `/api/v1/services?key=123&timestamp=10`의 임시 호출을 해보자.
    - headers에 secret키 검증에 걸리고, querystring은 2개다 존재하는 것을 확인할 수 있다.
    ```python
    http://localhost:8010/api/v1/services?key=123&timestamp=10
    
    # status	400
    # code	"4000012"
    # message	"잘못된 접근입니다."
    # detail	"서비스 요청시 Header에 secret(key)가 필요합니다."
    ```

    - **하지만 secret키도 headers에 박아서, db접근이 잘 되는지 확인해야한다. 이를 위해 `py파일에서 requests모듈로 호출`할 수 있게 설정한다.**
4. root에 `request_service_sample.py`을 생성하고, gitignore에 추가한다. -> **나중에는 test파일로 변경해야할 듯.**
    - **유효한 access_key, secret_key를 하나 db에서 가져온다.**
    - datetime.utcnow() + timedelta(9)를 `D.datetime(diff_hours=9)로 대체`해서 생성한 뒤, .timestamp()를 먹인 뒤, int()로 소수점을 자른다.
    - query_string dict를 dict(key=, timestamp=)로 만든다.
    ```python
    from app.utils.date_utils import D

    def request_service():
        access_key = "875cad56-8769-47b7-ae6d-aaffd87d-0bbb-4191-9d73-b1fdab8c138b"
        secret_key = "FiyRvvUTzzuwYrz8kxoBMbvBfwZtoCGkEjWs3pJF"
    
        datetime_kst = D.datetime(diff_hours=9)
        timestamp = int(datetime_kst.timestamp())  # 12355.1234
    
        params = dict(key=access_key, timestamp=timestamp)
    
    
    if __name__ == '__main__':
        request_service()

    ```
    - dict -> query_string으로 변환해주는 모듈이 필요하다.

#### param_utils.py 정의

1. app > utils > `param_utils.py`를 생성한다.
2. `to_query_string`모듈을 정의한다.
    - **`?`를 제외하고, key=value&key2=valu2 가 `&`로 사이사이 연결되니 "&".join으로 연결하며,**
    - **각각의 key, value가 모두 string변환되어야하므로 `f"{}={}"`를 활용한다**
    ```python
    from app.utils.date_utils import D
    from app.utils.param_utils import to_query_string
    
    
    def request_service():
        access_key = "875cad56-8769-47b7-ae6d-aaffd87d-0bbb-4191-9d73-b1fdab8c138b"
        secret_key = "FiyRvvUTzzuwYrz8kxoBMbvBfwZtoCGkEjWs3pJF"
    
        datetime_kst = D.datetime(diff_hours=9)
        timestamp = int(datetime_kst.timestamp())  # 12355.1234
    
        params = dict(key=access_key, timestamp=timestamp)
        query_string = to_query_string(params)
   
        service_name = ''
        url: str = "http://127.0.0.1:8010" \
                   f"/api/services/{service_name}?{query_string}"
        print(url)
        
    
    if __name__ == '__main__':
        request_service()
    ```

3. **이제 `query_string`을 `secret_key`를 이용하여 `hmac모듈`을 이용하여 `단방향 해싱된  hashed_secret`을 Headers에 넣어줘야한다.**
    - **차후 검증시 해당 access_key에 대응되는 secret_key도 단방향 해쉬시킨뒤 비교한다**
    - **query_string과 secret_key를 받아 해싱쉬키는 `params_utils.py 속 모듈 hash_query_string()`을 정의하자.**
   ```python
   from base64 import b64encode
   from hmac import HMAC, new
   
   def hash_query_string(query_string: str, secret_key: str) -> str:
       # key와 msg(해쉬 대상) string -> 모두 bytes객체로 변환한 뒤,
       # mac객체를 만들고 -> .digest()로 해쉬된 값(이진값)을 꺼낸 뒤
       # -> base64인코딩을 통해, 이진값 -> 문자열로 변환한다
       mac: HMAC = new(
           key=bytes(secret_key, encoding="utf-8"),
           msg=bytes(query_string, encoding="utf-8"),
           digestmod="sha256",
       )
   
       return str(b64encode(mac.digest()).decode("utf-8"))
   ```
4. **이제 요청을 보내려면 `requests`모듈을 따로 설치해야한다.**
    ```shell
    pip install requests
    
    pip freeze > .\requirements.txt
    
    docker-compose build --no-cache api; docker-compose up -d api;
    ```

5. 이제 requests모듈로 get요청을 보낼 때, **header에 'secret'키로 hashed_secret값을 넣어보낸다.**
    ```python
    def request_service():
        access_key = "875cad56-8769-47b7-ae6d-aaffd87d-0bbb-4191-9d73-b1fdab8c138b"
        secret_key = "FiyRvvUTzzuwYrz8kxoBMbvBfwZtoCGkEjWs3pJF"
    
        datetime_kst = D.datetime(diff_hours=9)
        timestamp = int(datetime_kst.timestamp())  # 12355.1234
    
        params = dict(key=access_key, timestamp=timestamp)
        query_string = to_query_string(params)
    
        # hash qs by secret_key
        hashed_secret = hash_query_string(query_string, secret_key)
    
        # query_string(accees_key, timestamp)를 포함한 url
        service_name = ''
        url: str = "http://127.0.0.1:8010" \
                   f"/api/v1/services/{service_name}?{query_string}"
    
        response = requests.get(url, headers=dict(secret=hashed_secret))
    
        return response
    
    if __name__ == '__main__':
        response = request_service()
        print(response.json())
    ```

#### 미들웨어에서 session 사용(추후 redis로 바꿔야함.)

- 일단 endpoint가 아니면 Depends(db.session)이 사용이 안된다.

1. ~~현재 db.session asyngenerator가 있는데, `async with`로 session을 사용하려면 추가 작업 `@contextlib.asynccontextmanager`이 필요하다.~~
    ```python
    @contextlib.asynccontextmanager
    async def get_db(self):
    # ...
    ```
    - **contextmanger가 되어버리면, async with을 middleware에서 session발급용으로 쓸 수 있지만, `asyncgenerator의 기능을 잃ㄱ어버린다`**
    ```python
    # @contextlib.asynccontextmanager
    async def get_db(self):
    ```
    - **그대로 `async def + yield를 통한 asyncgenerator`를 유지 -> middleware에서 땡겨 쓸 땐, `async for`로 일시적 추출을 하면 된다.**
    ```python
    class AccessControl(BaseHTTPMiddleware):
    
        @staticmethod
        async def get_api_key_with_owner(query_params_map):
    
            # async with db.session() as session: # get_db가 async contextmanger일 때 -> db.session().__anext()__가 고장나버림
            # => asyncgenerator를 1개만 뽑아 쓰고 싶다면, async for를 쓰자.
            async for session in db.session(): 
    
                matched_api_key: Optional[ApiKeys] = await ApiKeys.filter_by(session=session,
    ```

2. qs로 입력된 access_key로 api_key를 조회해야한다. **이후, 해당 api_key의 user(owner)도 가져와야한다.**
    - **미리 load하기엔 api_key가 없을 시에는 에러가 나므로 `relationship lazy`를 적용하고 싶다.**
    - 이 때, 방법이 `2가지`가 있다. [참고](https://stackoverflow.com/questions/70104873/how-to-access-relationships-with-async-sqlalchemy)
        1. relationship에 lazy='selectin' 옵션을 주는 방법 `foo = relationship("B", lazy='selectin')`
        2. **쿼리에 options()로 직접 호출하는 방법 `.options(selectinload(A.bs))`**
        3. **`sqlalchemy2.0.4`부터 `session.refresh(객체, attribute_names=["relationship변수명"])`을 통해, lazy load를 강제 load하는 방법**
    - **나는 아직 mixin load개발전이므로 session.refresh를 이용해서 해당객체의 relationship을 조회해본다.**
    ```python
    @staticmethod
    async def extract_user_token_by_service(headers: Headers, query_params: QueryParams,
        ):
        query_params_map: dict = dict(query_params)
        print(query_params_map)
        # 1) access_key를 key=로 달고오며, 현재시간을 timestamp=로 달고와야한다.
        # key= & timestamp 모두 통과해야하는 조건 -> if not all (): raise
        if not all(query_key in ('key', 'timestamp') for query_key in query_params_map.keys()):
            raise InvalidServiceQueryStringException()
    
        # 2) secret_key를 headers의 'secret'으로 달고와야한다.
        if 'secret' not in headers.keys():
            raise InvalidServiceHeaderException()
    
        # 3) 이제 qs로 들어온 access_key를 db에서 조회해서 ApiKey객체 -> Onwer User객체를 가져온다
        # -> ApiKey객체는 headers로 들어온 secret(key)를 검증하기 위해 가져온다.
        # -> User객체는 최종 UserToken을 생성할 때 쓰이는 info고
        # session = await db.session().__anext__()
        async with db.session() as session:
    
            matched_api_key: Optional[ApiKeys] = await ApiKeys.filter_by(session=session, access_key=query_params_map['key']).first()
            print(matched_api_key)
            if not matched_api_key:
                raise NoKeyMatchException()
    
            # user객체는, relationship으로 가져온다. lazy인데, session이 안닫힌 상태라 가져올 수 있다.
            await session.refresh(matched_api_key, attribute_names=["user"])
    
            if not matched_api_key.user:
                raise NotFoundUserException()
   
        print(matched_api_key, matched_api_key.user) # <ApiKeys#7> <Users#9>
    ```
   
    - 메서드로 일단 추출한다.
    ```python
    @staticmethod
    async def extract_user_token_by_service(headers: Headers, query_params: QueryParams,
                                            ):
        query_params_map: dict = dict(query_params)
    
        # 1) access_key를 key=로 달고오며, 현재시간을 timestamp=로 달고와야한다.
    
        if not all(query_key in ('key', 'timestamp') for query_key in query_params_map.keys()):
            raise InvalidServiceQueryStringException()
    
        # 2) secret_key를 headers의 'secret'으로 달고와야한다.
        if 'secret' not in headers.keys():
            raise InvalidServiceHeaderException()
        matched_api_key_with_owner = await AccessControl.get_api_key_with_owner(query_params_map)
    
        print(matched_api_key_with_owner, matched_api_key_with_owner.user)  # <ApiKeys#7> <Users#9>

    ```
    - request 파일로 요청해서 확인해본다.

3. 이제 **`db속 secret_key + query_string`으로 hash된 secret** vs front에서 Headers로 들어온 `첫발급secret_key + query_string`으로 hash된 secret으로
    - 단방향 해쉬 값을 비교하여 검증한다.
    ```python
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
    ```
4. **추가로 서버에서는 `replay attack`을 방지하기 위해, `timestamp`을 `60초전 요청 ~ 서버 현재 kst  timestamp 60초 후`사이 요청인지 query_string의 timestamp를 검증한다.**
    ```python
    if headers['secret'] != validating_secret:
        raise InvalidServiceHeaderException()
    
    # 5) 요청이 서버kst시간의 1분전 ~ 1분후 사이의 요청이어야한다.
    current_timestamp_kst = int(D.datetime(diff_hours=9).timestamp())
    if not (current_timestamp_kst - 60 < int(query_params_map["timestamp"]) < current_timestamp_kst + 60 ):
        raise InvalidServiceTimestampException() # 쿼리스트링에 포함된 타임스탬프는 KST 이며, 현재 시간보다 작아야 하고, 현재시간 - 10초 보다는 커야 합니다.
    
    ```
    ```python
    class InvalidServiceTimestampException(BadRequestException):
        def __init__(self, exception: Exception = None):
            super().__init__(
                code_number=13,
                detail=f"쿼리스트링에 포함된 타임스탬프는 KST 이며, 현재 시간 + 60초 보다 작아야 하고, 현재시간 - 60초 보다는 커야 합니다.",
                exception=exception
            )
    ```
   
5. load된 .user(apikey_owner)를 UserToken Schema에 `.model_validate()`로 입력시킨다.
    - 원래는 `**객체.to_dict()`를 UserToken()에 입력할 수 도 있다.
    ```python
    if headers['secret'] != validating_secret:
        raise InvalidServiceHeaderException()
    
    # 5) 요청이 서버kst시간의 1분전 ~ 1분후 사이의 요청이어야한다.
    current_timestamp_kst = int(D.datetime(diff_hours=9).timestamp())
    if not (current_timestamp_kst - 60 < int(query_params_map["timestamp"]) < current_timestamp_kst + 60):
        raise InvalidServiceTimestampException()
    
    return UserToken.model_validate(matched_api_key_with_owner.user)
    ```
   
6. request_service()의 내부요소 중 access_key, secret_key, timestamp를 조절해서 에러가 잘못 요청되는지 확인한다.

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