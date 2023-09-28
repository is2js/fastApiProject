### 패키지화

#### backends > oauth.py 속 각 client들을 패키지 내부로 세부화한다.

1. backends > oauth 패키지 생성 > base, google, kakao, discord.py 생성
2. 공통 OAuthBackend를 base.py로 이동
3. GoogleBackend 클래스, google_cookie_backend, google_bearer_backend 기본 백엔드 객체2개 -> 소환하는 get_google_backends() 메서드는
   google.py로 이동
    - 나머지 kakao, discord도 마찬가지로 이동
4. **각각의 get_xxx_backends() 내부에서, `미리 생성된 객체 대신, 실시간으로 backend객체 생성`하여 -> 추후 메서드호출은 `CLIENT, SECRET 키가 있을 때만` 객체를 생성해서
   반환해주도록 한다.**
    ```python
    # app/libs/auth/backends/oauth/google.py
    
    # google_cookie_backend = GoogleBackend(
    #     name="cookie",
    #     transport=get_cookie_transport(),
    #     get_strategy=get_jwt_strategy,
    #     has_profile_callback=True,
    # )
    # 
    # google_bearer_backend = GoogleBackend(
    #     name="bearer",
    #     transport=get_bearer_transport(),
    #     get_strategy=get_jwt_strategy,
    #     has_profile_callback=True,
    # )
    
    
    def get_google_backends():
        return [
            GoogleBackend(
                name="cookie",
                transport=get_cookie_transport(),
                get_strategy=get_jwt_strategy,
                has_profile_callback=True,
            ),
            GoogleBackend(
                name="bearer",
                transport=get_bearer_transport(),
                get_strategy=get_jwt_strategy,
                has_profile_callback=True,
            )
        ]
    ```
    ```python
    # app/libs/auth/backends/oauth/__init__.py
    from app.libs.auth.strategies import get_jwt_strategy
    from app.libs.auth.transports import get_cookie_transport, get_bearer_transport
    from .discord import DiscordBackend
    from .google import GoogleBackend
    from .kakao import KakaoBackend
    
    
    def get_google_backends():
        return [
            GoogleBackend(
                name="cookie",
                transport=get_cookie_transport(),
                get_strategy=get_jwt_strategy,
                has_profile_callback=True,
            ),
            GoogleBackend(
                name="bearer",
                transport=get_bearer_transport(),
                get_strategy=get_jwt_strategy,
                has_profile_callback=True,
            )
        ]
    
    
    def get_kakao_backends():
        return [
            KakaoBackend(
                name="cookie",
                transport=get_cookie_transport(),
                get_strategy=get_jwt_strategy,
                has_profile_callback=True,
            ),
            KakaoBackend(
                name="bearer",
                transport=get_bearer_transport(),
                get_strategy=get_jwt_strategy,
                has_profile_callback=True,
            )
        ]
    
    
    def get_discord_backends():
        return [
            DiscordBackend(
                name="cookie",
                transport=get_cookie_transport(),
                get_strategy=get_jwt_strategy,
                has_profile_callback=True,
            ),
            DiscordBackend(
                name="bearer",
                transport=get_bearer_transport(),
                get_strategy=get_jwt_strategy,
                has_profile_callback=True,
            )
        ]
    
    ```

#### oauth_clients를 기준으로 oauth_backends를 가져오므로, oauth_client의 생성을 ID, SECERT 확인후 생성하게 해준다.

```python
# app/libs/auth/oauth_clients/google.py
from httpx_oauth.clients import google
from httpx_oauth.clients.google import GoogleOAuth2

from app.common.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET


def get_google_client():
    return GoogleOAuth2(
        GOOGLE_CLIENT_ID,
        GOOGLE_CLIENT_SECRET,
        scopes=google.BASE_SCOPES + [
            "openid",
            "https://www.googleapis.com/auth/user.birthday.read",  # 추가 액세스 요청 3개 (전부 people api)
            "https://www.googleapis.com/auth/user.gender.read",
            "https://www.googleapis.com/auth/user.phonenumbers.read",
        ])

```

```python
# app/libs/auth/oauth_clients/__init__.py
from app.common.config import (
    GOOGLE_CLIENT_SECRET, GOOGLE_CLIENT_ID,
    KAKAO_CLIENT_ID, KAKAO_CLIENT_SECRET,
    DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET
)
from .discord import get_discord_client
from .google import get_google_client
from .kakao import get_kakao_client


def get_oauth_clients():
    clients = []

    if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
        clients.append(get_google_client())

    if KAKAO_CLIENT_ID and KAKAO_CLIENT_SECRET:
        clients.append(get_kakao_client())

    if DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET:
        clients.append(get_discord_client())

    return clients

```

