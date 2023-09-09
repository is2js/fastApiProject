### mysql docker 세팅

1. docker 내부에 `db > mysql` 폴더를 만들고, `Dockerfile`과 자식폴더 `init, config`폴더를 만든다.
    - host -> docker에서 받아 쓸 파일들을 config/init폴더에 넣어줄 예정이다.
    - cf) db > mysql 내부에 `자동`으로 생길 `data / logs` 폴더는 config/xxx.cnf파일에 의해 docker -> host로 data와 로그파일들을 쌓아줄 예정이다.

2. mysql용 `Dockerfile`은 사용할 이미지만 지정해준다.
    - volume 및 설정들은 cnf파일 + docke-compose에서 해결할 예정

```dockerfile
FROM mysql:8.0.31


ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
```

3. docker > db > mysql > config 폴더에 `my.cnf`를 아래와 같이 정의한다.
    - utf설정 및 log파일명 설정을 해준다.

```editorconfig
[client]
default-character-set = utf8mb4

[mysql]
default-character-set = utf8mb4

[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
range_optimizer_max_mem_size = 16777216

log-error = /var/log/mysql/error.log
general_log_file = /var/log/mysql/log_output.log
general_log = 1
slow_query_log_file = /var/lib/mysql/mysql_slow.log
slow_query_log = 1
log_queries_not_using_indexes = 1
long_query_time = 2
```

4. docker > db > mysql > init 폴더에는 `init.sql`을 작성한다
    - 초기에 미리 생성해야할 db, table, 데이터가 있다면 미리 insert해준다.
    - **한번 도커를 실행후 매번 실행되는게 아니다. `자동생성 data폴더(+log폴더) 삭제` + `이미지 빌드 + 재실행`까지 해줘야 init.sql이 실행된다.**
    - db use + table 생성 + csv 데이터 삽입 예시: https://mycup.tistory.com/382
    - **나는 test table을 생성하도록하여, init.sql이 잘 작동하는지만 테스트했다.**

```sql
DROP
DATABASE TESTDB;
CREATE
DATABASE IF NOT EXISTS TESTDB;
USE
TESTDB;

CREATE TABLE IF NOT EXISTS TEST
(
    title VARCHAR
(
    50
) NOT NULL
    );
```

5. 이제 root의 docker-compose.yml에서 `mysql` 서비스를 작성한다.
    - build는 루트context로 시행하고, dockerfile의 경로를 잡아준다.
    - ports는 도커실행시에는 host의 13306으로 빼준다.
    - 환경변수는 기본적으로 `TZ, MYSQL_ROOT_PASSWORD, MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD`를 작성해주는데,
        - **user이름과 password를 travis로 해주면 나중에 ci/cd할 때 편하다고 한다.**
        - MYSQL_DATABASE를 입력하면 자동으로 db가 생성된다.
    - 마운팅의 경우, my.cnf파일과 init폴더내부파일들을 각각 아래 폴더로 마운팅시켜주고
        - -> /etc/mysql/conf.d 폴더 (*.cnf파일들을 자동스캔)
        - -> /docker-entrypoint-initdb.d 폴더 (entrypoint: docker-entrypoint.sh 입력시 자동실행됨)
        - data와 log는 상시보존되기 위해 mysql/data, mysql/logs 폴더로 마운팅 시켜주면, 실행시 폴더들과 데이터가 생성된다.
    - entrypoint에는 `docker-entrypoint.sh`, `mysqld` 를 걸어줘서, 시작시 자동실행되게 한다.

```ini
services :
    mysql:
    build:
    context: .
    dockerfile: docker/db/mysql/Dockerfile
    restart: always
    env_file:
    - .env
    ports:
# [수정]
    - "13306:3306"
    environment:
    TZ: Asia/Seoul
    MYSQL_ROOT_PASSWORD: root
    MYSQL_DATABASE: notification_api
    MYSQL_USER: travis
    MYSQL_PASSWORD: travis
    volumes:
# 1. my.cnf 설정파일 host(cnf파일 미리작성) -> docker (*.cnf파일을 읽게됨)
    - ./docker/db/mysql/config:/etc/mysql/conf.d
# 2. host (자동실행될 스크립트들) -> docker
    - ./docker/db/mysql/init:/docker-entrypoint-initdb.d
# 3. docker 생성 data들을 공유받게 됨  host <- docker (생성)
    - ./docker/db/mysql/data:/var/lib/mysql
    - ./docker/db/mysql/logs:/var/log/mysql
    - docker-entrypoint.sh
    - mysqld
```

