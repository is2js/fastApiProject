- 참고 유튜브: https://www.youtube.com/watch?v=WI9eGCCP5-c&t=524s
### 수정 : associate_by_email, is_verified_by_default
- `associate_by_email=True` : sns로그인시, 이미 email가입이 있어도, oauth_account로 등록을 허용한다.
- `is_verified_by_default=True`, # sns로그인한 사람이라면 email인증을 안거쳐도 `is_verified`가 True로 등록된다.
- **sns로그인에 관련하는 `is_verified_by_default`의 인자를 모두 True로 바꾸자**
1. `app/api/dependencies/auth.py`에서 get_oauth_routers() 메서드내 모든 router 생성 정보에서 추가
    ```python
    def get_oauth_routers():
        routers = []
    
        for oauth_client in get_oauth_clients():
            if isinstance(oauth_client, GoogleOAuth2):
                for backend in get_google_backends():
                    routers.append({
                        "name": f'{oauth_client.name}/' + backend.name,
                        "router": fastapi_users.get_oauth_router(
                            oauth_client=oauth_client,
                            backend=backend,
                            state_secret=JWT_SECRET,
                            associate_by_email=True,  # 이미 존재하는 email에 대해서 sns로그인시 oauth_account 정보 등록 허용(이미존재pass)
                            is_verified_by_default=True,  # 추가: sns 로그인시, email인증 안하고도 이메일인증(is_verified) True 설정
                        )
                    })
            #...
    ```
2. 직접적으로 `sns로그인`을 책임지는 `callback route직접구현`장소로서, oauth계정 등록시, user_manager.oauth_callback()을 호출하는 곳인
    - app/pages/discord.py에서도 추가
    ```python
    @router.get("/callback", name='discord_callback')
    async def discord_callback(
            request: Request,
            code: str,
            user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
    ):
        #...
        try:
            user = await user_manager.oauth_callback(
                oauth_name='discord',
                access_token=oauth2_token.get("access_token"),
                account_id=account_id,
                account_email=account_email,
                expires_at=oauth2_token.get("expires_at"),
                refresh_token=oauth2_token.get("refresh_token"),
                request=request,
                associate_by_email=True, # sns로그인시, 이미 email가입이 있어도, oauth_account로 등록을 허용한다.
                # is_verified_by_default=False,
                is_verified_by_default=True, # sns로그인 성공할 사람이면 is_verified True로 이메일 인증 pass.
            )
        #...
    ```
### template 로그인여부 확인을 위한 optional_current_user 디펜던시 
- 참고: https://github.com/fastapi-users/fastapi-users/discussions/764
1. dependency를 정의해준다.
    ```python
    optional_current_active_user = fastapi_users.current_user(
        active=True,
        optional=True,
    )
    ```

2. 로그인 여부를 확인할 dashobard.html에서 주입하여 template의 context로 던진다
```python
@router.get("/dashboard")
async def discord_dashboard(request: Request, user: Users = Depends(optional_current_active_user)):
    #...
    context = {
        'request': request,  # 필수
        ),
        'user': user, # None or user
    }
    return templates.TemplateResponse(
        "discord_dashboard.html",
        context
    )
```

### state=를 통한 oauth 로그인시 next=요청url을 전달하여 redirect
- 참고
   - 스택: https://stackoverflow.com/questions/58858066/pass-a-string-through-discord-oauth
   - 예시: Passing variables through oAuth 2.0 : https://levbuchel.com/passing-variables-through-oauth/

#### fastapi-users는 state처리를 어떻게 하는지 보자.

