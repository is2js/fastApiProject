- 참고 유튜브: https://www.youtube.com/watch?v=I1pQQIPoU7s

### dashboard

#### ipc

- ipc: 프로세스 간 통신 (inter process communication : IPC)
    1. PIPE(파이프)
        - File 이용
        - 익명의 PIPE를 통해서 동일한 PPID를 가진 프로세스들 간에 단방향 통신을 지원
        - 생성된 PIPE에 대하여 Write 또는 Read만 가능하다.

    2. Message Queue(메시지 큐)
        - 메모리를 사용한 PIPE이다.
        - 구조체 기반(큐: FIFO 구조)으로 통신을 한다.

    3. Shared Memory(공유메모리, 전연변수)
        - 시스템 상의 공유 메모리를 통해 통신한다.
        - 메모리 길이 고정

    4. Memory Map
        - 파일을 프로세스의 메모리에 일정 부분 맵핑 키셔 사용한다.
        - 파일로 대용량 데이터를 공유 할 때 사용한다.

    5. Socket
        - 네트워크 소켓통신을 시용한 데이터 공유
        - 네트워크 소켓을 이용하여 Client - Server 구조로 데이터 통신
        - 운영체제 내에서 <sys/socket.h>라는 헤더를 이용하여 사용할 수 있으며, 같은 도메인에서의 경우에서 연결 될 수 있다.
        - 소켓을 사용하기 위해서는 생성해주고, 이름을 지정해주어야 합니다. 또한 domain과 type, Protocol을 지정해 주어야 한다.
        - 서버 단에서는 bind, listen, accept를 해주어 소켓 연결을 위한 준비를 해주어야 하고 , 클라이언트 단에서는 connect를 통해 서버에 요청하며, 연결이 수립 된 이후에는
          Socket을 send함으로써 데이터를 주고 받게 된다. 연결이 끝난 후에는 반드시 Socket 을 close()해주어야 한다.

    6. [RPC](https://cagea1.tistory.com/4)(Remote process call)
        - RPC는 쉽게 말해 한 프로세스가 다른 프로세스의 동작을 일으킬 수 있는 프로세스 간 통신, 즉 IPC의 일종이다.
        - **디스코드는 RPC 인터페이스로 로컬에서 동작하는 서비스**를 제공하고 있다. 이에 대한 내용은 여기에서 공식문서를 확인할 수 있다

#### 패키지 설치

1. `py-cord`, `better-ipc`, `jinja2`를 추가해준다.
    - better-ipc는 dicord.py의 ipc통신 포퍼먼스를 올려주는 library라고 한다.
    ```shell
    pip install py-crod, better-ipc, jinja2
    
    pip freeze > .\requirements.txt
    
    docker-compose build --no-cache api; docker-compose up -d api;
    ```

#### app > templates + static 폴더 생성

1. templates, static 폴더 및 templates / index.html 생성
    ```html
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width, user-scalable=no, initial-scale=1.0, maximum-scale=1.0, minimum-scale=1.0">
        <meta http-equiv="X-UA-Compatible" content="ie=edge">
        <title>BOT DASHBOARD</title>
    </head>
    <body>
    
    </body>
    </html>
    ``` 
2. 진자문법으로 bot이 속한 server갯수를 미리 작성해두자.
    ```html
    <body>
        <h1> Discord bot Dashboard</h1>
        <h3>bot은 {{count}} server에서 활동하고 있습니다.</h3>
    </body>
    ```

#### templates객체 만들기

1. app > router 패키지 ->  app > `pages` 패키지로 변환
    - [구조 참고](https://github.dev/artemonsh/fastapi_course)

2. 어차피 pages패키지 내의 router들만 쓸 templates객체이므로 `__iniy__.py`에 객체를 선언해준다.
    - **이 때, 하위 router(index.py)들보다 먼저 생성해놔야, import되는 하위 py들이 가져다 쓸 수 있다.**
    - **pathlib의 Path를 이용할 땐, `현재파일(Path(__file__)`의 `절대주소(.resolve()))`의 `부모.parent`로 `현재폴더`를 경로를 만들어내고**
    - **하위폴더를 추가할 땐 `/` 연산자로 폴더명을 덧붙혀서 경로를 만들 수 있다.**
    ```python
    from pathlib import Path
    
    from fastapi import APIRouter
    from starlette.templating import Jinja2Templates
    
    # jinja template 객체 생성
    # resolve() 함수는 파일의 Path객체 실제 경로(절대경로) -> 부모 : 현재 폴더
    current_directory = Path(__file__).resolve().parent
    # Path 객체에서 "/" 연산자를 사용하면 경로를 결합
    templates_directory = current_directory.parent / "templates"
    templates = Jinja2Templates(directory=str(templates_directory))
    
    from . import index
    
    router = APIRouter()
    router.include_router(
        index.router,
        tags=['Pages']
        )
    
    ```

3. create_app()내부에서도 index.router객체가 아닌, pages패키지의 init에서 통합된 router를 가져오도록 변경한다.
    ```python
    from app import api, pages
    
    def create_app(config: Config):
    
        # route 등록
        # app.include_router(index.router)  # template or test
        app.include_router(pages.router)  # template or test
    ```


4. **pages router에서는 `templates.TemplateResonse()`에 templates폴더의 `html 지정` 및 `필수contenxt dict`로서 내부에 `request`를 필수로
   보내줘야한다.**
    ```python
    from starlette.requests import Request
    
    from app.pages import templates
    
   # @router.get("/", response_model=UserMe)
    @router.get("/")
    async def index(request: Request, session: AsyncSession = Depends(db.session)):
        context = {
            'request': request,  # 필수
            'count': 3,  # 커스텀 데이터
        }
        return templates.TemplateResponse(
            "index.html",
            context
        )
    
    ```

#### static 폴더를 mount해주기

1. templates와 달리 전역에서 쓸 것이기 때문에 create_app에서 app.mount해줘야한다.
    - **역시 현재파일을 기준으로 Path객체를 사용해서 만들어 연결해준다. 이 때, mount()시 `route path`를 정해줘야하는데 prefix처럼 `/`로 시작해야한다.**
    - `route name`도 static으로 정의해준다. -> 진자 url_for에 사용됨.
    ```python
    # app/__init__.py
   
    from starlette.staticfiles import StaticFiles
    
    def create_app(config: Config):
    
        # static
        static_directory = Path(__file__).resolve().parent / 'static'
        # static_directory >> C:\Users\cho_desktop\PycharmProjects\fastApiProject\app\static
        app.mount('/static', StaticFiles(directory=static_directory), name='static')
    ```

#### static > css폴더 만들어서 style.css 추가 및 template내부에서 url_for로 사용하기

1. static 폴더아래 `css폴더 > style.css`를 만들고
2. html에 link태그 + `{{ url_for('static', path= ) }}`의 진자문법으로 router name을 이용한다.
    ```html
    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width, user-scalable=no, initial-scale=1.0, maximum-scale=1.0, minimum-scale=1.0">
        <meta http-equiv="X-UA-Compatible" content="ie=edge">
        <title>BOT DASHBOARD</title>
        <link rel="stylesheet" type="text/css" href="{{url_for('static', path='css/style.css')}}">
    </head>
    ```

3. **이제 `/static` router path를 미들웨어 `EXCEPT_PATH`에 추가해줘야한다.**
    - 안해주면, static폴더를 가져오는 과정에서 미들웨어에서 NotAuthorized가 뜬다.
    ```python
    # app/common/consts.py
    # EXCEPT_PATH_REGEX = "^(/docs|/redoc|/api/v[0-9]+/auth)"
    EXCEPT_PATH_REGEX = "^(/docs|/redoc|/api/v[0-9]+/auth|/static)"
    ```

4. index로 접속하면 static도 불러오는 것을 확인할 수 있다.
    ```shell
    INFO:     127.0.0.1:62017 - "GET / HTTP/1.1" 200 OK
    INFO:     127.0.0.1:62017 - "GET /css/style.css HTTP/1.1" 200 OK
    ```
   ![img.png](../images/77.png)

5. style.css에서, body는 검은색으로, strong태그에 한해서만 글자색을 넣어준다.
    ```css
    body {
        background: #222727;
        color: #d8d8d8;
        text-align: center;
        font-family: Verdana, sans-serif;
    }
    
    strong {
        color: #ea461e;
    }
    ```

6. 강조하고 싶은 글자에 strong 태그를 달아주자.
    ```html
    <h3>bot은 <strong>{{count}}</strong>개의 server에서 활동하고 있습니다.</h3>
    ```
   ![img.png](../images/78.png)

### bot 만들기

1. discord 개발자페이지 > `bot`에 들어가서, 기존에 만든 어플리케이션을 선택하고, `reset token`으로 `BOT_TOKEN`을 생성한다.
2. .env 및 config에 설정한다.
    ```dotenv
    DISCORD_BOT_TOKEN="xxx"
    ```
    ```python
    DISCORD_BOT_TOKEN: str = environ.get("DISCORD_BOT_TOKEN", None)
    ```

3. 여기를 참고해서, app > libs > `bot` 폴더 > `discord_bot.py`를 생성하여 DiscordBot객체를 위한 class를 정의할 준비를 한다.
    - **이 때, 아래의 `ezcord`패키지가 `discord 패키지를 내부import`하는데, 파일명이 discord.py면, 오류나서 조심.**
    ```python
    # app/libs/bot/discord_bot.py
    ```

##### ezcord

4. 좀 더 쉬운개발을 위해 `ezcord`패키지를 설치한다.
    ```shell
    pip install ezcord
    
    pip freeze > .\requirements.txt
    
    docker-compose build --no-cache api; docker-compose up -d api;
    ```
5. ezcord는 Discord용 Bot을 정의하는 클래스를
    - pycord가 있으면 discord.bot을 / 없으면 commands.Bot의 일반 명령어 bot을 기본 class로 설정한다.
   ```python
    try:
        _main_bot = discord.Bot  # Pycord
    except AttributeError:
        _main_bot = commands.Bot
    ```

6. discord_bot.py에서 ezcord.Bot을 상속한 DiscordBot class를 만들고, `생성자 재정의`에서 intents만 discord패키지에서 새로 넣어준다.
    - **이 때, `on_ready`메서드를 부모class에선 정의하지 않았찌만, string으로 파싱해서 cog_group 및 db_setup시 사용하므로 직접 정의해주면 된다.**
    ```python
    class Bot(_main_bot):  # type: ignore
        # ...
        self.ready_event = ready_event
        if ready_event:
            self.add_listener(self._ready_event, "on_ready")
        self.add_listener(self._check_cog_groups, "on_ready")
        self.add_listener(self._db_setup, "on_ready")
    ```
    ```python
    class DiscordBot(ezcord.Bot):
        def __init__(self):
            super().__init__(intents=discord.Intents.default())
    
        async def on_ready(self):
            print(f"{self.user} Application is online")
    ```

7. **bot token으로 객체생성 테스트를 돌려보기 위해서, config의 상수를 가져와야하는데, `main.py`처럼 실행전 db설정 로컬설정이 들어있는 `config객체 생성`이 안되어있어서 db연결
   에러난다.**
    - **그러므로 직접 load_dotenv() -> 환경변수에서 가져와서 사용하자.**
    - py-cord의 Bot으로서, 이쁘게 프린팅 된다.
    ```python
    if __name__ == '__main__':
        bot = DiscordBot()
        
        # from app.common.config import DISCORD_BOT_TOKEN
        # token = environ.get(DISCORD_BOT_TOKEN, None)
        # => app이 로드되는 순간, config 생성없이 init.py도 불러와져서 에러남.
        
        from dotenv import load_dotenv
        load_dotenv()
        token = environ.get("DISCORD_BOT_TOKEN", None)
        
        bot.run()
    
    # 한의원#xxx Application is online
    # [INFO] Bot is online with EzCord 0.3.7
    # ╭─────────────┬─────────────────────┬────────┬──────────┬────────┬─────────╮
    # │ Bot         │ ID                  │ Pycord │ Commands │ Guilds │ Latency │
    # │─────────────┼─────────────────────┼────────┼──────────┼────────┼─────────│
    # │ 한의원#xxx   │ xxxxx               │ 2.4.1  │ 0        │ 1      │ 225ms   │
    # ╰─────────────┴─────────────────────┴────────┴──────────┴────────┴─────────╯
    ```

### Bot으로 discord 통신을 하기 위한 ipc Server 만들기

1. from discord.ext.ipc import Server를 이용하여 bot을 이용한 ipc Server를 bot class의 `self.ipc`에 만들어놓는다.
    - 이 때, Server객체를 만들기 위한 secret_key는 server<->client사이의 임의의 키임.(application 키 아님)
    - **on_ready에서 `await self.ipc.start()`를 통해, bot생성과 동시에 server객체 생성 -> 서버 가동까지 한다.**
    ```python
    from discord.ext.ipc import Server
    
    
    class DiscordBot(ezcord.Bot):
        def __init__(self):
            super().__init__(intents=discord.Intents.default())
            self.ipc = Server(self, secret_key="hani") # test 이후 config로 변경
    
        async def on_ready(self):
            await self.ipc.start()
            print(f"{self.user} Application is online")
    ```

2. ipc에서 에러가 났을때의 listener도 정의해준다.
    - **custom exception을 `app.erros`에 정의하여 import하는 순간, db컨넥션에러가 뜰것이다.**
    - **ipc를 사용하는 순간부터 우리의 endpoint에서도 사용해야하므로 `app 단위에서 시작`하도록 변경해야한다.**
    ```python
    # 500 - discord 에러
    class DiscordError(APIException):
        def __init__(
                self, *,
                code_number: [str, int] = "0",
                detail: str = None,
                exception: Exception = None
        ):
            if not isinstance(code_number, str):
                code_number = str(code_number)
    
            super().__init__(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code=f"{status.HTTP_500_INTERNAL_SERVER_ERROR}{code_number.zfill(4)}",
                message="Discord 에러입니다.",
                detail=detail,
                exception=exception
            )
    
    
    class DiscordIpcError(DiscordError):
    
        def __init__(self, *, endpoint: str = "", exception: Exception = None):
            super().__init__(
                code_number=1,
                detail=f"{endpoint}에서 Ipc 통신 에러가 발생했습니다.",
                exception=exception
            )
    ```
    ```python
    from app.errors.exceptions import DiscordIpcError
    #...
    class DiscordBot(ezcord.Bot):
        def __init__(self):
            super().__init__(intents=discord.Intents.default())
            self.ipc = Server(self, secret_key="hani") # test 이후 config로 변경
    
        async def on_ready(self):
            await self.ipc.start()
            print(f"{self.user} Application is online")
    
        async def on_ipc_error(self, endpoint:str, exc: Exception) -> None:
            raise DiscordIpcError(exception=exc)
    ```


3. app과 같이 bot이 실행되도록 객체 생성은 해당 장소에서, start는 앱시작시로 변경한다
   - **discord_bot.py에서 `discord_bot`객체를 생성해놓고, create_app에서 app객체를 받을 수 있기 `init_app`을 구현하여, 내부에서 startup event를 단다.**
    ```python
    class DiscordBot(ezcord.Bot):
        #...
        def init_app(self, app: FastAPI):
            @app.on_event("startup")
            async def start_up_discord():
                ...
    
            @app.on_event("shutdown")
            async def shut_down_discord():
                ...
    
    discord_bot = DiscordBot()
    ```
    ```python
    from app.libs.bot.discord_bot import discord_bot
    #...
    def create_app(config: Config):
        #...
        # database
        db.init_app(app)
    
        # discord
        discord_bot.init_app(app)
    
    ```
   

4. **이 때, 더이상 동기용 run메서드는 못쓴다(쓰면 fastapi의 event loop가 진행중)이라고 뜸.**
    - py-cord [공식문서](https://docs.pycord.dev/en/stable/api/clients.html#discord.Bot.run)에 보면, 이벤트 루프 초기화코드가 내부에 있다고 함.
    - 그래서 run() 대신 `await start()와 await close()`를 사용하라고 한다.
    - [gist](https://gist.github.com/haykkh/49ed16a9c3bbe23491139ee6225d6d09)를 참고해서, `asyncio.create_ask())`안에서 start를 호출하고
    - shut_down시 close를 호출하도록 한다.
    - 3.8버전 이후에는 `asyncio.create_task()`안에 비동기 메서드를 호출한다.
    ```python
    def init_app(self, app: FastAPI):
        @app.on_event("startup")
        async def start_up_discord():
            asyncio.create_task(self.start(DISCORD_BOT_TOKEN))
    
        @app.on_event("shutdown")
        async def shut_down_discord():
            await self.close()
    ```
   
5. 예외처리를 해서, discord bot이 run(start)안되어도 진행되도록 / 종료안됬을 때만 종료되도록 수정한다.
    ```python
    def init_app(self, app: FastAPI):
        @app.on_event("startup")
        async def start_up_discord():
            # 연결에 실패하더라도, app은 돌아가도록
            try:
                asyncio.create_task(self.start(DISCORD_BOT_TOKEN))
            except discord.LoginFailure:
                app_logger.get_logger.log('Discord bot 연결에 실패하였습니다.')
    
        @app.on_event("shutdown")
        async def shut_down_discord():
            # websocket 연결이 끊겼으면, close시키기
            if not self.is_closed():
                await self.close()
    ```
   
#### ipc Server를 이용한 router를 bot class에 view func로 정의 -> router에서 ipc Clinter객체를 생성하여 -> bot에 정의된 router를 clinet.request("ipc view func명")으로 호출

1. bot class에 `@Server.route()`의 데코레이터를 이용하여 view function을 정의한다.
    - `bot이 속한 server == guild`의 갯수를 반환하도록 짠다.
    - **이 때, 2번째 인자는 router_name인데, `_`로 정의하여, 사용안하도록 죽여놓고 -> 내부에선 router_name 대신 func.__name__으로 데코레이터가 라우터의 endpoint를
      설정하게 한다.**
    - return에 `self.guilds`를 하면 Bot상속 부모의 속성으로서 guilds들이 나오는데 `str`(len())으로 반환하게 한다.
        - **router로서, 응답이 str or dict가 나가야해서, bot이 가진 `self.guilds`를 `str`으로 변환하여 내보내고, 추후 우리의 router에서 쓸때도 `.response`로
          뽑아서 써야한다.**
    ```python
    @Server.route()
    async def guild_count(self, _):
        # return len(self.guilds)
        # discord.ext.ipc.errors.InvalidReturn: ('guild_count', 'Expected type Dict or string as response, got int instead!')
        # => route라서, 외부에서 .response를 찍어 확인하며, 응답은 여느 http router처럼, str() or dict() ... 
        return str(len(self.guilds))
    ```

2. Bot속 ipc Server의 router에 정보요청을 할 `ipc Client`객체도 필요하다.
3. **bot 패키지를 -> discord패키지로 변환하고, discord_bot.py -> `bot.py` + `ipc_client.py`를 만들어**
    - bot 생성 secret_key와 동일한 값으로 Clinet객체를 만든다.
    ```python
    # app/libs/discord/ipc_client.py
    from discord.ext.ipc import Client
    
    from app.common.config import DISCORD_BOT_SECRET_KEY
    
    discord_ipc_client = Client(secret_key=DISCORD_BOT_SECRET_KEY)
    
    ```
4. 이제 pages > index.py에서 import하여 @Server.route()로 만든 view_function을 `await ipc객체.request("viewfunc명")`으로 요청한다.
    - router의 응답으로서 `.response`를 찍어야, 값이 제대로 넘어온다.
    ```python
    @router.get("/")
    async def index(request: Request, session: AsyncSession = Depends(db.session)):
        # bot에 연결된 server.route에 요청
        guild_count = await discord_ipc_client.request("guild_count")
    
        print("guild_count", guild_count)
        # guild_count <ServerResponse response=1 status=OK>
        print("guild_count.response", guild_count.response)
        # guild_count.response 1
    
        context = {
            'request': request,  # 필수
            'count': guild_count.response,  # 커스텀 데이터
        }
        return templates.TemplateResponse(
            "index.html",
            context
        )
    ```
    ![img.png](../images/79.png)
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