6. docker compose를 작동시키고, 파이참-데이터베이스에서 `localhost + 13306`포트로 travis/travis으로 접속시킨다.
    - 도커에서 접속하려면 터미널 > mysql -utravis -ptravis
    - **init.sql을 수정하거나 등등 새로 빌드하려면, `반드시 data폴더 삭제`후 docker를 새로 빌드 + 작동**시켜준다.

```shell
docker-compose build --no-cache mysql; docker-compose up -d mysql;
```

7. 이제 **data폴더와 logs폴더를 gitignore에 추가한다**

8. 추가로 **api서비스 도커에서 mysql 서비스 도커를 사용하기 위해 `links`와 `depends_on`을 걸어준다.**

```ini
services :
    mysql:
    api:
# mysql 서비스 도커를 이용하기 위함.
    links:
    - mysql
    depends_on:
    - mysql
```

### sqlalchemy, pymysql 설치

1. sqlalchemy(2.0), pymysql(psycopg-2binary), alembic, `cryptography` 패키지를 설치한다.
    - cryptography는 fastapi에서 mysql에 접속하기 위해 필요한 패키지다.
2. 패키지 설치 후, pip freeze를 한 뒤, docker를 재빌드하여 docker 환경을 바꿔준다.

```shell
pip freeze > .\requirements.txt

docker-compose build --no-cache api; docker-compose up -d api;
```

### app 코드 작성

#### Config

1. **도커는 로컬용이므로, `LocalConfig`에 해당 docker DB_URL을 입력해준다.**
    - **이 때, host에서 접속하는 `localhost` + `13306`이 아니라**
    - **도커끼리의 연결인 links에 걸린 `mysql`서비스명을 address로 + 도커자체의 port인 `3306`으로 연결해줘야한다.**

```python
@dataclass
class LocalConfig(Config):
    PROJ_RELOAD: bool = True

    # 도커 서비스 mysql + 도커자체port 3306으로 접속
    # - host에 연결시에는 localhost + 13306
    DB_URL: str = "mysql+pymysql://travis:travis@mysql:3306/notification_api?charset=utf8mb4"
```

2. create_app에서 conf객체를 dict화 -> 언패킹해서, `db.init_app(app, **conf_dict)`의 형태로, `DB_URL`이 keyword인자로 전달되도록 한다.
    - **미리 생성되어 나중에 초기화되는 `db` 관리 객체는 `python싱글톤으로서 시작시 미리 1개를 이미 생성 -> 나중에 데이터 받아 초기화`하는 전략을 쓴다.**
        - **딱 1곳만 db session pool을 유지하도록 한다.**

```python
def create_app():
    """
    앱 함수 실행
    :return:
    """
    app = FastAPI()

    config = conf()
    config_dict = asdict(config)

    db.init_app(app, **config_dict)

    return app
```

3. app > database 폴더에 3개의 파일을 생성한다.
    - conn.py crud.py models.py

#### conn.py

4. **conn.py 내부에는 `SQLAlchemy` 싱글톤 객체를 만들어 관리되게 하는데, db라는 객체를 선언해서 띄워놓고, 내부의 `init_app()`메서드에 app객체 및 설정 keyword인자를
   받아둔다.**
    - **app객체와 키워드인자로 초기화할 수 있지만, 차후에도 가능하도록 app객체 존재여부를 검사해서, 없으면 내부 메서드로 따로 한번더 초기화한다.**

```python
class SQLAlchemy:

    # 1. 애초에 app객체 + 키워드인자들을 받아서 생성할 수 있지만,
    def __init__(self, app: FastAPI = None, **kwargs) -> None:
        self._engine = None
        self._Session = None
        # 2. app객체가 안들어올 경우, 빈 객체상태에서 메서드로 초기화할 수 있다. 
        if app is not None:
            self.init_app(app=app, **kwargs)
```