1. oauth route 중 /authorize를 보면, `user.id`를 str로 만든 뒤, `sub=`의 value로 넣은 dict를 `state_data`로 취급하고
    - `aud=`에 fastapi-users 상수인 `fastapi-users:oauth-state`를 value로 추가하여 **`sub= user_id, aud=상수 를 넣은 dict`를 `generate_state_token`메서드로 `jwt로 1개의 string으로 encoding`한다.**
    ```python
    # venv/Lib/site-packages/fastapi_users/router/oauth.py
    STATE_TOKEN_AUDIENCE = "fastapi-users:oauth-state"
    
    
    class OAuth2AuthorizeResponse(BaseModel):
        authorization_url: str
    
    
    def generate_state_token(
        data: Dict[str, str], secret: SecretType, lifetime_seconds: int = 3600
    ) -> str:
        data["aud"] = STATE_TOKEN_AUDIENCE
        return generate_jwt(data, secret, lifetime_seconds)
    
    
    # venv/Lib/site-packages/fastapi_users/router/oauth.py
    @router.get(
        "/authorize",
        name=f"oauth:{oauth_client.name}.{backend.name}.authorize",
        response_model=OAuth2AuthorizeResponse,
    )
    async def authorize(
        request: Request,
        scopes: List[str] = Query(None),
        user: models.UP = Depends(get_current_active_user),
    ) -> OAuth2AuthorizeResponse:
        if redirect_url is not None:
            authorize_redirect_url = redirect_url
        else:
            authorize_redirect_url = str(request.url_for(callback_route_name))
    
        state_data: Dict[str, str] = {"sub": str(user.id)}
        state = generate_state_token(state_data, state_secret)
        authorization_url = await oauth_client.get_authorization_url(
            authorize_redirect_url,
            state,
            scopes,
        )
    ```
   
2. `httpx_oauth`패키지의 각 oauth_client에서 get_authorization_url()을 호출할 때, `jwt encoding된 state(str)`를 받아서
    - **각 oauth마다 고유 auhorization_url에 `urlencode()`메서드를 활용하여 `querystring`으로 붙혀넣는다.**
    ```python
    # venv/Lib/site-packages/httpx_oauth/oauth2.py:
    class BaseOAuth2(Generic[T]):
    
        async def get_authorization_url(
            self,
            redirect_uri: str,
            state: Optional[str] = None,
            scope: Optional[List[str]] = None,
            extras_params: Optional[T] = None,
        ) -> str:
            params = {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
            }
            if state is not None:
                params["state"] = state
            return f"{self.authorize_endpoint}?{urlencode(params)}"
    ```
   
3. 인증서버에서 authorization_url에 포함된 redirect_uri인 callback route로 내려오는 순간
    - callback 디펜던시에 의해 access_token과 `state`를 받은 뒤, **`decode_jwt()`로 다시 sub=,aud=의 dict를 반환받는다.**
    ```python
    @router.get(
        "/callback",
        name=callback_route_name,
    async def callback(
        request: Request,
        access_token_state: Tuple[OAuth2Token, str] = Depends(
            oauth2_authorize_callback
        ),
        user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
        strategy: Strategy[models.UP, models.ID] = Depends(backend.get_strategy),
    ):
        #...
        token, state = access_token_state
    
        try:
            decode_jwt(state, state_secret, [STATE_TOKEN_AUDIENCE])
        except jwt.DecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    
    ```
   
4. fastapi-users는 디펜던시에 의해 `code=`와 `state=`를 내부에서 받아, access_token과 state를 한번에 받아왔지만
    - **인증서버 callback 들어올 때 `code=`필수값 외에 `state=`도 같이 내려오므로, `route 인자로 qs state:str`를 받아주면 된다.**
    ```python
    class OAuth2AuthorizeCallback:
        client: BaseOAuth2
        route_name: Optional[str]
        redirect_url: Optional[str]
    
        def __init__(
            self,
            client: BaseOAuth2,
            route_name: Optional[str] = None,
            redirect_url: Optional[str] = None,
        ):
            assert (route_name is not None and redirect_url is None) or (
                route_name is None and redirect_url is not None
            ), "You should either set route_name or redirect_url"
            self.client = client
            self.route_name = route_name
            self.redirect_url = redirect_url
    
        async def __call__(
            self,
            request: Request,
            code: Optional[str] = None,
            code_verifier: Optional[str] = None,
            state: Optional[str] = None,
            error: Optional[str] = None,
        ) -> Tuple[OAuth2Token, Optional[str]]:
            if code is None or error is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error if error is not None else None,
                )
    
            if self.route_name:
                redirect_url = str(request.url_for(self.route_name))
            elif self.redirect_url:
                redirect_url = self.redirect_url
    
            access_token = await self.client.get_access_token(
                code, redirect_url, code_verifier
            )
    
            return access_token, state
    ```

