- 참고 유튜브: https://www.youtube.com/watch?v=WI9eGCCP5-c&t=524s

### cookie

1. 현재까지 상황
    - dashboard.html의 로그인 페이지
    - front에서 `autrhoization_url` with redirect_url(callback router)-> `인증서버` oauth로그인 요청 -> redirect callback route
    - -> code in qs -> access_token 요청 with grant_type/code/client_id, secret -> `access_token`
    - **`빠진 것`: access_token을 user DB에 저장 -> user정보 jwt encoding `user token`-> response에 `set_cookie user_token` + Redirect 정보페이지('/discord/guilds')**
    - **`빠진 것2` : -> redirect된 정보 route로 온 request.cookies에서 user_token 확인 -> DB속 `access_token` 추출** 
    - -> access_token으로 `정보서버` oauth user정보 요청 -> 필요한 정보(guilds) 취득
    - **`빠진 것3`: -> 취득한 정보들을 정보 template에 `정보html + 정보data`를 뿌려주기**

2. 문제점
    - cookie에 user token을 심으면, front에서 decode_jwt( user token ) 바로 정보를 추출할 수 있지만, `fastapi-user의 cookie와 달라, get_current_user 디펜던시 연동은 안됨`**
    - **Bearer방식은, user_token을 내려보내주는 게 fastapi-users도 동일하나, `Cookie방식만, user_token이 아닌 자체 token`을 strategy객체로 만드는 듯하다.**
    - 일반 user객체를 jwt로 encoding하면 아래와 같은 예시가 나오지만, `jwt.io`에서 확인해본다.
        ```json
        {
          "id": 5,
          "email": "user@example.com",
          "name": null,
          "phone_number": null,
          "profile_img": null,
          "sns_type": "email"
        }
        ```
    - **cookie로 response받은 token을 decode해보면, `아래와 같이 aud가 붙어있고, sub와 만료기한이 자체적으로 표시`된다.**
        - GET /api/v1/auth/discord/cookie/authorize -> 로그인 후, rest api용으로서 redirect되지 않아서, 뒤로가기 한번 클릭하면, cookie에 들어가있다. 
        ```json
        {
          "sub": "4",
          "aud": [
            "fastapi-users:auth"
          ],
          "exp": 1696411043
        }
        ```
3. **해결법**
    - **빠진 부분에서 user + oauth_account 등록을 `UserManager` 디펜던스의 `.oauth_callback()`메서드를 이용해서 처리하고**
    - **`자체 jwt_encode() + user객체를 이용한 create_access_token( user)`로 user token을 만드는 대신**
    - **백엔드로 넣어줬던 CookieBackend에서 사용중인 `strategy객체.write_token(user)`를 이용해서, `fastapi-users용 user_token`을 만들고**
    - **백엔드로 넣어줬던 CookieBackend에서 사용중인 `cookie transport객체.get_login_response( fastapi-users user_token)`으로 response를 만들어서 반환한다.**
    - **이 때, 특정 route로 Redirecet시켜주는 response(원래는 NoContent  no redirect)를 만들기 위해, `Custom RedirectCookieTransport class`를 정의해서 사용한다.**

#### callback route에서 code로 만든 access_token(in OAuth2Token) 을 이용하여 UserManager도 Users+OAuthAccount 동시 자동 생성
1. `get_user_manager` 디펜던시를 callback route에 입혀서, user 생성을 준비한다.
    ```python
    @router.get("/callback", name='discord_callback')
    async def discord_callback(
            request: Request,
            code: str,
            user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
    ):
    ```

