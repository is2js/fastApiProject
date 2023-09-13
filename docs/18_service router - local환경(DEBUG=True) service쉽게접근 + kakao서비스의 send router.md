### 카카오 임시token 발급

1. **도구 > RESTAPI 테스트 > `나에게 기본 템플릿으로 보내기`를 선택 한 뒤,**
    - 인증앱을 sample -> 내가 만든 애플리케이션으로 선택
    - **8시간되면 만료. 추후 코드로 refresh해서 재생산해야하는 `access token`을 발급한 뒤 가져온다.**
    - **발급받은 임시토큰을 .env에 `KAKAO_ACCESS_TOKEN=`라고 저장해놓고, Config 수정하기 전까진 직접 router에서 쓸 예정.**
    - **해당 토큰은 나에게보내기 메세지 요청시 `headers의 Authorization`으로 넣어줘야한다.**

2. dotenv정의 후, config.py에서 app관련인 Config객체가 아닌, 전역상수로서 선언한다.
    ```dotenv
    KAKAO_ACCESS_TOKEN="uq82-Q0yOa0ITCkpqPBvgScfTEWxm0c__oHTLu7zCj102wAAAYqMOQo-"
    ```
    ```python
    # config.py
    
    # REST API SERVICE
    KAKAO_ACCESS_TOKEN = "Bearer " + environ.get("KAKAO_ACCESS_TOKEN")
    ```

### service router

- local에서는 access_control service접속시, qs(access_key)+headers["secret"](key) 필요없이, headers["Authorization"]으로만 인증(User조회)
  되도록

#### api/v1/service router

1. app > api > v1 > `services.py`를 생성하고 router를 구현한다
    - 임시로 request -> state.user.email을 꺼내 이메일을 반환하는 라우터를 만든다.
    - **기존 user.py를 users.py로 변경한다.(복수형)**

2. 해당 router를 상위 router(상위패키지의 `__init__.py`)에 include시킨다.
    - 인증필요할 때는 dependencies를 추가해야한다.
    ```python
    from fastapi import APIRouter, Depends
    from fastapi.security import APIKeyHeader
    
    from . import auth, users, services
    
    API_KEY_HEADER = APIKeyHeader(name='Authorization', auto_error=False)
    
    router = APIRouter()  # v1 router -> 상위 main router객체에 prefix
    router.include_router(auth.router, prefix='/auth', tags=['Authentication'])
    router.include_router(users.router, prefix='/users', tags=['Users'], dependencies=[Depends(API_KEY_HEADER)])
    router.include_router(services.router, prefix='/services', tags=['Services'], dependencies=[Depends(API_KEY_HEADER)])
    ```

#### Test를 위해, local DEBUG=TRUE일 땐, Middleware-Service에서, swagger 인증 가능한 headers속 Authorization으로 인증되도록, api/vx/service에서 DEBUG 확인

1. service url 진입시, DEBUG=True == LocalConfig 환경이면, **headers속 secret/ qs속 key=,timestamp => 인증 없이, swagger
   Authorization 인증이 가능하도록 설정한다**
    ```python
    class AccessControl(BaseHTTPMiddleware):
    
        async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
    
            try:
                # (1) token 검사(user정보) 없는 except_path -> endpoint로
                if await url_pattern_check(url, EXCEPT_PATH_REGEX):
                    ...
                elif url in EXCEPT_PATH_LIST:
                    ...
                # (3) services router들로 들어오면, headers(secret[key]) and querystring([access]key + timestamp)
                # ->  UserToken을 state.user에 담아 endpoint로
                elif await url_pattern_check(url, SERVICE_PATH_REGEX):
                    
                    # (4) local(DEBUG=True) swagger로 qs + secret로는 swagger 테스트가 안되니, 
                    # -> swagger에서 삽입한 Authorization으로 인증(user_token)하도록 non_service(headers-Authorization에 jwt access token)로 처리되게 한다.
                    if config.DEBUG:
                        request.state.user = await self.extract_user_token_by_non_service(headers, cookies)
                        response = await call_next(request)
                        await app_logger.log(request=request, response=response)
                        return response
                    
                    request.state.user = await self.extract_user_token_by_service(headers, query_params)
                # (2) service아닌 API or 템플릿 렌더링 
                #  -> token 검사 후 (request 속 headers(서비스아닌api) or cookies(템플릿렌더링)) -> UserToken을 state.user에 담아 endpoint로
                else:
                    request.state.user = await self.extract_user_token_by_non_service(headers, cookies)
    ```