#### 우리는...
1. `authrization_url`을 만들어 template에 전해주는데, **`state_date(dict) -> jwt encoding -> query_string`으로 추가**해서 반환해줘야한다.
    - 현재요청 url인 `request.url`을 `next=`에 넣어서 state_date(dict)를 만들고,
    - fastapi-users의 `generate_state_token()` 이용해서 jwt로 만들어야한다.
    - discord제공 url을 update_query_string()으로 처리했으니, 마찬가지로 사용해서 `state=`로 넣어주는 메서드를 만든다.
    - 이 과정을 `discord_client`에 `.get_authorization_url()`메서드로 통합한다.
    ```python
    context = {
    
        'authorize_url': await discord_client.get_authorization_url(
            redirect_uri=str(request.url_for('discord_callback')),
            state_data=dict(next=str(request.url)),
        ),
    }
    ```
    ```python
    # app/libs/discord/oauth_client.py
    class DiscordClient:
    
        authorization_url: str
    
        def __init__(self, client_id: str, client_secret: str, authorization_url: str):
            self.client_id = client_id
            self.client_secret = client_secret
            self.authorization_url = authorization_url
    
        async def get_authorization_url(
                self,
                redirect_uri: str,
                state_data: Dict[str, str] = None,
        ) -> str:
    
            self.authorization_url = update_query_string(
                self.authorization_url,
                redirect_uri=redirect_uri,
                state=generate_state_token(state_data, JWT_SECRET) if state_data else None
            )
    
            return self.authorization_url
        
    discord_client = DiscordClient(
        client_id=DISCORD_CLIENT_ID,
        client_secret=DISCORD_CLIENT_SECRET,
        authorization_url=DISCORD_GENERATED_AUTHORIZATION_URL,
    )
    ```
   
2. **callback route에서는 인증서버에서 넘어오는 query_string `code=`이외에 `state=`까지 추가로 route에서 인자로 받아준다.**
    - **넘어온 state(jwt)를 decode_jwt()으로 dict로 만들고, 여기서 `fastapi-users aud=`외에 `next=`를 뽑아서, redirect cookie transport에 넣어서, 그것으로 redirect되게 한다.**
    ```python
    @router.get("/callback", name='discord_callback')
    async def discord_callback(
            request: Request,
            code: str,
            state: Optional[str] = None,
            user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
    ):
        #...
        try:
            decode_jwt(state, JWT_SECRET, [STATE_TOKEN_AUDIENCE])
            next_url = decode_jwt(state, JWT_SECRET, [STATE_TOKEN_AUDIENCE])['next'] if state \
                else str(request.url_for('discord_dashboard'))
        except jwt.DecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
        
        #...
        cookie_redirect_transport = get_cookie_redirect_transport(
            redirect_url=next_url  # 로그인 성공 후 cookie정보를 가지고 돌아갈 곳.
        )
    
        response = await cookie_redirect_transport.get_login_response(user_token_for_cookie)
    
        return response
    ```

