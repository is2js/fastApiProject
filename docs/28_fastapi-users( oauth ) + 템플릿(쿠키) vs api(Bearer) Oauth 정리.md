### oauth 적용

#### model 추가

- https://fastapi-users.github.io/fastapi-users/12.1/configuration/oauth/?h=oauth_accounts#beanie

1. **`SQLAlchemyBaseOAuthAccountTable`(Generic not UUID)를 이용해서, OauthAccount 모델을 추가한다.**

```python
class OAuthAccount(BaseModel, SQLAlchemyBaseOAuthAccountTable[int]):
    pass
```

    - 기본 tablename은 `oauth_account`이지만, BaseModel 최종부모가 되서어서 oauthaccount로 지어질 것이다.

2. **기본 추가필드는 id를 제외하고 6개의 필드가 추가된다.**
    ```python
    oauth_name: Mapped[str] = mapped_column(
        String(length=100), index=True, nullable=False
    )
    access_token: Mapped[str] = mapped_column(String(length=1024), nullable=False)
    expires_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(
        String(length=1024), nullable=True
    )
    account_id: Mapped[str] = mapped_column(
        String(length=320), index=True, nullable=False
    )
    account_email: Mapped[str] = mapped_column(String(length=320), nullable=False)
    
    ```

3. Users 모델에서는 해당 테이블에 대한 relationship을 lazy="joined"로 추가해서, 바로 조회가능하도록 한다.
    - cascade를 추가함.

```python
class Users(BaseModel, SQLAlchemyBaseUserTable[int]):
    oauth_accounts = relationship(
        "OAuthAccount", lazy="joined",
        back_populates="user",
        cascade="all, delete-orphan",
    )
```

4. 공식문서에는 UUID가 아닌 제네릭 사용시, OAuthAccount 모델에는 Users에 대한 fk키가 없었다.
    - UUID는 user_id의 fk를 가졌음.
    - **그래서 추가했다. -> 다시 찾아보니 공식문서 아래에 해당 내용이 적혀있음.**
    ```python
    class OAuthAccount(BaseModel, SQLAlchemyBaseOAuthAccountTable[int]):
        user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
        user = relationship("Users", back_populates="oauth_accounts",
                            foreign_keys=[user_id],
                            uselist=False,
                            )
    ```

5. **이제 디펜던시에서 session -> SQLAlchemyUserDatabase를 yield할때, session+Users모델외 + `OAuthAccount모델`도 추가로 인자로준다**

```python
# app/api/dependencies/auth.py
async def get_user_db(session: AsyncSession = Depends(db.session)):
    # yield SQLAlchemyUserDatabase(session=session, user_table=Users)
    yield SQLAlchemyUserDatabase(session=session, user_table=Users, oauth_account_table=OAuthAccount)
```

### httpx-oauth 패키지 설치 및 OAuth2 client 만들기

1. 내부에서 `httpx_oauth`모듈이 사용되는데 따로 설치해야한다.
    - fastapi-users[oauth]를 설치하면 되는 것 같지만, 나는 `httpx-oauth`패키지를 바로 찾아서 설치했다.
    ```shell
    pip install httpx-oauth
    
    pip freeze > .\requirements.txt
    
    docker-compose build --no-cache api; docker-compose up -d api;
    ```

2. libs > auth > `oauth_clients.py`를 만들어서, GoogleOAuth2 client객체를 만든다.

```python
from httpx_oauth.clients.google import GoogleOAuth2

google_oauth_client = GoogleOAuth2("CLIENT_ID", "CLIENT_SECRET")

```

#### google cloud에서 인증앱 등록 후 router 생성