2. fastapi-user의 callback router를 만들 때, user db를 생성하는데 사용된 로직인 `user_manager.oauth_callback()`를 가져온다.
    ```python
    @router.get("/callback", name='discord_callback')
    async def discord_callback(
            request: Request,
            code: str,
            user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
    ):  
        #...
        
        # 4-1. fastapi-users callback route 로직 
        # - venv/Lib/site-packages/fastapi_users/router/oauth.py
        try:
            user = await user_manager.oauth_callback(
                oauth_name='discord',
                access_token=oauth2_token.get("access_token"),
                account_id=account_id,
                account_email=account_email,
                expires_at=oauth2_token.get("expires_at"),
                refresh_token=oauth2_token.get("refresh_token"),
                request=request,
                associate_by_email=True,
                is_verified_by_default=False,
            )
    
        except UserAlreadyExists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorCode.OAUTH_USER_ALREADY_EXISTS,
            )
    
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorCode.LOGIN_BAD_CREDENTIALS,
            )
    
    ```
   
3. 이 때, oauth_callback 메서드는 access_token 이외에 `discord의 id와 email`을 요구하는데, 
    - oauth_client들을 만들어낸 `httpx_oauth.oauth2 import BaseOAuth2` 내부의 get_id_email을 그대로 가져와서 `discord_client`에 메서드로 정의해서 사용하게 한다.
    ```python
    class DiscordClient:
        #...
        async def get_id_email(self, token: str) -> Tuple[str, Optional[str]]:
            async with self.get_httpx_client() as client:
                response = await client.get(
                    PROFILE_ENDPOINT,
                    headers={**self.request_headers, "Authorization": f"Bearer {token}"},
                )
    
                if response.status_code >= 400:
                    raise GetIdEmailError(response.json())
    
                data = cast(Dict[str, Any], response.json())
    
                user_id = data["id"]
                user_email = data.get("email")
    
                return user_id, user_email
    ```
    ```python
    @router.get("/callback", name='discord_callback')
    async def discord_callback(
            request: Request,
            code: str,
            user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
    ):
        #...
        
        # 4-2. httx_oauth의 각 oauth client에서 공통으로 사용하는 메서드
        # - venv/Lib/site-packages/httpx_oauth/clients/discord.py
        account_id, account_email = await discord_client.get_id_email(oauth2_token["access_token"])
    
        try:
            user = await user_manager.oauth_callback(
                oauth_name='discord',
                access_token=oauth2_token.get("access_token"),
                account_id=account_id,
                account_email=account_email,
                expires_at=oauth2_token.get("expires_at"),
                refresh_token=oauth2_token.get("refresh_token"),
                request=request,
                associate_by_email=True,
                is_verified_by_default=False,
            )
    
        except UserAlreadyExists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorCode.OAUTH_USER_ALREADY_EXISTS,
            )
    
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorCode.LOGIN_BAD_CREDENTIALS,
            )
    ```
   

4. discord_backend에서 UserManager에서 사용되는 on_after_login 내부속 프로필 정보를 추가로 가져왔던 get_profile_info() 메서드도 가져와서 적용해준다.
    ```python
    class DiscordClient:
        #...
        async def get_profile_info(self, access_token):
            async with self.get_httpx_client() as client:
                response = await client.get(
                    PROFILE_ENDPOINT,
                    # params={},
                    headers={**self.request_headers, "Authorization": f"Bearer {access_token}"},
                )
                if response.status_code >= 400:
                    raise GetOAuthProfileError()
    
                profile_dict = dict()
    
                data = cast(Dict[str, Any], response.json())
                if avatar_hash := data.get('avatar'):
                    profile_dict['profile_img'] = f"https://cdn.discordapp.com/avatars/{data['id']}/{avatar_hash}.png"
                if nickname := data.get('global_name'):
                    profile_dict['nickname'] = nickname
    
            return profile_dict
    ```
    ```python
    @router.get("/callback", name='discord_callback')
    async def discord_callback(
            request: Request,
            code: str,
            user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
    ):
        # 4-2. httx_oauth의 각 oauth client에서 공통으로 사용하는 메서드
        # - venv/Lib/site-packages/httpx_oauth/clients/discord.py
        account_id, account_email = await discord_client.get_id_email(oauth2_token["access_token"])
    
        # 4-1. fastapi-users callback route 로직
    
        try:
            user = await user_manager.oauth_callback(
        #...
    
        # 4-3. backend에서 oauth_client에서 못가져온 추가정보 가져오는 로직도 추가한다.
        # - app/libs/auth/backends/oauth/discord.py
        try:
            if profile_info := await discord_client.get_profile_info(oauth2_token["access_token"]):
                await user.update(auto_commit=True, **profile_info, sns_type='discord')
        except Exception as e:
            raise OAuthProfileUpdateFailException(obj=user, exception=e)
    ```
   