#### code와 state qs를 받아 한번에 access_token 및 decode된 state속 next_url을 반환하는 discord_callback 디펜던시 객체 만들기
1. fastapi-users의 oauth /callback route에서 `OAuth2AuthorizeCallback`객체를 만들고, dependency로서, code 등을 받아 처리하는 것을 모방한다.
    - callback객체 생성시 생성자에서 `client`, `route_name or redirect_url`를 받아서, 
    - **clinet -> 내부에 client_id, secret, authorize_url을 내포하고 있으며, call메서드에서 dependency로서 받을 `code`값과 같이 access_token를 요청해서 얻음**
    - **route_name or redirect_url -> 인증서버가 access_token요청시 필요한 callback route의 url인 redirect_uri를 정의한다.**
    - **추가로 fastapi-users는 state(encoding str)을 그대로 반환하는데 반면, 나는 state를 decoding해서 next_url을 얻고, 없으면 `config.HOST_MAIN`으로 redirect시킨다.**
    - **fastapi-users는 callback 객체를 생성할 때, route내에서 callback route의 주소인 redirect_url을 받는데, 나는 메서드에서 받아서 객체를 생성하는 동시에 주입한다.**
    ```python
    from typing import Optional, Tuple
    
    import jwt
    from fastapi_users.jwt import decode_jwt
    from fastapi_users.router.oauth import STATE_TOKEN_AUDIENCE
    from httpx_oauth.oauth2 import OAuth2Token
    from starlette import status
    from starlette.exceptions import HTTPException
    from starlette.requests import Request
    
    from app.common.config import JWT_SECRET, config
    from app.libs.discord.pages.oauth_client import DiscordClient, discord_client
    
    
    class DiscordAuthorizeCallback:
        client: DiscordClient  # BaseOAuth2
        route_name: Optional[str]
        redirect_url: Optional[str]
    
        def __init__(
                self,
                client: DiscordClient,
                route_name: Optional[str] = None,
                redirect_url: Optional[str] = None,
        ):
            assert (route_name is not None and redirect_url is None) or (
                    route_name is None and redirect_url is not None
            ), "You should either set route_name or redirect_url"
            self.client = client
            self.route_name = route_name
            self.redirect_url = redirect_url
    
        # dependency에 들어갈 객체용
        async def __call__(
                self,
                request: Request,
                code: Optional[str] = None,
                state: Optional[str] = None,
                error: Optional[str] = None,
        ) -> Tuple[OAuth2Token, Optional[str]]:
    
            if code is None or error is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error if error is not None else None,
                )
    
            if self.route_name:
                redirect_url = str(request.url_for(self.route_name))
            elif self.redirect_url:
                redirect_url = self.redirect_url
    
            access_token: OAuth2Token = await self.client.get_access_token(
                code=code, redirect_uri=redirect_url
            )
    
            # return access_token, state
    
            # 추가로 로직 -> state에 next=가 있으면 여기서 빼주기
            try:
                next_url = decode_jwt(state, JWT_SECRET, [STATE_TOKEN_AUDIENCE])['next'] if state \
                    else config.HOST_MAIN
            except jwt.DecodeError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    
            return access_token, next_url
    
    
    def get_discord_callback(redirect_url: Optional[str] = None, route_name: Optional[str] = None):
        return DiscordAuthorizeCallback(
            discord_client,  # client_id, secret + authorization_url 기본 포함. -> access_token을 받아냄.
            redirect_url=redirect_url,  # 2개 중 1개로 client가 access_token요청시 필요한 redirect_uri을 만듦
            route_name=route_name,
        )
    
    ```
2. **이제 callback route에서 `route_name=`을 입력해서 만든 callable 객체 디펜던시를 만들어서, 주입하여, code=, state=를 내부에서 받는다.** 
    ```python
    @router.get("/callback", name='discord_callback')
    async def discord_callback(
            request: Request,
            # code: str,
            # state: Optional[str] = None,
            access_token_and_next_url: DiscordAuthorizeCallback = Depends(
                get_discord_callback(route_name='discord_callback')
            ),  # 인증서버가 돌아올떄 주는 code와 state를 내부에서 받아 처리
            user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
    ):
        oauth2_token, next_url = access_token_and_next_url
        #...
    ```
   
### CustomAPIRoute with error_handler