```python
# app/api/dependencies/auth.py
def get_oauth_routers():
    routers = []

    for oauth_client in get_oauth_clients():
        if isinstance(oauth_client, GoogleOAuth2):
            for backend in get_google_backends():
        # ...
```

### 기존 login/{sns_type}에 oauth 로그인 통합

1. `{sns_type}`에 email 외 다른 값이 들어오면, 미리 생성해둔 bearer타입의 /authorize 라우터들로 redirect시켜서 `authorize_url`을 뱉어내도록 만든다.
    - **이 때, POST router 인데, `RedirectResponse`를 쓰면, POST로 그대로 넘어가서 `GET으로 정의된 /authorize 라우터들`에서 Method not allowed 에러를 뱉는다.**
    - **그래서 `Response` + headers에 "Location"key의 value로 `"f'/api/v1/auth/{sns_type}/bearer/authorize'`를 넣어주는 방식으로 가본다.**
    ```python
    @router.post("/login/{sns_type}", status_code=200, response_model=Token)
    async def login(
            sns_type: SnsType,
            user_request: UserRequest,
            session: AsyncSession = Depends(db.session),
            password_helper=Depends(get_password_helper)
    ):
        """
        `로그인 API`\n
        """
        if sns_type == SnsType.EMAIL:
    
        elif sns_type in SnsType:
            return Response(
                status_code=status.HTTP_302_FOUND,
                headers={"Location": f'/api/v1/auth/{sns_type}/bearer/authorize'}
            )
    
        raise NoSupportException()
    ```
   
2. **이렇게 두면, oauth 로그인에서도 user_request가 들어오게 된다.**
    - **path params 중 `특정 종목을 먼저 정의하는 방법`으로 router 2개를 선언한다.**
        - `/login/email`
        - `/login/{sns_type}`
    - 아래와 같은 예시가 있을 수 있다.
    ```python
    @app.get("/users/me")
    async def read_user_me():
        return {"user_id": "the current user"}
    
    
    @app.get("/users/{user_id}")
    async def read_user(user_id: int):
        return {"user_id": user_id}
    ```
3. **그 전에 통합하려고 노력은 햇으나, UserRequest를 sns_type에 따라 주입받는 주입메서드를 따로 정의하면, `UserRequest`가 `/docs`상에서 안보이게 된다.**
  - 새로운 주입메서드 정의시, docs상에 안보이게됨. 대신 **주입메서드에 path params를 받아지긴 했다.**
    ```python
    def get_user_request_for_sns_type(sns_type: SnsType) -> [UserRequest, None]:
        print(f"sns_type >> {sns_type}") # SnsType.EMAIL
        
        if sns_type == SnsType.EMAIL:
            return UserRequest()
        else:
            return
    @router.post("/login/{sns_type}", status_code=200, response_model=Token)
    async def login(
            sns_type: SnsType,
            # user_request: Optional[UserRequest],
            user_request: UserRequest = Depends(get_user_request_for_sns_type),
            session: AsyncSession = Depends(db.session),
            password_helper=Depends(get_password_helper)
    ):
        """
        `로그인 API`\n
        - 통합로그인 endpoint로서, 직접 {"email": "" , "password": ""}를 request body로 입력해야합니다.
        """
    ```
    
