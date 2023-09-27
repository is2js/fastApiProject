### discord

- 전체
  참고: https://velog.io/@pung8146/%EB%94%94%EC%8A%A4%EC%BD%94%EB%93%9C-%EC%86%8C%EC%85%9C%EB%A1%9C%EA%B7%B8%EC%9D%B8-%EB%B0%A9%EB%B2%95
- scope
  참고 : https://velog.io/@pung8146/%EB%94%94%EC%8A%A4%EC%BD%94%EB%93%9C-OAuth2-URL-%EA%B6%8C%ED%95%9CSCOPE-%EB%AA%A9%EB%A1%9D

#### discord 개발자 어플리케이션 만들기

1. https://discord.com/developers/applications 에서 새 어플리케이션을 만든다.
2. 만든 앱에서 좌측메뉴 `OAuth2` 선택
    - `client_id`가 나와있고, `client secret`은 Reset Secret을 선택해서 만든다.
    - `redirect_url`은 callback router로서, google, kakao와 같은 양식으로 추가한다.
      ![img.png](../images/73.png)
3. .env -> config에 client id, secret을 설정한다.
    ```dotenv
    DISCORD_CLIENT_ID="xx"
    DISCORD_CLIENT_SECRET="xxx"
    ```
    ```python
    DISCORD_CLIENT_ID: str = environ.get("DISCORD_CLIENT_ID", None)
    DISCORD_CLIENT_SECRET: str = environ.get("DISCORD_CLIENT_SECRET", None)
    ```