#### 쿠키용 user_token을 jwt encoding하지않고, fastapi-users의 Strategy객체로 encoding하기
- 연동을 위해서 직접 하지 않고, fastapi-users의 jwt encoding for cookie backend 를 활용한다.
    ```python
    @router.get("/callback", name='discord_callback')
    
    async def discord_callback(
            request: Request,
            code: str,
            user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
    ):
        # 4-4. 쿠키용 user_token을 jwt encoding하지않고, fastapi-users의 Strategy객체로 encoding하기
        # token_data = UserToken.model_validate(user).model_dump(exclude={'hashed_password', 'marketing_agree'})
        # token = await create_access_token(data=token_data)
        jwt_strategy = get_jwt_strategy()
        user_token_for_cookie = await jwt_strategy.write_token(user)  
        # {
        #   "sub": "4",
        #   "aud": [
        #     "fastapi-users:auth"
        #   ],
        #   "exp": 1696397563
        # }
    ```

5. backend login을 끝나고 user_manager 내부에 on_after_login에 정의한 `last_seen` 필드 업뎃도 여기서 해준다.
    ```python
    await user.update(
        auto_commit=True,
        **profile_info,
        sns_type='discord',
        last_seen=D.datetime(), # on_after_login에 정의된 로직도 가져옴
    )
    ```

#### 직접 Redirect Response를 만들지 않고, fastapi-users의 쿠키용 Response제조를 위한 Cookie Transport를 Cusotm해서 Response를 만든다.
1. 원래 BaseBackend인 AuthenticatinoBackend는 `transport` + `strategy` 2개를 받아
    - login시  strategy로 `.write_token( user )` + transport로 `.get_login_response( token )`
    - logout시 strategy로 `.destroy_token( token, user)` + transport로 `.get_login_response()`를 수행한다.
    ```python
    class AuthenticationBackend(Generic[models.UP, models.ID]):
    
        name: str
        transport: Transport
    
        def __init__(
            self,
            name: str,
            transport: Transport,
            get_strategy: DependencyCallable[Strategy[models.UP, models.ID]],
        ):
            self.name = name
            self.transport = transport
            self.get_strategy = get_strategy
    
        async def login(
            self, strategy: Strategy[models.UP, models.ID], user: models.UP
        ) -> Response:
            token = await strategy.write_token(user)
            return await self.transport.get_login_response(token)
    
        async def logout(
            self, strategy: Strategy[models.UP, models.ID], user: models.UP, token: str
        ) -> Response:
            try:
                await strategy.destroy_token(token, user)
            except StrategyDestroyNotSupportedError:
                pass
    
            try:
                response = await self.transport.get_logout_response()
            except TransportLogoutNotSupportedError:
                response = Response(status_code=status.HTTP_204_NO_CONTENT)
    
            return response
    ```