2. 확인해보니, swagger로 삽입한 Authorization도 headers 속에선 key가 소문자로 잡히는 것을 확인했다.
    - cookies는 대문자 라고 하는데 둘다 검사하게 한다.
    ```python
    @staticmethod
    async def extract_user_token_by_non_service(headers: Headers, cookies: dict[str, str]):
        # if "Authorization" in headers.keys():
        if "authorization" in headers.keys() or "Authorization" in headers.keys() :
            token = headers.get("Authorization")
            
        elif "Authorization" in cookies.keys() or "authorization" in cookies.keys():
            # 템플릿 쿠키 검사1) 키가 없으면 탈락
            cookies['Authorization'] = \
                'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MiwiZW1haWwiOiJ1c2VyQGV4YW1wbGUuY29tIiwibmFtZSI6bnVsbCwicGhvbmVfbnVtYmVyIjpudWxsLCJwcm9maWxlX2ltZyI6bnVsbCwic25zX3R5cGUiOm51bGx9.6cnlgT4xWyKh5JTXxhd2kN1hLT4fawhnyBsV3scvDzU'
            token = headers.get("Authorization")
        else:
            raise NotAuthorized()
    
        user_token_info = await decode_token(token)
    
        return UserToken(**user_token_info)
    ```
3. **이제 LocalConfig상태에선, swagger에 Authorization을 넣어주면, api/services라우터에 접근할 수 있다.**

#### kakao(service명)/send router 구현

1. `post`로 `/kakao/send` router를 만들고, config.py의 전역상수 `KAKAO_ACCESS_TOKEN`을 가져온 뒤
    - request를 주입하고, 상수Schema를 return한다
    ```python
    @router.post('/kakao/send')
    async def send_kakao(request: Request):
        token = KAKAO_ACCESS_TOKEN
        print(token)
    
        return SuccessMessage()
    
    ```
   ![img.png](../images/16.png)

