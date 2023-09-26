## 프로젝트 소개

- 비교적 최신 웹 프레임워크인 fastAPI를 이용해서 `소셜로그인 + 알림 API` 어플리케이션을 구현합니다.
    - fastAPI선택 이유: 문서자동화, 역직렬화 속도, 비동기 지원
    - [참고문서](https://tech.kakaopay.com/post/image-processing-server-framework/)
    - python 3.9 / sqlalchemy 2.0.4 이상(relationship refresh lazy load를 위함.)
    - AWS ROUTE 53, SES 경험
    - asyncio를 적용한 비동기 어플리케이션 개발
- 구현 목표
    - fastAPI, DB 등을 모두 Dockerizing 한다.
    - Oauth 인증을 적용한다
    - Test 코드를 작성하고 CI를 활용한다.
    - Raw query대신 sqlalchemy 2.0의 mixin 등을 구현해서 활용한다.

- **[참고 프로젝트](https://github.com/riseryan89/notification-api) `개선 사항`**
    - 제작 과정 문서화 + 도커라이징 + 프로젝트 구조 변경(api패키지 도입)
    - DB table 자동 생성 적용
    - schemas.py <-> models.py 구분
    - Sqlalchemy BaseModel <-> Mixin 구분, Sqlalchemy Mixin 고도화(2.0 style + async 적용 등)
        - `Sqlalchemy 2.0 style + async sqlalchemy`를 적용한 `mixin` 구현
        - AsyncSession 사용시 BaseModel의 default칼럼 refresh prevening by `__mapper_args__ = {"eager_defaults": True}`
    - 명확한 변수화(is_exists -> exists_user, reg_info -> user_register_info 등)
    - 코드 간결화(if user: return True + return False -> return True if user else False)
    - `Pydantic v1 -> v2` 적용 및 Schema패키지 도입하여 세분화
        - 참고페이지: https://zenn.dev/tk_resilie/articles/fastapi0100_pydanticv2
        - .from_orm().dict()) -> .model_validate().model_dump()
        - class Config: orm_mode = True -> model_config = ConfigDict(from_attributes=True)
    - 미들웨어 `Exceptions handling 세분화`
    - `Logger 설정 세분화`(api log <-> db log 구분하여 미들웨어에서 logging)
    - config.py / conn.py 싱글톤 적용
    - test를 위해 faker패키지를 통한 Provider 활용
    - `fastapi-users` 패키지를 도입하여 `기존 User모델과 통합` 및 Oauth 소셜 로그인시 `CustomBackend` 구현으로 추가정보 추출하여 Users모델에 입력
        1. google 로그인 -> people API 중 personFields=`photos,birthdays,genders,phoneNumbers` 추가 입력
            - 구글클라우드 프로젝트에서 OAuth 동의화면 scope(기본 .../auth/userinfo.email, .../auth/userinfo.profile)에 scope 추가
                - `.../auth/user.birthday.read`, `.../auth/user.gender.read`, `.../auth/user.phonenumbers.read`
            ```python
            # 1. client scope 추가(profile, email 외)
            google_oauth_client = GoogleOAuth2(
                GOOGLE_CLIENT_ID,
                GOOGLE_CLIENT_SECRET,
                scopes=[
                    "openid",
                    "https://www.googleapis.com/auth/userinfo.profile",  # 구글 클라우드 - 동의에서 설정한 범위
                    "https://www.googleapis.com/auth/userinfo.email",
                    "https://www.googleapis.com/auth/user.birthday.read",  # 추가 액세스 요청 3개 (전부 people api)
                    "https://www.googleapis.com/auth/user.gender.read",
                    "https://www.googleapis.com/auth/user.phonenumbers.read",
                ])
            
            # 2. backend 객체 생성시, has_profile_callback=True 입력
            google_cookie_backend = GoogleBackend(
                name="cookie",
                transport=get_cookie_transport(),
                get_strategy=get_jwt_strategy,
                has_profile_callback=True, # 추가 프로필 요청 여부
            )
            ```
        2. kakao 로그인


- Todo
    - ~~request_service_sample.py를 test코드로 변경~~ -> 완료

## 설치

---

1. `.env` PORT 관련
    - fastAPI: docker 포팅은 환경변수 `PORT`(내부 8000고정) / local main.py 실행시 `8001` 고정
    - mysql: docker 포팅은 환경변수 + local main.py 실행 `MYSQL_PORT`(내부 3306고정) -> DB_URL / docker 돌때만 `3306`고정
        - host: docker돌면서 docker service명 `MYSQL_HOST`  / local main.py 실행시 `localhost` 고정
        - user: docker 돌면 `MYSQL_USER/PASSWORD` / local main.py 실행시 `root/root`로 설정

2. 도커가 있는 환경
    ```shell
    git clone
    .env.dev -> .env 변경 및 내용 수정
   
    docker-compose up -d (포트 - api:8000, mysdql: 13306)
    ```

3. 도커가 없는 환경
    ```shell
    git clone
    .env.dev -> .env 변경 및 내용 수정 (기본 포트 - api:8010, mysdql: 13306)
    
    venv 가상환경 생성 및 활성화
    pip install -r requirements.txt
    uvicorn app.main:app --host=0.0.0.0 --reload
    ```

## mixin 사용법

1. mixin내부에서 외부 주입 session이 없더라도, 자체적으로 CRUD하기 위한 session 발급을 위해, `Base.scoped_session` 변수에, db connection시 생성된
   async_scoped_session객체를 주입한다.
    ```python
    class SQLAlchemy(metaclass=SingletonMetaClass):
        # ...
        self._scoped_session: async_scoped_session[AsyncSession] | None = \
            async_scoped_session(
                async_sessionmaker(
                    bind=self._async_engine, autocommit=False, autoflush=False, future=True,
                    expire_on_commit=False  # refresh로 대체할려 했으나, 매번 select가 되어 필요시마다 하기로.
                ),
                scopefunc=current_task,
            )
    
    db = SQLAlchemy(**asdict(config))

    Base = declarative_base()
    # for mixin 자체 세션 발급
    Base.scoped_session = db.scoped_session

    ```

2. Base를 상속한 BaseModel을 정의한 뒤, 필요한 Mixin을 추가 상속해서 쓴다.
    ```python
    class BaseModel(CRUDMixin, ReprMixin):
        __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.
        __mapper_args__ = {"eager_defaults": True}  # default 칼럼 조회시마다 refresh 제거 (async 필수)
    
        @declared_attr
        def __tablename__(cls) -> str:
            return cls.__name__.lower()
    
        id = Column(Integer, primary_key=True, index=True)
        created_at = Column(DateTime, nullable=False, default=func.utc_timestamp())
        updated_at = Column(DateTime, nullable=False, default=func.utc_timestamp(), onupdate=func.utc_timestamp())
    
    ```

3. 해당 sessino generator는 외부 session 주입이 없을 때, 자체 session을 발급할 때 쓰인다.
    ```python
    class ObjectMixin(BaseMixin):
        #...
        async def set_session(self, session: AsyncSession = None):
    
            # 외부 O or 자신X
            if session:
                self._session, self._served = session, True
            else:
                if not getattr(self, "scoped_session"):
                    raise Exception(f'세션 주입이 안되었습니다. >> Base.scoped_session = db.scoped_session')
    
                # (외부 X) and 자신X -> 새 발급
                async with self.scoped_session() as self_session:
                    self._session = self_session
    
                self._served = False
    ```