#### router 2개로 분리 (특정sns_type인 "email" router 먼저 정의 vs Enum 중에 골라서 오는 path {sns_type})
```python
class RequestError(BadRequestException):
    def __init__(self, detail="잘못된 요청이 들어왔습니다.", exception: Exception = None):
        super().__init__(
            code_number=15,
            detail=detail,
            exception=exception
        )
```
```python
@router.post("/login/email", status_code=200, response_model=Token)
async def login(
        user_request: UserRequest,
        session: AsyncSession = Depends(db.session),
        password_helper=Depends(get_password_helper)
):
    """
    `로그인 API`\n
    :param user_request:
    :param session:
    :param password_helper:
    :return:
    """
    # 검증1) 모든 요소(email, pw)가 다 들어와야한다.
    if not user_request.email or not user_request.password:
        # return JSONResponse(status_code=400, content=dict(message="Email and PW must be provided."))
        raise RequestError('이메일와 비밀번호를 모두 입력해주세요.')

    # 검증2) email이 존재 해야만 한다.
    # user = await Users.get_by_email(session, user_info.email)
    user = await Users.filter_by(session=session, email=user_request.email).first()
    if not user:
        # return JSONResponse(status_code=400, content=dict(message="NO_MATCH_USER"))
        raise NoUserMatchException()

    # 검증3)  [입력된 pw] vs email로 등록된 DB저장 [해쉬 pw]  동일해야한다.
    # is_verified = bcrypt.checkpw(user_request.password.encode('utf-8'), user.password.encode('utf-8'))
    # is_verified = verify_password(user.hashed_password, user_request.password)
    is_verified, updated_hashed_password = password_helper.verify_and_update(
        user_request.password,
        user.hashed_password
    )

    if not is_verified:
        raise NoUserMatchException()

    if updated_hashed_password:
        await user.update(session=session, hashed_password=updated_hashed_password)

    await user.update(session=session, auto_commit=True, last_seen=D.datetime())

    token_data = UserToken.model_validate(user).model_dump(exclude={'hashed_password', 'marketing_agree'})
    token = dict(
        Authorization=f"Bearer {await create_access_token(data=token_data)}"
    )
    return token


@router.post("/login/{sns_type}", status_code=200, response_model=Token)
async def login_sns(sns_type: SnsType):
    """
    `소셜 로그인 API`\n
    - 개별 /api/v1/auth/{sns_type}/bearer/authorize로 redirect 됩니다.
    :param sns_type: 
    :return: 
    """

    if sns_type in SnsType:
        return Response(
            status_code=status.HTTP_302_FOUND,
            headers={"Location": f'/api/v1/auth/{sns_type}/bearer/authorize'}
        )
    raise NoSupportException()
```

#### 이제 SnsType에 EMAIL은 제외시키자. (docs에 EMAIL이 골라짐)
```python
class SnsType(str, Enum):
    # EMAIL: str = "email"
    # FACEBOOK: str = "facebook"
    GOOGLE: str = "google"
    KAKAO: str = "kakao"
    DISCORD: str = "discord"
```

### Sns로그인 추가 방법 정리
1. models > enums > `SnsType`에 enum 요소를 추가한다.
    - **DB의 Users 테이블(enum칼럼) 재생성되어야한다. Enum타입으로 정해져있음.**

2. 개발자 페이지에서 앱 생성 > client_id, secret키를 구한 뒤, SCOPE를 확인한다.
    - .env > config에 정리한다.
3. libs > auth > oauth_clients > `해당oauth.py`를 생성하고 httx_oauth 패키지에서 client를 생성한다.
    - libs > auth > oauth_clients > `__init__.py`에서 id, secret 키가 있는 경우에만 해당 client객체를 불러올 수 있도록 `get_oauth_clients()`에 추가한다.
4. libs > auth > backends > oauth > `해당oauth.py`를 생성하고, client의 get_id_email에서 추가정보요청 PROFILE_ENDPOINT 및 요청 방법을 참고하여
    - scope를 늘려 요청한 뒤 양식에 맞게 `get_profile_info`를 정의한다.
    - libs > auth > backends > oauth > `__init__.py`에서 bearer, cookie 방식의 객체를 생성할 수 있는 메서드를 정의한다.

5. app/api/dependencies/auth.py에서, 해당 Client객체가 발견시, 해당 Backend객체들을 가져와 router를 만들 수 있게 `get_oauth_routers()`에 추가한다.
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

3. docker 추가 명령어

```powershell
docker stop $(docker ps -aq)
docker rm $(docker ps -aqf status=exited)
docker network prune 

docker-compose -f docker-compose.yml up -d
```

### pip 명령어

```powershell
# 파이참 yoyo-migration 설치

pip freeze | grep yoyo

# 추출패키지 복사 -> requirements.txt에 붙혀넣기

```

### git 명령어

```powershell
git config user.name "" 
git config user.email "" 

```

### yoyo 명령어

```powershell
yoyo new migrations/

# step 에 raw sql 작성

yoyo apply --database [db_url] ./migrations 
```

- 참고
    - 이동: git clone 프로젝트 커밋id 복사 -> `git reset --hard [커밋id]`
    - 복구: `git reflog` -> 돌리고 싶은 HEAD@{ n } 복사 -> `git reset --hard [HEAD복사부분]`