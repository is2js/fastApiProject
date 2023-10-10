### guilds.html 꾸미기

#### row + col로 card형태의 길드 만들기
1. 내 서버 목록임을 알려주고 {{ | count }} 로 순회하는 guilds의 갯수를 찍어준다.
    ```html
    <h6 class="h6 text-white text-center">내 서버 목록 ({{ user_guilds | count }})</h6>
    ```
2. `.row`안에 `px-x`로 전체 x여백만 준 뒤, **col로 이미 정해진 간격을 주기 때문에, row gap만 `row-gap-x`로 주고, 만 준다.**
    - **col간격을 주고 싶다면, col-x 내부에서 px로 줘야한다.**
    ```html
    <div class="row px-3 row-gap-3">
        {% for guild in user_guilds %}
            <div class="col-sm-12 col-md-6 col-lg-4">
                <div class="px-2 ...
    ```

3. 각 guild들은 flex & 가운데정렬 & 수직가운데 정렬 + `rounded-3`정도로 카드를 만들고
    - **카드의 부모로서 `자식의75%로 height/font-size`를 가져갈 수 있게 `.guild-item`에 height 85px, fs-1.3rem, 배경색을 css로 정의해놓는다.**
    ```css
    .guild-item {
        background-color: #3a4242;
        height: 85px;
        font-size: 1.5rem;
        overflow: hidden;
    }
    ```
    ```html
    <div class="col-sm-12 col-md-6 col-lg-4">
        <div class="guild-item px-2 d-flex justify-content-center align-items-center rounded-3">
    
        </div>
    </div>
    ```
4. **카드:hover로서, 1.05배 크기를 키워주고, 쉐도우를 넣어준다.**
    ```css
    .guild-item:hover {
        transform: scale(1.05);
        box-shadow: 0 .2rem .5rem rgba(0,0,0,0.3), 0 1rem .5rem rgba(0,0,0,0.22)
    }
    ```
   
5. flex-item으로서 `img`와 `p태그`로 이미지와 길드이름을 적는데, **`h-75`로 가져간다.**
    - img는 `h-75`에 +  rounded + 이름에 대한 `me-3`우측여백을 준다.
    - p태그도 `h-75`에 + p태그기본마진 삭제`m-0`에, 글자 수직정렬을 위해 `d-flex align-items-center`로 만들어놓고 내부 b태그에 길드이름을 적는다.
    - p태그의 `글자크기를 75%`로 해야하는데, 줄 수 없으니 `css`로 줘야한다.
    ```html
    <div class="col-sm-12 col-md-6 col-lg-4">
        <div class="guild-item px-2 d-flex justify-content-center align-items-center rounded-3">
            <img class="me-3 h-75 rounded" src="https://cdn.discordapp.com/embed/avatars/0.png">
            <p class="m-0 h-75 d-flex align-items-center">
                <b>{{ guild.name }}</b>
            </p>
        </div>
    </div>
    ```
    ```css
    .guild-item > p {
        font-size: 75%;
    }
    ```
6. 최종 html
    ```html
    {% block content %}
        <h6 class="h6 text-white text-center">내 서버 목록 ({{ user_guilds | count }})</h6>
        <div class="row px-3 row-gap-3">
            {% for guild in user_guilds %}
                <div class="col-sm-12 col-md-6 col-lg-4">
                    <div class="guild-item px-2 d-flex justify-content-center align-items-center rounded-3">
                        <img class="me-3 h-75 rounded" src="https://cdn.discordapp.com/embed/avatars/0.png">
                        <p class="m-0 h-75 d-flex align-items-center">
                            <b>{{ guild.name }}</b>
                        </p>
                    </div>
                </div>
            {% endfor %}
        </div>
    {% endblock content %}
    ```
   
### 그동안 libs > discord에서 정의한 discord_client의 사용처를 get_oauth_client(SnsType.DISCORD)로 모두 변환.
#### /guilds의 .get_guilds()만 자체구현 discord_client라, libs > auth > httx의 DiscordOAuth2를 재정의
```python
GUILD_ENDPOINT = PROFILE_ENDPOINT + '/guilds'


class DiscordClient(DiscordOAuth2):

    async def get_guilds(self, token: str):
        async with self.get_httpx_client() as client:
            response = await client.get(
                GUILD_ENDPOINT,
                headers={**self.request_headers, 'Authorization': f"Bearer {token}"},
            )

            data = cast(Dict[str, Any], response.json())

            return data


def get_discord_client():
    # return DiscordOAuth2(
    return DiscordClient(
        client_id=DISCORD_CLIENT_ID,
        client_secret=DISCORD_CLIENT_SECRET,
        scopes=discord.BASE_SCOPES + ['bot'],  # BASE_SCOPE ["identify", "email"]
    )

```
- @oauth_login_required()도 변경
    ```python
    def oauth_login_required(sns_type: SnsType):
        def decorator(func):
            @wraps(func)
            async def wrapper(request: Request, *args, **kwargs):
    
                state_data = dict(next=str(request.url))
                state = generate_state_token(state_data, JWT_SECRET) if state_data else None
    
                oauth_client = get_oauth_client(sns_type)
    
                # redirect_uri에 적을 callback route 만 달라진다.
                if not request.state.user:
                    if sns_type == SnsType.DISCORD:
    
                        authorization_url: str = await oauth_client.get_authorization_url(
                            redirect_uri=str(request.url_for('discord_callback')),
                            state=state
                        )
    
                        response = RedirectResponse(authorization_url)
                        return response
    
                    else:
                        raise NoSupportException()
                else:
                    return await func(request, *args, **kwargs)
    
            return wrapper
    
        return decorator
    ```