- 아래 2사이트를 참고해서 생성한다
    1. [장고](https://hyeo-noo.tistory.com/223)
    2. [fastapi](https://blog.hanchon.live/guides/google-login-with-fastapi/)

1. 구글 클라우드 > 프로젝트 > 새프로젝트
    - 프로젝트이름: `haniwon-auth-app` > 생성
    - 프로젝트 선택 > `사용자 인증 정보` > `OAuth 클라이언트 ID 만들기` > OAuth 동의화면 만들기 > UserType: `외부` > 정보입력(도메인 필요?!)
    - 사용자 인증정보 > Ouath 클라이언트 ID 만들기 > 승인된 js원본(내가 구글인증서버 요청하는 주소) + 승인된 리디렉션URI (구글서버가 오는 router주소)
    - **일단 `승인된 redirect_url`을 잘알지는 못하지만, prefix까지 포함한 `/authorize`, `/callback`으로 완성될 것이다.**
      ![img.png](../images/47.png)
    - 만들기를 누르면 `클라이언트 ID`, `클라이언트 보안 비밀번호`가 첫화면에 나온다.
    - **`사용자 정보`를 추후 사용하려면 `API 라이브러리 > 추가 > Peopel api`를 사용 추가한다.**

2. .env에 `GOOGLE_` 붙혀서 받아놓기 (다른 소셜로그인도 추가될 것임.)
    ```dotenv
    # oauth
    GOOGLE_CLIENT_ID=""
    GOOGLE_CLIENT_SECRET=""
    ```
    - config.py에 등록하고 client에 사용하기
    ```python
    # oauth
    GOOGLE_CLIENT_ID: str = environ.get("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET: str = environ.get("GOOGLE_CLIENT_SECRET", None)
    ```
    ```python
    from httpx_oauth.clients.google import GoogleOAuth2
    
    from app.common.config import (
        GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
    )
    
    google_oauth_client = GoogleOAuth2(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)
    ```


3. scope를 정의해줘야하는데, 이미 BASE_SCOPE로 기본값이 정의되어있고, 구글 프로젝트 앱에서 설정은 안되는 것 같은데, openid를 추가한 scopes=[]를 인자로 추가한다.
    ```python
    google_oauth_client = GoogleOAuth2(
        GOOGLE_CLIENT_ID,
        GOOGLE_CLIENT_SECRET,
        scopes=[
            "https://www.googleapis.com/auth/userinfo.profile",  # 구글 클라우드에서 설정한 scope
            "https://www.googleapis.com/auth/userinfo.email",
            "openid"
        ])
    
    ```

4. 이제 cookie_transport로 만들어지 fastapi_users객체에서 `.get_oauth_router()`를 통해 oauth router를 생성 -> 반환해주는
   메서드를 `app/api/dependencies/auth.py`에서 구현한다.
    - **이 때, `redirect_url=`을 넣지 않으면, `자동생성되는 callback router`로 `로그인 성공 후 정보`를 가지고 알아서 redirect된다.**
    ```python
    def get_oauth_router():
        router = fastapi_users.get_oauth_router(
            oauth_client=google_oauth_client,
            backend=cookie_auth_backend,
            state_secret=JWT_SECRET,
            associate_by_email=True,
        )
        return router
    ```

5. 이제 `app/api/v1/auth/router.py`에서 router를 등록해준다.
    ```python
    # app/api/v1/auth/router.py
    router.include_router(
        router=get_oauth_router(),
        prefix='/users/jwt/google'
    )
    ```

6. **docs에 생긴 router는 `prefix를 포함한 router의 주소` + `/authorize` 및 `/callback` 2개의 router가 자동 완성되며**
    - **redirect_url은 내부에서 /callback router의 url을 `callback router name -> str(request.url_for())로 뽑아서 입력된다.**
    - /authorize를 docs에서 GET수동요청하면 아래와 같은 응답이 나온다.
    - **이 redirect_url은 `구글 인증서버 로그인 완 -> callback서버 redirect`로 되도록 인증서버 요청 url인 `authorize_url`의 querystring에 포함된다.**
       ```json
       {
       "data": {
         "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id=622493818735-g9gp89jisli2igf2qhkmanp4vgdtkbs4.apps.googleusercontent.com&redirect_uri=http%3A%2F%2Flocalhost%3A8001%2Fapi%2Fv1%2Fauth%2Fusers%2Fjwt%2Fgoogle%2Fcallback&state=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJmYXN0YXBpLXVzZXJzOm9hdXRoLXN0YXRlIiwiZXhwIjoxNjk1NDkzMzY4fQ.StayKyQeLcqqCk8C3-UymVz3CqyUPuOCGNESL9_FFJU&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuserinfo.profile+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuserinfo.email+openid"
       },
       "version": "1.0.0"
       }
       ```
       ```
       # &redirect_uri=http%3A%2F%2Flocalhost%3A8001%2Fapi%2Fv1%2Fauth%2Fusers%2Fjwt%2Fgoogle%2Fcallback
       ```

7. **이제 이 /callback으로 가는 `redirect_url`값을 /authorize에 GET요청으로 (front가 할 작업) 얻는 authorize_url에서 `redirect_url부분만 추출`한 뒤**
    - **`로컬용/테스트용` PORT변경(8000, 8001) 및 `실제 도메인(https://실제도메인/ ~)`까지 모든 경우의수의 callback url을 구글 인증앱에서 승인된 url로 등록해준다.**
    - **만약, 배포 도메인이 바뀌거나, 로컬/테스트의 PORT가 바뀌면 직접 구글 앱으로 와서 수정해야한다.**
      ![img.png](../images/48.png)

### 템플릿(Cookie) VS 풀스택(api Bearer) Oauth 정리

#### 템플릿 서버

![img.png](../images/49.png)

#### API 서버(frontend vs backend)

![img.png](../images/50.png)

### Cookie backend에서 /callback set_cookie된 204_NO_CONTENT response return후 종료 대신, RedirectResponse 되도록 수정
#### 원래 CookieTransport를 이용한 환경에선, cookie가 박힌 204_NO_CONTENT Response가 반환된다.
- Cookie Backend에서 /callback을 마치면, return되는 204_NO_CONTENT Response는 set_cookie가 반영X 체로 무한로딩 되며,  **redirect가 자동으로 안된다.**
    ```python
    class CookieTransport(Transport):
    
        def _set_login_cookie(self, response: Response, token: str) -> Response:
            response.set_cookie(
                self.cookie_name,
                token,
                max_age=self.cookie_max_age,
                path=self.cookie_path,
                domain=self.cookie_domain,
                secure=self.cookie_secure,
                httponly=self.cookie_httponly,
                samesite=self.cookie_samesite,
            )
            return response
    ```
    ```python
    class CookieTransport(Transport):
    
        async def get_login_response(self, token: str) -> Response:
                response = Response(status_code=status.HTTP_204_NO_CONTENT)
                return self._set_login_cookie(response, token)
    ```
    ```python
    class AuthenticationBackend(Generic[models.UP, models.ID]):
    
        async def login(
            self, strategy: Strategy[models.UP, models.ID], user: models.UP
        ) -> Response:
            token = await strategy.write_token(user)
            return await self.transport.get_login_response(token)
    ```
    ```python
    def get_oauth_router(
    
        oauth_client: BaseOAuth2,
        backend: AuthenticationBackend,
        get_user_manager: UserManagerDependency[models.UP, models.ID],
        state_secret: SecretType,
        redirect_url: Optional[str] = None,
        associate_by_email: bool = False,
        is_verified_by_default: bool = False,
    ) -> APIRouter:
        #...
       @router.get(
            "/callback",
            name=callback_route_name,
            description="The response varies based on the authentication backend used.",
            responses={
                #...
            },
        )
        async def callback(
            #...
            # Authenticate
            response = await backend.login(strategy, user)
            await user_manager.on_after_login(user, request, response)
            return response
    ```
  
#### callback이 204_NO_CONTENT면, google login이후 redirect없이 무한 로딩된다.
```shell
"GET /api/v1/auth/users/jwt/google/authorize HTTP/1.1" 200 OK
```
- authorize_url 값 복사 -> 붙혀넣기(front redirect 대신)
```shell
"GET /api/v1/auth/users/jwt/google/callback?state=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJmYXN0YXBpLXVzZXJzOm9hdXRoLXN0YXRlIiwiZXhwIjoxNjk1NTQwMzY4fQ.SVS14cyrqLSh-Gs2R55dK3H50ubcJLXUFRrBCUAIyWM&code=4%2F0AfJohXmjE5wZ95UUZbHUcWPHWyUGI62IGqdN5G1hX_RHvFky7tOENJc1lFYRBOxBzmz_qw&scope=email+profile+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuserinfo.profile+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuserinfo.email+openid&authuser=0&prompt=consent HTTP/1.1" 204 No Content
```
- callback으로 redirect 되었지만, Response자체가 Redirect X 204_NO_CONTENT Response라서 **쿠키만 set되어있는 무한로딩이 걸린다.**
    - **대신 `최초 요청한 url`에서는 coockie_name으로 `'Authorization='`이 자동으로 박혀있긴한다.**
    - **사실은, 알아서 직전 페이지로 리다이렉트 하는 것 같기도 하다.**

- **만약, redirect가 필요하다면 아래와 같이 Custom CookieTransport 클래스를 정의하고 사용한다.**
```python
class CookieRedirectTransport(CookieTransport):
    ...

    async def get_login_response(self, token: str) -> Any:
        response = RedirectResponse(config.FRONTEND_URL, 302)
        self._set_login_cookie(response, token)
        return response
    # or 
    async def get_login_response(self, token: str) -> Any:
        redirect_url = config.FRONTEND_URL

        response = await super().get_login_response(token)

        response.status_code = 302
        response.headers["Location"] = redirect_url

        return response
```
```python
cookie_auth_backend = AuthenticationBackend(
    name="jwt",
    # transport=get_cookie_transport(),
    transport=get_cookie_redirect_transport(),
    get_strategy=get_jwt_strategy,
)

```
```python
@dataclass
class Config(metaclass=SingletonMetaClass):
    #...
    FRONTEND_URL: str = f'https://{HOST_MAIN}'
    #...
    def __post_init__(self):

        # redirect시 필요한 프론트 URL 동적으로 만들기
        self.FRONTEND_URL: str = f'http://localhost:{self.PORT}/authenticated-route' if API_ENV != 'prod' \
            else f'https://{HOST_MAIN}'

```

### 템플릿서빙용 cookie backend의 name을 아예 jwt -> cookie로 변경 및 router들 정리하기

1. `login/logout`의 get_auth_routers()는 `auth_backend의 name`으로 prefix를 자동으로 붙이고 있는 상황이므로, 수정해준다.
    ```python
    def get_auth_routers():
        routers = []
    
        for auth_backend in get_auth_backends():
            routers.append({
                "name": auth_backend.name,
                "router": fastapi_users.get_auth_router(auth_backend),
            })
    
        return routers
    
    for auth_router in get_auth_routers():
        router.include_router(
            router=auth_router['router'],
            prefix=f"/users/{auth_router['name']}",
        )
    ```
    ```python
    cookie_auth_backend = AuthenticationBackend(
        # name="jwt",
        name="cookie",
        transport=get_cookie_transport(),
        # transport=get_cookie_redirect_transport(),
        get_strategy=get_jwt_strategy,
    )
    ```
   
2. `register`는 cookie든 Bearer방식이든 동일하므로 그대로 둔다.

3. get_users_router()로 인해 추가되는 5개 router는 auth라기보단 Users로 옮겨야한다.
    - 기존에 /users/me는 주석처리한다.
    ```python
    # /api/v1/users + @
    router = APIRouter()
    
    # fastapi-users
    router.include_router(
        router=get_users_router(),
        # prefix=''  # /me(get) + me(patch)  + {id}(get) + {id}(patch) + {id}(delete)
    )
    
    # @router.get('/me', response_model=UserMe)
    # async def get_user(request: Request, session: AsyncSession = Depends(db.session)):
    #     """
    #     get my info
    #     :param request:
    #     :return:
    #     """
    #     user_token = request.state.user
    #     user = await Users.get(session=session, id=user_token.id)
    #     return user
    
    ```
    - **추후, Bearer방식이 나오면, 수정하든지 자동 적용되도록**

4. google로그인의 prefix를 backend의 name으로 추출하고, 여러개 반영할 수 있도록 변경
    - **이 때, cookie와 bearer방식 서로 다르게 적용시키기 위해서, 각각 get_routers 메서드를 생성**
```python
google_oauth_client = GoogleOAuth2(
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    scopes=[
        "https://www.googleapis.com/auth/userinfo.profile",  # 구글 클라우드에서 설정한 scope
        "https://www.googleapis.com/auth/userinfo.email",
        "openid"
    ])

# app/libs/auth/oauth_clients.py
def get_oauth_clients():
    return [
        google_oauth_client,
    ]
```
```python
# app/api/dependencies/auth.py
def get_cookie_oauth_routers():
    routers = []

    for oauth_client in get_oauth_clients():
        routers.append({
            "name": cookie_auth_backend.name,
            "router": fastapi_users.get_oauth_router(
                oauth_client=oauth_client,
                backend=cookie_auth_backend,
                state_secret=JWT_SECRET,
                associate_by_email=True,
            )
        })

    return routers

def get_bearer_oauth_routers():
    routers = []

    for oauth_client in get_oauth_clients():
        ...

    return routers
```
```python
# app/api/v1/auth/router.py

# router.include_router(
#     router=get_oauth_router(),
#     prefix='/users/jwt/google'
# )
for oauth_router in get_cookie_oauth_routers():
    router.include_router(
        router=oauth_router['router'],
        prefix=f"/users/{oauth_router['name']}",
    )
```
5. oauth는 인증에도 /users가 들어갈 이유가 없어서, 다 빼준다.
    ```python
    # fastapi-users
    for oauth_router in get_auth_routers():
        router.include_router(
            router=oauth_router['router'],
            # prefix=f"/users/{oauth_router['name']}",
            prefix=f"/{oauth_router['name']}",
        )
        # /cookie/login + logout
    
    router.include_router(
        router=get_register_router(),
        # prefix='/users'  
    ) # /register
    ```
6. **추가로, 직접 cookie_auth_backend일땐, prefix로 들어갈 이름에 backed.name을 `clinet.name(google)` + `/` + `backend.name(cookie)`를 prefix로 준다.**
    ```python
    def get_cookie_oauth_routers():
        routers = []
    
        for oauth_client in get_oauth_clients():
            routers.append({
                "name": f'{oauth_client.name}/' + cookie_auth_backend.name ,
                "router": fastapi_users.get_oauth_router(
                    oauth_client=oauth_client,
                    backend=cookie_auth_backend,
                    state_secret=JWT_SECRET,
                    associate_by_email=True,
                )
            })
    
        return routers
    ```
    ```python
    for oauth_router in get_cookie_oauth_routers():
        router.include_router(
            router=oauth_router['router'],
            # prefix=f"/users/{oauth_router['name']}",
            prefix=f"/{oauth_router['name']}",
        )
    ```
   
    ![img.png](../images/51.png)
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