4. OAuth2 > `Generate URL`을 선택하면, `scope를 선택`하고, 특정 callback redirect_url에 대한 url을 반환해준다.
    - **우리는 scope에 `identify, email` 외 `bot`까지 선택해준다.**
    -
    scope설명은 [이 문서](https://velog.io/@pung8146/%EB%94%94%EC%8A%A4%EC%BD%94%EB%93%9C-OAuth2-URL-%EA%B6%8C%ED%95%9CSCOPE-%EB%AA%A9%EB%A1%9D)
    를 참고한다.
    - 일단 로컬용 8001포트용 generate된 URL도 복사해놓자.
    - https://discord.com/api/oauth2/authorize?client_id=1156507222906503218&permissions=8&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fv1%2Fauth%2Fdiscord%2Fcookie%2Fcallback&response_type=code&scope=identify%20email%20bot
#### Sns_type Enum칼럼을 위해 discord 추가하기
```python
class SnsType(str, Enum):
    EMAIL: str = "email"
    FACEBOOK: str = "facebook"
    GOOGLE: str = "google"
    KAKAO: str = "kakao"
    DISCORD: str = "discord"
```
- **테이블 삭제후 테이블 칼럼 재생성해야함.**
#### clinet 만들기

1. oauth_clients.py에 `from httpx_oauth.clients.discord import DiscordOAuth2, BASE_SCOPES`를 import해서 client 생성
    - **BASE_SCOPE에, `bot`을 추가한다. 그러면 알아서 /authorize 및 /callback router가 완성될 것이다.**
    - **kakao, google과 다르게 `client에서 넣어준 scope로 /authorize가 반환해주는 url을 미리 완성시켜 보여주는 듯? 우리는 자동으로 생성될 듯 하다.**

    ```python
    # app/libs/auth/oauth_clients.py
    
    # - BASE_SCOPE ["identify", "email"]
    discord_oauth_client = DiscordOAuth2(
        client_id=DISCORD_CLIENT_ID,
        client_secret=DISCORD_CLIENT_SECRET,
        scopes=BASE_SCOPES + ['bot']
    )
    
    
    def get_oauth_clients():
        return [
            google_oauth_client, kakao_oauth_client, discord_oauth_client
        ]
    ```

#### backend 만들기
```python
class DiscordBackend(OAuthBackend):
    OAUTH_NAME = 'discord'

    async def get_profile_info(self, access_token):
        return dict()
    
    
discord_cookie_backend = DiscordBackend(
    name="cookie",
    transport=get_cookie_transport(),
    get_strategy=get_jwt_strategy,
    has_profile_callback=True,
)

discord_bearer_backend = DiscordBackend(
    name="bearer",
    transport=get_bearer_transport(),
    get_strategy=get_jwt_strategy,
    has_profile_callback=True,
)

def get_discord_backends():
    return [
        discord_cookie_backend, discord_bearer_backend
    ]
```

#### get_oauth_routers() 에서 client type확인해서, 해당 backend들 입력해서 만들기
```python
# app/api/dependencies/auth.py

def get_oauth_routers():
    routers = []

    for oauth_client in get_oauth_clients():

        elif isinstance(oauth_client, DiscordOAuth2):
            for backend in get_discord_backends():
                routers.append({
                    "name": f'{oauth_client.name}/' + backend.name,
                    "router": fastapi_users.get_oauth_router(
                        oauth_client=oauth_client,
                        backend=backend,
                        state_secret=JWT_SECRET,
                        associate_by_email=True,
                    )
                })

    return routers
```
![img.png](../images/75.png)

#### docs /authorize 에서 제공해주는 url과  디스코드앱 GenerateURL과 비교하기
```json
{
  "data": {
    "authorization_url": "https://discord.com/api/oauth2/authorize?response_type=code&client_id=xxx&redirect_uri=http%3A%2F%2Flocalhost%3A8001%2Fapi%2Fv1%2Fauth%2Fdiscord%2Fbearer%2Fcallback&state=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJmYXN0YXBpLXVzZXJzOm9hdXRoLXN0YXRlIiwiZXhwIjoxNjk1ODA5MjM3fQ.OafusCu1yRYtpyTvHsVQ-UGF94zR1Vancs099I6bTko&scope=identify+email+bot"
  },
  "version": "1.0.0"
}
```

- 얼추 비슷한 것 같다. 직접 복사해서 작동하는지 본다.
- **fastapi-users가 제공해주는 authorization_url 주소로도 제대로 작동을 한다.**
    - **fastapi-users에서 제공해주는 것에는 redirect_uri랑 비교를 해보면**
    - fastapi-users: `redirect_uri=http%3A%2F%2Flocalhost%3A8001%2Fapi%2Fv1%2Fauth%2Fdiscord%2Fbearer%2Fcallback`
    - 디스코드 앱:  `redirect_uri=http%3A%2F%2Flocalhost%3A8001%2Fapi%2Fv1%2Fauth%2Fdiscord%2Fcookie%2Fcallback`
    ```
    # https://discord.com/api/oauth2/authorize?response_type=code&client_id=xxx&redirect_uri=http%3A%2F%2Flocalhost%3A8001%2Fapi%2Fv1%2Fauth%2Fdiscord%2Fbearer%2Fcallback&state=xxx&scope=identify+email+bot"
    # https://discord.com/api/oauth2/authorize?client_id=xxx&permissions=8&redirect_uri=http%3A%2F%2Flocalhost%3A8001%2Fapi%2Fv1%2Fauth%2Fdiscord%2Fcookie%2Fcallback&response_type=code&scope=identify%20email%20bot
    ```
  - **순서를 제외하곤 state=가 들어있는 것이 차이점이다.**
  - state는 입력받은 state_data + state_secret(JWT_SECERT)으로 jwt토큰을 만들어서 나온 것이며, 이것만 추가된다.    


#### client의 .get_id_email을 참고하여, backend.login 속 추가정보 입력을 위한 get_profile_info() 구현하기
1. **client객체 속 get_id_email 코드를 복사해온 뒤, `params={}`로 discord문서를 참고하여 PROFILE_ENDPOINT에서 `추가정보를 포함하여 요청`한다.**
    - **google, kakao와 달리, 추가정보를 얻기 위한, params를 요청하지 않고, `identify, email`에서 다 뽑아낸다.**
    ```python
    response = await client.get(
                # PROFILE_ENDPOINT,
                google.PROFILE_ENDPOINT,
        params={"personFields": "photos,birthdays,genders,phoneNumbers"},
                headers={**self.request_headers, "Authorization": f"Bearer {access_token}"},
            )
            PROFILE_ADDITIONAL_PROPERTIES = [
                "kakao_account.profile",
                "kakao_account.age_range",
                "kakao_account.birthday",
                "kakao_account.gender"
            ]
    
    response = await client.post(
        kakao.PROFILE_ENDPOINT,
        params={"property_keys": json.dumps(PROFILE_ADDITIONAL_PROPERTIES)},
        headers={**self.request_headers, "Authorization": f"Bearer {access_token}"},
    )
    ```

2. 이제 필요한 정보를 추출해서 profile_info = dict()에 집어넣는다.
    - `https://cdn.discordapp.com/avatars/{user.id}/{user.avatar}.png` 양식으로 `profile_img` 를 채울 수 있다.
    - **이 때, 아바타 안바꾸면 None이 들어가 있으니 확인한다.**
    - `username`이 사용자명 / `global_name`이 별명이다.
    ```python
    class DiscordBackend(OAuthBackend):
        OAUTH_NAME = 'discord'
        async def get_profile_info(self, access_token):
            async with self.get_httpx_client() as client:
                response = await client.get(
                    discord.PROFILE_ENDPOINT,
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

### google, kakao도 프로필 정보에서 ~~name,~~, nickname을 찾아 넣어준다.
1. google의 people api에서 요청 params=인 personFields에서 파라미터들을 확인한다.
    - `names,nicknames`를 추가해서 요청하여 정보를 받아먹는다.
    ```python
    class GoogleBackend(OAuthBackend):
    
        async def get_profile_info(self, access_token):
    
            async with self.get_httpx_client() as client:
    
                response = await client.get(
                    google.PROFILE_ENDPOINT,
                    params={"personFields": "photos,birthdays,genders,phoneNumbers,names,nicknames"},
                    headers={**self.request_headers, "Authorization": f"Bearer {access_token}"},
                )
                # ...
                # for field in "photos,birthdays,genders,phoneNumbers,names,nicknames".split(","):
                for field in "photos,birthdays,genders,phoneNumbers,names,nicknames".split(","):
                    #...
                    if field == 'names' and (name := primary_data.get('displayName')):
                        # "displayName":"조재성",
                        profile_info['nickname'] = name
    
                    # if field == 'nicknames' and (nickname:=primary_data['value']):
                    #     # "value":"부부한의사",
                    #     profile_info['nickname'] = nickname

   
                return profile_info
    ```
    ```json
    "names":[
            {
                "metadata":{
                    "primary":true,
                    "source":{
                        "type":"PROFILE",
                        "id":"xxx"
                    },
                    "sourcePrimary":true
                },
                "displayName":"조재성",
                "familyName":"조",
                "givenName":"재성",
                "displayNameLastFirst":"조재성",
                "unstructuredName":"조재성"
            }
        ],
    "nicknames":[
        {
            "metadata":{
                "primary":true,
                "source":{
                    "type":"PROFILE",
                    "id":"xxx"
                }
            },
            "value":"부부한의사",
            "type":"ALTERNATE_NAME"
        }
    ],
    ```
   

2. kakao
    ```python
    class KakaoBackend(OAuthBackend):
    
        async def get_profile_info(self, access_token):
    
                if profile := kakao_account.get('profile'):
                    profile_info['profile_img'] = profile.get('thumbnail_image_url', None)
                    if nickname := profile.get('nickname', None):
                        profile_info['nickname'] = nickname
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