- **template용 discord > pages > oauth_client.py 삭제**
    - **state_data를 받아주는 커스텀 oauth_callback.py만 필요한 듯?**
    ```python
    @router.get("/guilds")
    
    @oauth_login_required(SnsType.DISCORD)
    async def guilds(request: Request):
        access_token = request.state.user.get_oauth_access_token('discord')
    
        oauth_client = get_oauth_client(SnsType.DISCORD)
        
        user_guilds = await oauth_client.get_guilds(access_token)
    
        context = {
            'user_guilds': user_guilds,
        }
    
        return render(
            request,
            "bot_dashboard/guilds.html",
            context=context
        )
    
    ```
#### fastapi-users backend객체에만 정의해놨던 get_profile_info를 자체콜백을 위해 client에도 옮겨준다.

- **각 백엔드 객체 속 get_profile_info 메서드를 -> 각 oauth client객체에도 다 옮겨준다.**
    - discord 뿐만 아니라.. 모두 httx의 XXXXOAuth2 (client 클래스)를 재정의해서 옮겨준다.
```python
class DiscordClient(DiscordOAuth2):

    async def get_guilds(self, token: str):
        async with self.get_httpx_client() as client:
            response = await client.get(
                GUILD_ENDPOINT,
                headers={**self.request_headers, 'Authorization': f"Bearer {token}"},
            )

            data = cast(Dict[str, Any], response.json())

            return data

    async def get_profile_info(self, access_token):
        async with self.get_httpx_client() as client:
            response = await client.get(
                discord.PROFILE_ENDPOINT,
                # params={},
                headers={**self.request_headers, "Authorization": f"Bearer {access_token}"},
            )
            if response.status_code >= 400:
                raise GetOAuthProfileError()

            profile_dict = dict()

            data = cast(Dict[str, Any], response.json())
            if avatar_hash := data.get('avatar'):
                # profile_dict['profile_img'] = f"https://cdn.discordapp.com/avatars/{data['id']}/{avatar_hash}.png"
                profile_dict['profile_img'] = f"https://cdn.discordapp.com/avatars/{data['id']}/{avatar_hash}"
            if nickname := data.get('global_name'):
                profile_dict['nickname'] = nickname

        return profile_dict

```
```python
class GoogleClient(GoogleOAuth2):
    
    # 자체 콜백을 위해, backend에만 정의해놨던 것을, client에도
    async def get_profile_info(self, access_token):
        async with self.get_httpx_client() as client:
            response = await client.get(
                # PROFILE_ENDPOINT,
                google.PROFILE_ENDPOINT,
                # params={"personFields": "emailAddresses"},
                # params={"personFields": "photos,birthdays,genders,phoneNumbers"},
                params={"personFields": "photos,birthdays,genders,phoneNumbers,names,nicknames"},
                headers={**self.request_headers, "Authorization": f"Bearer {access_token}"},
            )
    
            if response.status_code >= 400:
                raise GetOAuthProfileError()
    
            data = cast(Dict[str, Any], response.json())
    
            profile_info = dict()
            # for field in "photos,birthdays,genders,phoneNumbers,names,nicknames".split(","):
            for field in "photos,birthdays,genders,phoneNumbers,names,nicknames".split(","):
                field_data_list = data.get(field)
                primary_data = next(
                    (field_data for field_data in field_data_list if field_data["metadata"]["primary"])
                    , None
                )
                if not primary_data:
                    continue
                # 'photos' primary_data >> {'metadata': {'primary': True, 'source': {'type': '', 'id': ''}}, 'url': 'https://lh3.googleusercontent.com/a/ACg8ocKn-HgWhuT191z-Xp6lq0Lud_nxcjMRLR1eJ0nMhMS1=s100', 'default': True}
                if field == 'photos' and (profile_img := primary_data.get('url')):
                    # "url": "https://lh3.googleusercontent.com/a/ACg8ocKn-HgWhuT191z-Xp6lq0Lud_nxcjMRLR1eJ0nMhMS1=s100",
                    profile_info['profile_img'] = profile_img
    
                if field == 'birthdays' and (date := primary_data.get('date')):
                    birthday_info = date
                    # "date": {
                    #              "year": 1900,
                    #              "month": 00,
                    #              "day": 00
                    #          }
                    # profile_info['birthday'] = str(birthday_info['year']) + str(birthday_info['month']) + str(
                    #     str(birthday_info['day']))
                    profile_info['birthyear'] = str(birthday_info['year'])
                    profile_info['birthday'] = str(birthday_info['month']) + str(birthday_info['day'])
                    profile_info['age_range'] = self.calculate_age_range(birthday_info['year'], birthday_info['month'],
                                                                         birthday_info['day'])
    
                if field == 'genders' and (gender := primary_data.get('value')):
                    # "value": "male",
                    profile_info['gender'] = gender
    
                if field == 'phoneNumbers' and (phone_number := primary_data.get('value')):
                    # "value": "010-yyyy-xxxx",
                    profile_info['phone_number'] = phone_number
    
                if field == 'names' and (name := primary_data.get('displayName')):
                    # "displayName":"조재성",
                    profile_info['nickname'] = name
    
                # if field == 'nicknames' and (nickname:=primary_data['value']):
                #     # "value":"부부한의사",
                #     profile_info['nickname'] = nickname
    
            return profile_info


# scope 선택 (backend.login()에서 재요청할 것이므로 굳이 여기서 안해도 될듯 하긴 함.)
def get_google_client():
    # return GoogleOAuth2(
    return GoogleClient(
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
class KakaoClient(KakaoOAuth2):
    # # 자체 콜백을 위해, backend에만 정의해놨던 것을, client에도
    async def get_profile_info(self, access_token):
        async with self.get_httpx_client() as client:
            # https://developers.kakao.com/docs/latest/ko/kakaologin/rest-api#propertykeys
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

            if response.status_code >= 400:
                raise GetOAuthProfileError()

            data = cast(Dict[str, Any], response.json())
            # 동의 안했을 수도 있으니, 키값을 확인해서 꺼내서 db에 맞게 넣는다.
            profile_info = dict()

            kakao_account = data['kakao_account']

            if profile := kakao_account.get('profile'):
                profile_info['profile_img'] = profile.get('thumbnail_image_url', None)
                if nickname := profile.get('nickname', None):
                    profile_info['nickname'] = nickname

            if kakao_account.get('birthday'):
                profile_info['birthday'] = kakao_account['birthday']

            if kakao_account.get('has_age_range'):
                # profile_info['birthday'] = kakao_account['age_range'] + profile_info['birthday']
                profile_info['age_range'] = kakao_account['age_range']

            if kakao_account.get('gender'):
                profile_info['gender'] = kakao_account['gender']
        return profile_info


def get_kakao_client():
    # return KakaoOAuth2(
    return KakaoClient(
```