- **해당 `db 관리 객체` SQLAlchemy는 `싱글톤으로서 1개의 객체`로만 관리해야하므로 `startup`될 당시 `1개만 미리 생성`해놓는다.**

```python
class SQLAlchemy:


# ...
db = SQLAlchemy()
```

5. 이제 외부에서 외부데이터를 받아줄, init_app 메서드를 정의해준다.
    - app과 config 속 keyword인자들을 받았지만, 내부에서 kwargs를 dict로 사용할 수 있다.
    - **DB_URL은 반드시 존재해야하므로, `get`으로 `없으면 None을 반환`받지만**
    - **DB_POOL_RECYCLE, DB_ECHO는 `setdefault`로 get `없으면 kwargs에 기본값을 설정 후, 설정값 반환`받도록 해준다.**
    - config -> sqlalchemy에 필요한 정보는 `url, echo여부, pool_recycle, pool_pre_ping` 4개 정도로 create_engine한다.
    - 만든 engine과 session은 `싱글톤의 self._engine, self._session`에 박아준다
    - 만든 engine으로 sessionmaker를 이용해 auto가 없는 옵션으로 bind하여 session을 박아준다.
    - **이제 넘겨받은 app객체로, `@app.on_event()` 중 startup, shutdown을 지정하여, 앱시작/종료시 engine과 session을 처리해준다.**
    - **시작시에는 engine만 connect 해주고 / 종료시에는 session부터 close_all + engine dispose 해준다.**

```python
class SQLAlchemy:

    # 1. 애초에 app객체 + 키워드인자들을 받아서 생성할 수 있지만,
    def __init__(self, app: FastAPI = None, **kwargs) -> None:
        self._engine = None
        self._Session = None
        # 2. app객체가 안들어올 경우, 빈 객체상태에서 메서드로 초기화할 수 있다.
        if app is not None:
            self.init_app(app=app, **kwargs)

    def init_app(self, app: FastAPI, **kwargs):
        """
        DB 초기화
        :param app:
        :param kwargs:
        :return:
        """
        database_url = kwargs.get("DB_URL")
        pool_recycle = kwargs.setdefault("DB_POOL_RECYCLE", 900)
        echo = kwargs.setdefault("DB_ECHO", True)

        self._engine = create_engine(database_url, echo=echo, pool_recycle=pool_recycle, pool_pre_ping=True, )
        self._Session = sessionmaker(bind=self._engine, autocommit=False, autoflush=False, )

        @app.on_event("startup")
        def start_up():
            self._engine.connect()
            logging.info("DB connected.")

        @app.on_event("shutdown")
        def shut_down():
            self._Session.close_all()
            self._engine.dispose()
            logging.info("DB disconnected.") 
```

- **이제 app event만 설정해주는 부분만 method로 추출해서 나눠준다.**
```python
def init_app(self, app: FastAPI, **kwargs):
    #...
    self._engine = create_engine(database_url, echo=echo, pool_recycle=pool_recycle, pool_pre_ping=True, )
    self._Session = sessionmaker(bind=self._engine, autocommit=False, autoflush=False, )
    self.init_app_event(app)
    
def init_app_event(self, app):
    @app.on_event("startup")
    def start_up():
        self._engine.connect()
        from .models import Users
        Base.metadata.create_all(bind=self._engine)
        logging.info("DB connected.")

    @app.on_event("shutdown")
    def shut_down():
        self._Session.close_all()
        self._engine.dispose()
        logging.info("DB disconnected.")
```

6. 이제 main.py의 create_app에서 싱글톤 db객체를 import시켜서, app과 config설정이 제대로 되도록 한다.

```python
from app.database.conn import db


def create_app():
    db.init_app(app, **config_dict)
    # ...
    return app
```