2. **타 rest api를 이용할 땐**
    - **`headers=dict() or {}`에 `Authorization=Bearer 토큰` + `Content-type=`을 넣고**
    - **`data=dict()`에 원하는 방식의 `key`=`json.dump( body , ensure_ascii=False)`으로 value는 `json패키지로 dict -> text`로 변환하여**
        - json.dump()가 무난히 잘바뀌려면 `python datetime같은 형식`이 없어야한다.
        - 한글 -> ascii가 아님을 명시해줘야한다. -> **ascii아닌 한글이 포함되면,ensure_ascii=False옵션을 넣어줘야한다.**
    - **`res - requests모듈.post()`에 요청한 뒤**
    - **`try: res.raise_for_status() -> 200~300대가 아니면 에러 except: raise`로 검증한다.**
        - 이 때, `res.json()`으로 결과값을 받아서, 내부 result_code 등의 원하는 방식의 응답을 확인한다.
    - 원하는 headers와 data를 만드려면, [이 문서](https://developers.kakao.com/docs/latest/ko/message/rest-api#default-template-msg)
      를 참고한다.
      ![img.png](../images/17.png)

3. route안에서 object_type: text로 보내기 코드를 작성한다.
    ```python
    @router.post('/kakao/send')
    async def send_kakao(request: Request):
        # TODO: 추후 임시 8시간 TOKEN(REST API 테스트 -> 토큰발급)이 아닌, REFRESH가 계속 되도록 변경
        token = KAKAO_ACCESS_TOKEN  # Bearer uq82-Q0yOa0ITCkpqPBvgScfTEWxm0c__oHTLu7zCj102wAAAYqMOQo-
    
        # 헤더
        headers = {
            'Authorization': token,
            'Content-Type': "application/x-www-form-urlencoded",
        }
    
        # data {'template_object': json }
        # 1) body
        template_object = json.dumps({
            "object_type": "text",
            "text": "텍스트 영역입니다. 최대 200자 표시 가능합니다.",
            "link": {
                "web_url": "https://developers.kakao.com",
                "mobile_web_url": "https://developers.kakao.com"
            },
            "button_title": "바로 확인"
        }, ensure_ascii=False)
    
        # 2) data
        data = {
            'template_object': template_object
        }
    
        # kakako api url
        kakao_send_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    
        # request
        response = requests.post(kakao_send_url, headers=headers, data=data)
    
        try:
            response.raise_for_status()
            # 카카오의 응답 중 result_code가 0이 아니면 에러
            if response.json()['result_code'] != 0:
                raise
        except Exception as e:
            # 로깅
            raise e
    
        return SuccessMessage()
    
    ```
   ![img.png](../images/18.png)

4. **메세지 내용을 직접 입력하고 싶으면, RequestSchema를 작성하면 된다.**
    - schemas/services.py를 만들고 내부에서 KakaoMessageRequest를 만든다.
    ```pyhton
    # schemas/services.py
    from typing import Optional
    
    from pydantic import BaseModel
    
    
    class KakaoMessageRequest(BaseModel):
    message: Optional[str] = None
    ```
    ```python
    from .services import *
    ```
    ```python
    @router.post('/kakao/send')
    async def send_kakao(request: Request, message_request: KakaoMessageRequest):
    #...
    template_object = json.dumps({
    "object_type": "text",
    "text": message_request.message,
    ```

5. 커스텀으로 알림톡 object_type으로 변경해보자.
    - **이 때, link가 안보일 수 있는데, 내앱>플랫폼>web플랫폼에 등록되어야만 뜨게 된다.**
    - 이미지는 github에서 이미지주소복사해서 config에 전역상수로 지정한다.
    - 스키마에 title과 message를 구분해서, 각각 보낼 수 있게 한다.
    ```python
    KAKAO_IMAGE_URL: Optional[str] = \
        "https://github.com/is3js/hospital/blob/master/images/popup/mainPopup_530x640_2.jpg?raw=true"
    ```
    ```python
    class KakaoMessageRequest(BaseModel):
        title: Optional[str] = None
        message: Optional[str] = None
    ```
    
    ```python
    # data {'template_object': json }
    # 1) body
    # 내 앱 > 플랫폼 > Web플랫폼 등록된 것만 link로 보낼 시 보이게 됨.
    link_1 = "https://google.com"
    link_2 = "https://duckduckgo.com"
    
    template_object = json.dumps({
        "object_type": "feed",
        "content": {
            "title": message_request.title,
            "description": message_request.message,
            "image_url": KAKAO_IMAGE_URL, # 530x640 jpg
            "image_width": 530,
            "image_height": 640,
            "link": {
                "web_url": "http://google.com",
                "mobile_web_url": "http://google.com",
                "android_execution_params": "contentId=100",
                "ios_execution_params": "contentId=100",
            },
        },
        "buttons": [
            {
                "title": "구글",
                "link": {"web_url": link_1, "mobile_web_url": link_1},
            },
            {
                "title": "덕덕고",
                "link": {"web_url": link_2, "mobile_web_url": link_2},
            },
        ],
    }, ensure_ascii=False)
    ```
    ![img.png](../images/19.png)
    ![img_1.png](../images/20.png)


6. 상수들을 config.py 에 상수화한다.
    ```python
    # kakao - 나에게 메세지 보내기
    KAKAO_SEND_ME_ACCESS_TOKEN = "Bearer " + environ.get("KAKAO_ACCESS_TOKEN")
    # "http://k.kakaocdn.net/dn/wwWjr/btrYVhCnZDF/2bgXDJth2LyIajIjILhLK0/kakaolink40_original.png"
    KAKAO_SEND_ME_IMAGE_URL: Optional[str] = "https://github.com/is3js/hospital/blob/master/images/popup/mainPopup_530x640_2.jpg?raw=true"
    KAKAO_SEND_ME_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    ```
7. 이제 APIExcetion의 400에러(BadRequest)로서, 카카오 전송에러 exception을 만든다.
    ```python
    class KakaoSendMeMessageException(BadRequestException):
        def __init__(self, exception: Exception = None):
            super().__init__(
                code_number=14,
                detail=f"카카오톡(나에게 메세지 보내기) 전송에 실패하였습니다.",
                exception=exception
            )
    
    ```
    ```python
    try:
        response.raise_for_status()
        # 카카오의 응답 중 result_code가 0이 아니면 에러
        if response.json()['result_code'] != 0:
            raise Exception
    except Exception as e:
        # 로깅
        raise KakaoSendMeMessageException(exception=e)
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