#### 이제 libs > discord > pages > oauth_callback.py를  pages패키지로 옮겨준다.

#### discord client 생성시 scope에 ['bot']을 제거해서, 내 서버중 어느서버에서 추가할 것인지 선택을 제거
- **그동안 'bot'을 scope에 추가했더니, `해당 application의 bot을 내 서버중 어느서버에 추가할 것인지`가 계속 같이 떴었다.**
    - 이것은 나중에 처리한다.
```python
def get_discord_client():
    return DiscordClient(
        client_id=DISCORD_CLIENT_ID,
        client_secret=DISCORD_CLIENT_SECRET,
        scopes=discord.BASE_SCOPES # + ['bot'],  # BASE_SCOPE ["identify", "email"]
    )
```

### 개발자 문서 길드페이지 보면서, guilds에서 정보 뽑기
- 개발자 페이지(앱): https://discord.com/developers/applications
- 문서: https://discord.com/developers/docs

1. 문서 > User > Get Current User Guilds
 - oauth client 재정의하면서, GUILD_ENDPOINT로 정해놓은 /users/@me/guilds
    ```json
    {
      "id": "80351110224678912",
      "name": "1337 Krew",
      "icon": "8342729096ea3675442027381ff50dfe",
      "owner": true,
      "permissions": "36953089",
      "features": ["COMMUNITY", "NEWS"],
      "approximate_member_count": 3268,
      "approximate_presence_count": 784
    }
    ```
   

2. guild 정보에서 icon -> img로 추출할라면 url 양식안에 추가해야한다.
    - guilds정보를 순회하면서, "icon"을 덮어쓴다.
    ```python
    user_guilds = await oauth_client.get_guilds(access_token)
    
    for guild in user_guilds:
        if guild.get('icon', None):
            guild['icon'] = 'https://cdn.discordapp.com/icons/' + guild['id'] + '/' + guild['icon']
        else:
            guild['icon'] = 'https://cdn.discordapp.com/embed/avatars/0.png'
    
    ```

### pages패키지 정리 -> index.py, discord.py를 pages > routers로 옮겨준다.
```python
from .routers import router
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