2. 외부(route)에서 redirect_url을 입력할 수 있게 `CookieTransport`를 상속하여 `외부인자로는 redirect_url`을, 받고
    - **`get_login_response( token )`메서드를 재정의해서, `.get_login_reponse( token )`시 반환되는 response에 `.headers['Location']`으로 redirect_url을 넣어준다.**
    ```python
    # app/libs/auth/transports.py:
    class CookieRedirectTransport(CookieTransport):
        ...
        redirect_url: str
    
        def __init__(self, redirect_url,
                     cookie_name: str = "fastapiusersauth", cookie_max_age: Optional[int] = None,
                     cookie_path: str = "/", cookie_domain: Optional[str] = None, cookie_secure: bool = True,
                     cookie_httponly: bool = True, cookie_samesite: Literal["lax", "strict", "none"] = "lax",
                     ):
            super().__init__(cookie_name, cookie_max_age, cookie_path, cookie_domain, cookie_secure, cookie_httponly,
                             cookie_samesite)
    
            self.redirect_url = redirect_url
    
        async def get_login_response(self, token: str) -> Any:
            response = await super().get_login_response(token)
    
            response.status_code = status.HTTP_302_FOUND
    
            # 생성시, request.url_for('라우트명')을 입력할 시, URL객체가 들어와 에러나므로 str() 필수
            response.headers["Location"] = str(self.redirect_url) if not isinstance(self.redirect_url, str) \
                else self.redirect_url
    
            return response
   
   
    def get_cookie_redirect_transport(redirect_url):
        return CookieRedirectTransport(
            redirect_url,
            cookie_name='Authorization',
            cookie_max_age=USER_AUTH_MAX_AGE,
        )
    ```
   - **부모의 인자와 사용을 그대로 할 땐, args, kwargs를 활용한다**
   ```python
    class CookieRedirectTransport(CookieTransport):
        ...
        redirect_url: str
    
        def __init__(self, redirect_url, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.redirect_url = redirect_url
        #...
    ```
3. **이제 callback route에서 custom transport객체를 생성하여, `redirect가 적용된 response`를 반환받아 return한다.**
    ```python
    @router.get("/callback", name='discord_callback')
    async def discord_callback(
            request: Request,
            code: str,
            user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
    ):
        #...
        jwt_strategy = get_jwt_strategy()
        user_token_for_cookie = await jwt_strategy.write_token(user)
        
        # 5. 직접 Redirect Response를 만들지 않고, fastapi-users의 쿠키용 Response제조를 위한 Cookie Transport를 Cusotm해서 Response를 만든다.
        # 3. 데이터를 뿌려주는 api router로 Redirect시킨다.
        # return RedirectResponse(url='/guilds')
        cookie_redirect_transport = get_cookie_redirect_transport(
            redirect_url=request.url_for('guilds') # 로그인 성공 후 cookie정보를 가지고 돌아갈 곳.
        )
        response = await cookie_redirect_transport.get_login_response(user_token_for_cookie)
    
        return response
    ```


#### cookie가 심어진 response를 Redirect받은 정보 route에서는 current_active_user 디펜던시를 통해 cookie를 직접 안뒤져도, 내부에서 user 객체까지 뽑아서 온다.
1. api > dependencies > auth.py에 fastapi_users.current_user()로 dependencty를 반환받고, 사용해준다.
    ```python
    # app/api/dependencies/auth.py
    current_active_user = fastapi_users.current_user(
        active=True,
    )
    ```
    ```python
    @router.get("/guilds")
    async def guilds(request: Request, user: Users = Depends(current_active_user)):
        #...
    
    ```
   
2. 이제 discord_client.get_guilds( token )요청시 필요한 **user token이 아닌 `access_token`을 user객체(db)에서 꺼내와야한다.**
    - joined로 연결된 oauth_account이므로, 가져오는 메서드를 Users모델에 정의하고 뽑아올 수 이게 한다.
    ```python
    class Users(BaseModel, SQLAlchemyBaseUserTable[int]):
        #...
        def get_oauth_access_token(self, oauth_name: str):
            """
            lazy="joined"되어 session 없이, oauth_accounts 모델에서 특정 oauth의 access_token을 얻는 메서드
            """
            for existing_oauth_account in self.oauth_accounts:
                if existing_oauth_account.oauth_name == oauth_name:
                    return existing_oauth_account.access_token
    
            return None
    ```
    ```python
    @router.get("/guilds")
    async def guilds(request: Request, user: Users = Depends(current_active_user)):
        # discord_access_token = ''
        # for existing_oauth_account in user.oauth_accounts:
        #     if existing_oauth_account.oauth_name == 'discord':
        #         discord_access_token = existing_oauth_account.access_token
        
        access_token = user.get_oauth_access_token('discord')
    
        guilds = await discord_client.get_guilds(access_token)
        return dict(guilds=guilds)
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