7. 이제 연결이 잘되는 것을 확인했으면, db객체에서 쓸 `get_db`메서드, `session`프로퍼티, `engine`프로퍼티를 정의해준다.
    - **이 때, sessionmaker로 만든 것은 순수 session객체가 아니라 Session클라스임을 생각하자.**
    - **세션객체를 만들고, yield+close까지 정의된 메서드 -> 호출하기 쉽게 session프로퍼티 추가**
    - **내부 egnine객체를 호출하는 프로퍼티 추가**

```python
class SQLAlchemy:
    # ...
    def get_db(self):
        """
        요청시마다 DB세션 1개만 사용되도록 yield 후 close까지
        :return: 
        """
        # 초기화 X -> Session cls없을 땐 에러 
        if self._Session is None:
            raise Exception("must be called 'init_app'")

        # 세션 객체를 만들고, yield한 뒤, 돌아와서는 close까지 되도록
        db_session = None
        try:
            db_session = self._Session()
            yield db_session
        finally:
            db_session.close()

    # get_db를 프로퍼티명()으로 호출할 수 있게, 호출전 함수객체를 return하는 프로퍼티
    @property
    def session(self):
        return self.get_db

    # 이것은 수정불가능한 내부 객체를 가져와야만 할 때
    @property
    def engine(self):
        return self._engine
```

8. **매번 돌려써야하는 Base객체 역시, 싱글톤으로서, 같은 db싱글톤객체가 있는 conn.py에 정의해준다.**

```python
db = SQLAlchemy()
Base = declarative_base()
```

#### models > base.py - BaseModel + auth.py - Users

1. **app > `models`폴더를 생성하고, `__init__`, `base`, `auth` .py 를 만든다.**
2. base.py에는 Base를 상속하는 `BaseModel`부터 생성한다.
    - 추상table으로서 abstract=True 옵션을 주고, @declarded_attr로서 tablename을 클래스의 소문자로 만든다.
    - **id, created_at, updated_at를 추가 고정필드로 생성하고, 자동으로 주어지는 id를 이용해 hash()로 hash를 만든다.**
    ```python
    class BaseModel(Base):
        __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.
    
        @declared_attr
        def __tablename__(cls) -> str:
            return cls.__name__.lower()
    
        id = Column(Integer, primary_key=True, index=True)
        created_at = Column(DateTime, nullable=False, default=func.utc_timestamp())
        updated_at = Column(DateTime, nullable=False, default=func.utc_timestamp(), onupdate=func.utc_timestamp())
    

    
        # id가 아닌 id의 해쉬값
        def __hash__(self):
            return hash(self.id)
    ```

2. `auth.py`에는 BaseModel을 상속한, `Users`모델을 만든다.
    - **sqlalchemy의 Enum()에 콤마로 연결된 데이터를 넣고, default=로 하나를 지정해준다.**
    - email은 email없이 `facebook` 폰번호로 가입한 사람이 있을 수 있으니, default이 nullable=False 대신 True로 준다.
    - password도 소셜로그인하면 필요없게 되서 nullable로 지정해준다.
    - 그외 name, phone-number(unqiue), profile_img, sns_type, marketing_agree를 전부 nullable로 준다.

```python
class Users(BaseModel):
    status = Column(Enum("active", "deleted", "blocked"), default="active")
    email = Column(String(length=255), nullable=True)
    pw = Column(String(length=2000), nullable=True)
    name = Column(String(length=255), nullable=True)
    phone_number = Column(String(length=20), nullable=True, unique=True)
    profile_img = Column(String(length=1000), nullable=True)
    sns_type = Column(Enum("FB", "G", "K"), nullable=True)
    marketing_agree = Column(Boolean, nullable=True, default=True)
    # keys = relationship("ApiKeys", back_populates="users")
```

- **이후 init.py에는 생성된 auth의 풀경로 + `*`로 모든 class를 import시켜준다.**

```python
from app.models.user import *

```

3. **DB table을 자동생성하기 위해, `conn.py의 init_app() 내부`에서, models패키지의 모든 테이블을 명시(모듈레벨이라서 `*` 불가) Users를 import한뒤, Base.metadata.create_all()을 self._engine으로 해준다.**