#### app에만 있는 error_handler를 CustomAPIRoute 구현으로 특정route의 401에러를 잡아 redirect
- 참고: [how to use customer exception handler by APIRouter? #1667](https://github.com/tiangolo/fastapi/issues/1667)
1. **@app.error_handler(특정에러) -> 로그인 요구 router에서 user: Users = Depends(current_active_user)시 로그인 에러 -> 401에러 -> 인증화면(authorization_url)로 redirect를 쓰려고 했다.**
2. 하지만, **`pages의 discord관련 route에서만` 잡고 싶었다. 그렇지 않다면, 특정 exception을 생성하고 -> @app.error_handler에서 해당 exception만 잡아서 처리하면 되었다.**
    - raise RedirectExcept(redirect_url) -> 해당 error 시 redirect
3. **discord로그인 관련, 정보 route들만 처리되면 되므로, 특정Route에서 error_handler를 대신하는 방법은**
    1. APIRoute를 상속한 route custom class를 정의한다.
    2. `get_route_handler`를 재정의한 뒤, `super().get_route_handler()`를 통해, callable 원본 router handler객체를 반환 받고
    3. get_route_handler 메서드 내부에서 `async def custom_route_handler`를 재정의하는데
    4. try: 그냥 돌려보내주고, except 에러를 잡는데, 특정에러 발생시 특정처리 후 `return response`를 만들어서 반환해준다.
    5. **해당 route를 APIRouter(route_class=)객체 생성시 `route_class=`옵션으로 넣어준다.**
    ```python
    class DiscordRoute(APIRoute):
        
        def get_route_handler(self) -> Callable:
            original_route_handler = super().get_route_handler()
            
            async def custom_route_handler(request: Request) -> Response:
                app = request.app
                try:
                    return await original_route_handler(request)
                except Exception as exc:
                    # 특정에러 확인
                    # 특정에러시 처리
            return custom_route_handler
    ```
    ```python
    # app/pages/discord.py
    router = APIRouter(route_class=DiscordRoute)
    ```

#### 로그인요구 route가 포함된 router객체에서 401에러시 authorization_url로 redirect처리를 해줄 CustomRouter 정의하기
1. libs > discord > 에 bot용 파일을 /bot 폴더에, pages전용으로서 `pages`패키지안에 route.py를 생성하여 custom route인 `DiscordRoute`를 정의한다.
    - **이 때, `custom_route_handler`를 정의하는데, 다른 exception외에 `HTTPException`이면서, `401 권한에러`가 뜨면**
    - **discord_client로 현재route요청 url인 `request.url`을 str()으로 state_data에 넣은 authorizaion_url을 생성하여 redireect시킨다.**
    ```python
    # app/libs/discord/pages/route.py
    from typing import Callable
    
    from fastapi import HTTPException
    from fastapi.routing import APIRoute
    from starlette import status
    from starlette.requests import Request
    from starlette.responses import Response, RedirectResponse
    
    from app.libs.discord.pages.oauth_client import discord_client
    
    class DiscordRoute(APIRoute):
        def get_route_handler(self) -> Callable:
            original_route_handler = super().get_route_handler()
            async def custom_route_handler(request: Request) -> Response:
                app = request.app
                try:
                    return await original_route_handler(request)
                except Exception as e:
                    if isinstance(e, HTTPException) and e.status_code == status.HTTP_401_UNAUTHORIZED:
                        authorization_url: str = await discord_client.get_authorization_url(
                            redirect_uri=str(request.url_for('discord_callback')),
                            state_data=dict(next=str(request.url))
                        )
                        return RedirectResponse(authorization_url)
    
                    raise e
    
    
            return custom_route_handler
    ```
   
2. 이제 pages > discord.py의 router 객체에 `route_class=`를 넣어줘서, 커스텀 error_handler(`custom_route_handler`)가 해당 route에만 작동할 수 있게 한다.
    ```python
    # app/pages/discord.py
    router = APIRouter(route_class=DiscordRoute)
    ```
   
3. **로그인이 요구되는 `/guilds` 페이지에는 optional_current_active_user가 아닌 `current_active_user`를 주입하고, 로그인 안될시 내부에서 401에러가 발생하는데, 그것을 잡아서 redirect되게 한다.**
    ```python
    @router.get("/guilds")
    # async def guilds(request: Request, user: Users = Depends(optional_current_active_user)):
    async def guilds(request: Request, user: Users = Depends(current_active_user)):
        #...
    ```
   
4. 이제 /discord/guilds에 접속하면 로그인안됬으므로 자동으로 디스코드 로그인페이지로 이동후, 다시 state=에 적힌 요청route /discord/guilds로 돌아오게 된다.
5. **문제는 logout시 현재페이지로 로그아웃되는데, 또 로그인 안된 상태라, 디스코드 로그인 화면으로 간다.**
    - **`로그아웃`시 `비로그인 허용`route인 `/index`페이지가 필요하다.**
    - 기존의 /dashboard 대신, home이 필요하긴 한 것 같다.
    - **또한, 추후, 여러 로그인이 필요한 곳을 위해, /login 페이지도 필요한 것 같다.**


#### dashboard를 base.html로 취급한, guilds.html
```python

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