```python
class SQLAlchemy:

    # ...

    def init_app(self, app: FastAPI, **kwargs):
        database_url = kwargs.get("DB_URL")
        pool_recycle = kwargs.setdefault("DB_POOL_RECYCLE", 900)
        echo = kwargs.setdefault("DB_ECHO", True)

        self._engine = create_engine(database_url, echo=echo, pool_recycle=pool_recycle, pool_pre_ping=True, )
        self._Session = sessionmaker(bind=self._engine, autocommit=False, autoflush=False, )
        self.init_app_event(app)
        
        # table 자동 생성
        from app.models import Users
        Base.metadata.create_all(bind=self._engine)
```

4. 이제 BaseModel에 create를 만들어주기 위해, **id, created_at의 자동고정값을 제외한 칼럼들을 추출해주는 메서드 `all_columns`를 정의해준다**

```python
class BaseModel(Base):
    # ...
    def all_columns(self):
        return [c for c in self.__table__.columns if c.primary_key is False and c.name != "created_at"]

```

5. create함수는 `외부에서 주어지는 공용세션`으로만 진행한다. 내부에서 자체 생성하지 않는다.
    - 일단 먼저 Model의 객체 obj를 생성하고, self메서드` .all_columns()를 호출하여 순회하면서, kwargs로 들어온 데이터에 포함되어 있는 것만 입력`한다(nullable은 안들어올 수
      있으니)
    - flush는 기본으로 하고, 인자의 autocommit여부에 따라, commit해서 close()한다.

```python
class BaseModel(Base):
    # ...
    @classmethod
    def create(cls, session: Session, auto_commit=False, **kwargs):
        obj = cls()
        # id, created_at 제외 칼럼들을 돌면서, kwargs로 들어온 것 중에 있는 칼럼명의 경우, setattr()
        for col in obj.all_columns():
            col_name = col.name
            if col_name not in kwargs:
                continue
            setattr(obj, col_name, kwargs.get(col_name))

        session.add(obj)
        # 일단 flush해서 session을 유지하다가, auto_commit=True까지 들어오면, commit하면서 닫기
        session.flush()
        if auto_commit:
            session.commit()

        return obj
```

#### router > index.py

1. app > router폴더를 만들고, index.py를 생성한다
    - fastapi의 APIRouter()로 객체를 만든 뒤, @router.get('/')으로 기본 라우트를 만든다.
    - async def로 비동기 라우터를 만들면서, **fastapi의 Depends를 이용해 callable한 함수객체 db.session을 넣어주고, session객체를 반환받는다.**
    - return은 starlette.responses의 Response로 string을 응답한다.
    - **Users모델을 가져온 뒤, classmehtod인 .create()를 이용해서 생성한다. 필수인 session과 auto_commit여부를 입력해준 뒤, kwarg로 필요한 데이터를 입력해준다.**

```python
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.database.conn import db
from app.models import Users

router = APIRouter()


# create가 포함된 route는 공용세션을 반드시 주입한다.
@router.get("/")
async def index(session: Session = Depends(db.session)):
    # user = Users(name='조재성')
    # session.add(user)
    # session.commit()

    Users.create(session, auto_commit=True, name='조재성')

    current_time = datetime.utcnow()
    return Response(f"Notification API (UTC: {current_time.strftime('%Y.%m.%d %H:%M:%S')} )")
```

2. 생성된 router를 create_app의 app객체에 등록해준다.
    - **index.py를 import한 뒤, index.`router객체`를 app에 .include_router()로 더해준다.**

```python
from app.router import index


def create_app():
    """
    앱 함수 실행
    :return:
    """
    app = FastAPI()
    # route 등록
    app.include_router(index.router)

    return app

```

3. main.py에 기존에 있었던 `@app.get`의 router없이 바로 라우트 만드는 코드들은 삭제해준다.

### 도커 명령어

1. (패키지 설치시) pip freeze 후 `api 재실행`

```shell
pip freeze > .\requirements.txt

docker-compose build --no-cache api; docker-compose up -d api;
```

2. (init.sql 재작성시) data폴더 삭제 후, `mysql 재실행`

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