### faker패키지를 이용한 user_info(request) 만들기
1. faker 패키지 설치
    ```shell
    pip install faker 
    
    pip freeze > .\requirements.txt
    
    docker-compose build --no-cache api; docker-compose up -d api;
    ```
    - utils > `faker_utils.py`를 생성한다.
   
#### Users테이블 수정

1. user정보 중 필수 정보 email/password 외에 name + 폰번호 + status를 faker를 통해 제공하도록 해보자.
    - 그 전에 `sex(gender)` + `age` + `sns_token` + `nickname` + `birthday`
    ```python
    class Users(BaseModel):
        status = Column(Enum("active", "deleted", "blocked"), default="active")
        email = Column(String(length=255), nullable=True, unique=True)
        pw = Column(String(length=2000), nullable=True)
        name = Column(String(length=255), nullable=True)
        phone_number = Column(String(length=20), nullable=True, unique=True)
        profile_img = Column(String(length=1000), nullable=True)
        sns_type = Column(Enum("FB", "G", "K"), nullable=True)
        marketing_agree = Column(Boolean, nullable=True, default=True)
    
        sns_token = Column(String(length=64), nullable=True, unique=True)
        nickname = Column(String(length=30), nullable=True)
        gender = Column(Enum("male", "female"), nullable=True)
        age = Column(Integer, nullable=True, default=0)
        birthday = Column(String(length=20), nullable=True)
    ```
    - migration 도구가 없기 때문에, `테이블 전체를 지웠`다가, `main.py`를 실행하여 자동 재생성 시킨다.
2. 추가로 **`one쪽의 many relationship에는 cascade="all, delete-orphan"`을 추가하고, `many의 fk에는 ondelete="CASCADE"옵션`을 추가해서 같이 지워지게 한다.**
    - many쪽의 one relationship에는 아무것도 안한다.
    - **user에서 api_keys를 조회할 때는 자주 사용될 것이므로, session안에서 불러주는 layz=True옵션을 켜두자.**
    ```python
    class Users(BaseModel):
    
        # keys = relationship("ApiKeys", back_populates="user")
        api_keys = relationship("ApiKeys", back_populates="user",
                                cascade="all, delete-orphan",
                                lazy=True
                                )
    class ApiKeys(BaseModel):
    
        # user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
        user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
        user = relationship("Users", back_populates="api_keys",
                            foreign_keys=[user_id],
                            uselist=False,
                            )
        whitelists = relationship("ApiWhiteLists", back_populates="api_key",
                                  cascade="all, delete-orphan"
                                  )
    class ApiWhiteLists(BaseModel):
        ip_address = Column(String(length=64), nullable=False)
    
        # api_key_id = Column(Integer, ForeignKey("apikeys.id"), nullable=False)
        api_key_id = Column(Integer, ForeignKey("apikeys.id", ondelete="CASCADE"), nullable=False)
        api_key = relationship("ApiKeys", back_populates="whitelists",
                               foreign_keys=[api_key_id],
                               uselist=False,
                               )
    ```
3. Enum칼럼에 들어갈 요소들을 `string tuple` -> `밖으로 빼서 Enum으로 만들고, 배정하는 방식으로 변환하여, 다른데서도 쓸 수 있게` 한다.
    - **admin 페이지, form, faker에서 사용 등**
    ```python
    class Users(BaseModel):
    
        # status = Column(Enum("active", "deleted", "blocked"), default="active")
        status = Column(Enum(UserStatus), default=UserStatus.active)
    
    class ApiKeys(BaseModel):
    
        # status = Column(Enum("active", "stopped", "deleted"), default="active")
        status = Column(Enum(ApiKeyStatus), default=ApiKeyStatus.active)
    ```
   

#### 다시 faker
1. 한국어버전의 faker객체를 만들고, add_provider할 UserProvider class를 정의해서, Provider속 메서드가 `faker객체.provider속메서드`로 호출할 수 있게 한다.
    - **이 때, 특정 정보는 외부에서 직접 주입할 수 잇으니 `dict() | dict()` 병합을 통해, 덮어쓰기(or 추가)되는 전략을 취한다.**
    ```python
    from faker import Faker
    from faker.providers import BaseProvider
    
    
    class UserProvider(BaseProvider):
    
        def create_user_info(self, **kwargs):
            return dict(
    
            ) | kwargs
    
    
    my_faker: Faker = Faker(locale='ko_KR')
    my_faker.add_provider(UserProvider)
    
    if __name__ == '__main__':
        print(my_faker.create_user_info(email='asdf'))
        # {'email': 'asdf'}
    ```
   

2. **Provider내부에서 fake객체를 사용하려면 `self.generator`를 쓰면 된다.**
    - **faker객체.profile()을 주면, dict정보가 나오는데 거기서 필요한것만 `fields=[]`옵션으로 골라서 dict를 만들 때, 뽑아쓴다.**
    ```python
    class UserProvider(BaseProvider):
    
        def create_user_info(self, **kwargs):
            _faker = self.generator
            # profile = _faker.profile()
            # print(profile)
            # {'job': '여행 및 관광통역 안내원', 'company': '유한회사 서',
            # 'ssn': '130919-1434984', 'residence': '인천광역시 동작구 백제고분가 (영숙이리)',
            # 'current_location': (Decimal('-58.1016835'), Decimal('-118.314709')),
            # 'blood_group': 'B-', 'website': ['https://gimgim.com/', 'http://www.baecoei.org/'],
            # 'username': 'sunog18', 'name': '안정호', 'sex': 'M', 'address': '서울특별시 강서구 논현길 (은정박읍)',
            # 'mail': 'hwangsumin@hotmail.com', 'birthdate': datetime.date(1962, 6, 12)}
            fake_profile = _faker.profile(
                fields=['ssn', 'username', 'name', 'sex', 'mail', 'birthdate']
            )
            phone_number = _faker.bothify(text='010-####-####')
    
            return dict(
                email=fake_profile['mail'],
                pw="string",
                phone_number=phone_number,
                name=fake_profile['name'],
                nickname=fake_profile['username'],
                birthday=fake_profile['ssn'][:6],
            ) | kwargs
    
    
    my_faker: Faker = Faker(locale='ko_KR')
    my_faker.add_provider(UserProvider)
    
    if __name__ == '__main__':
        print(my_faker.create_user_info(email='asdf'))
        # {'email': 'asdf', 'pw': 'string', 'phone_number': '010-3395-0942', 'name': '강건우', 'nickname': 'cunjai', 'birthday': '470210'}
    
    ```
   
3. enum 필드는, enum을 가져와서 `faker.random_element()`에 넣어준 뒤, `.value`로 꺼내 쓴다.
    - 숫자 랜덤은 `faker.random.randint(,)`를 사용한다.
    - **추후 생성할 땐 status="active"로 지정해줘서 쓰면 될듯**
    ```python
    class UserProvider(BaseProvider):
    
        def create_user_info(self, **kwargs):
            _faker = self.generator
            fake_profile = _faker.profile(
                fields=['ssn', 'username', 'name', 'sex', 'mail']
            )
            phone_number = _faker.bothify(text='010-####-####')
            age = _faker.random.randint(16, 70)
            status = _faker.random_element(UserStatus).value
    
            return dict(
                email=fake_profile['mail'],
                pw="string",
                phone_number=phone_number,
                name=fake_profile['name'],
                nickname=fake_profile['username'],
                birthday=fake_profile['ssn'][:6],
                age=age,
                status=status,
            ) | kwargs
        
    my_faker: Faker = Faker(locale='ko_KR')
    my_faker.add_provider(UserProvider)
    
    if __name__ == '__main__':
        print(my_faker.create_user_info(status='active'))
    ```
   


#### 다시 conftest
##### user_info fixture(user객체가 아니라 reqeust user info가 필요하다.)
1. 이제 설정된 faker객체를 import해서 fixture를 만든다.
    ```python
    @pytest.fixture(scope="session")
    def user_info() -> dict[str, str]:
        return my_faker.create_user_info(status="active")

    ```
    ```python
    # test_xxx.py
    async def test_config(user_info):
        print(user_info)
        assert True
    # PASSED [100%]{'email': 'eunseo56@hanmail.net', 'pw': 'string', 'phone_number': '010-9838-4722', 'name': '이지현', 'nickname': 'hongjeongja', 'birthday': '180101', 'age': 56, 'status': 'active'}

    ```
   
2. **`추가적으로` fixture내부에서 `return func`을 통해 `인자를 받아서, 함수를 반환하는 fixture`를 정의해서 Depends처럼 사용할 수 있다.**
    ```python
    @pytest.fixture(scope="session")
    def create_user_info():
        def func(**kwargs):
            return my_faker.create_user_info(**kwargs, status="active")
    
        return func
    
    async def test_config(create_active_user_info):
        print(create_active_user_info(email="123@gmail.com"))
        assert True
    ```
    - 이것은 나중에 `client 생성 전 app의 dependency를 오버라이딩`할 때 응용할 수 있다.
    ```python
    @pytest.fixture
    def add_user(session):
        def func(username: str = None, first_name: str = None, last_name: str = None):
            row = models.User(
                username=username or "fc2021",
                first_name=first_name or "fast",
                last_name=last_name or "campus",
            )
            session.add(row)
            session.commit()
            return row
    
        return func
    
    @pytest.fixture
    async def client(app, add_user):
        async def mock_get_user():
            return add_user()
    
        app.dependency_overrides[deps.get_user] = mock_get_user
    
        async with AsyncClient(app=app, base_url="http://test/v1") as ac:
            models.Base.metadata.drop_all(bind=engine)
            models.Base.metadata.create_all(bind=engine)
            yield ac
    ```
   

##### login_headers: user_info로 미리 회원가입(user생성 + jwt access_token 생성 후) -> 로그인준비(headers의 Authorization)
1. user_info(user_request)를 받아 access token을 반환하는 로직을 복붙 후에, headers까지만든다.
    ```python
    @pytest.fixture(scope="session")
    async def login_headers(user_info: dict[str, str]) -> dict[str, str]:
        """
        User 생성 -> data(dict) 생성 -> token 생성
        """
        new_user = await Users.create(auto_commit=True, refresh=True, **user_info)
    
        new_user_data = UserToken \
            .model_validate(new_user) \
            .model_dump(exclude={'pw', 'marketing_agree'})
    
        new_token = await create_access_token(data=new_user_data, expires_delta=24, )
    
        return dict(
            Authorization=f"Bearer {new_token}"
        )
    ```
    ```python
    async def test_config(login_headers):
        print(login_headers)
        assert True
    ```
   
2. 이 때, refresh로 인해 무한로딩이 걸린다.
    - **save메서드에서 refresh는 외부세션 주입시에만 가능하도록 변경**
    ```python
    async def save(self, auto_commit=False, refresh=False):
    
        try:
    
            if self.id is not None and self.served:
                await self.session.merge(self)
            else:
                self.session.add(self)
                await self.session.flush()
    
            if auto_commit:
                await self.session.commit()
                # if refresh:
                if self.served and refresh:
                    await self.session.refresh(self)
                else:
                    self._session = None
                    self._served = False
    
            return self
    ```
   
##### api_key_info: 로그인headers + user_memo -> api 생성하여, access_key + secret_key dict
- asyncClient + 로그인headers + api user_memo(랜덤) ->  api생성 및 access+secret_key 첫응답
```python
@pytest.fixture(scope="session")
async def api_key_info(async_client: AsyncClient, login_headers: dict[str, str]):
    """
    asyncClient + 로그인 headers + api user_memo(랜덤)
     ->  api생성 및 access+secret_key 첫응답 속에 정보 추출
    """
    response = await async_client.post(
        "api/v1/users/apikeys",
        headers=login_headers,
        json=dict(user_memo=f"TESTING: {str(datetime.utcnow())}")
    )

    assert response.status_code == 201

    response_body = response.json()
    assert "access_key" in response_body
    assert "secret_key" in response_body

    return response_body
    # {'user_memo': 'TESTING: 2023-09-20 01:09:27.206007', 'id': 1,
    # 'created_at': '2023-09-20T01:09:31',
    # 'access_key': '97a17d4c-50c3-41d5-ab7d-bd086699-ed1b-4cfc-a58a-267911c049f0',
    # 'secret_key': 'uVEMWd99axBFzs7CP5i3fCHcxZ98bQJSGB0r3zzW'}
```

##### request_service: api_key_dict의 access_key-> 서비스로그인용 qs + secret_key -> 서비스로그인용 headers + asyncclient로 접속 
1. 서비스 요청시 url에는 `access_key`와 `timestamp(KST) int`가 key=&timestamp로 들어가야한다.
    - 그 전에 테스트 router 말고, 특정 서비스라면, servicename이 들어가야한다.
    - **이 때, service네임이 없는데도 불구하고 `/`로 끝나게 되면 fastapi는 redirect요청을 응답(307)하므로 조심한다.**
    - 직접만든 dict형 query_params를 to_query_string 유틸에 넣고 url에 붙여준다.
    ```python
    @pytest.fixture(scope="session")
    async def request_service(async_client: AsyncClient, api_key_info: dict[str, str]):
    
        # 1. 서비스 요청 url 생성 with access_key -> query_string -> url
        url: str = f"/api/v1/services"
        service_name: str = ""
    
        # /api/v1/services/?key=e5ca4723-d16e-4d6b-8e90-875ad56c-b1d2-46db-833f-e6b985e281f3&timestamp=1695173079
        # => 307 redirect 응답
        # => fastapi에서 마지막 endpoint에 /가 있으면 rediect되도록 인식된다. -> service_name이 있을때만 앞에 '/'를 붙인다.
        if service_name:
            url += f"/{service_name}"
    
        datetime_kst = D.datetime(diff_hours=9)
        timestamp = int(datetime_kst.timestamp())
        params = dict(key=api_key_info['access_key'], timestamp=timestamp)
        query_string: str = to_query_string(params)
    
        url += f"?{query_string}"
    ```
   
2. 이제 headers에 `secret=`키에 **`secret_key` + timestamp가 포함된 `query_string`으로 `hash된 secret_key값`이 들어가야한다**
    ```python
    @pytest.fixture(scope="session")
    async def request_service(async_client: AsyncClient, api_key_info: dict[str, str]):
    
        # 1. 서비스 요청 url 생성 with access_key -> query_string -> url
        url: str = f"/api/v1/services"
        service_name: str = ""
    
        # /api/v1/services/?key=e5ca4723-d16e-4d6b-8e90-875ad56c-b1d2-46db-833f-e6b985e281f3&timestamp=1695173079
        # => 307 redirect 응답
        # => fastapi에서 마지막 endpoint에 /가 있으면 rediect되도록 인식된다. -> service_name이 있을때만 앞에 '/'를 붙인다.
        if service_name:
            url += f"/{service_name}"
    
        datetime_kst = D.datetime(diff_hours=9)
        timestamp = int(datetime_kst.timestamp())
        params = dict(key=api_key_info['access_key'], timestamp=timestamp)
        query_string: str = to_query_string(params)
    
        url += f"?{query_string}"
    
        # 2. service_login_headers 생성  'secret'=  query_string + secret_key를 해쉬한 값(DB와 일치)
        hashed_secret: str = hash_query_string(query_string, api_key_info['secret_key'])
        service_login_headers = dict(secret=hashed_secret)
        # {'secret': '/6Br4HL0G4QlYbmMvFD35hCQ1BDdD86MzKaAgyNao/Q='}
    
        response = await async_client.get(url, headers=service_login_headers, )
        assert response.status_code == 200  # <Response [307 Temporary Redirect]>
    
        response_body = response.json()
    
        return response_body
    ```
   

3. **외부 변수가 필요한 fixture는 `def func -> return func`으로 정의하여, 테스트시, 인자를 넣고 호출할 수 있게 만든다.**
   - `service_name`
   - access/secret_key(api_key_info)로 만들어지는 `headers 에 추가 요소` by dict 병합
   - async_client의 `http 메서드` 및 `htpp요청시 옵션 (headers=외 추가 등등)` -> dict(headers=)를 기본으로 한 뒤, 병합
   - response에서 `허용할 status_code` - tuple 200, 201
    ```python
    @pytest.fixture(scope="session")
    async def request_service(async_client: AsyncClient, api_key_info: dict[str, str]):
        service_name: str = ""
        http_method: Literal["get", "post", "put", "delete", "options"] = "get"
        additional_headers: dict = {}
        method_options: dict = {}
        allowed_status_code: tuple = (200, 201)
    
        # 1. 서비스 요청 url 생성 with access_key -> query_string -> url
        url: str = f"/api/v1/services"
    
        # fastapi에서 마지막 endpoint에 /가 있으면 rediect되도록 인식된다. -> service_name이 있을때만 앞에 '/'를 붙인다.
        if service_name:
            url += f"/{service_name}"
    
        datetime_kst = D.datetime(diff_hours=9)
        timestamp = int(datetime_kst.timestamp())
        params = dict(key=api_key_info['access_key'], timestamp=timestamp)
        query_string: str = to_query_string(params)
    
        url += f"?{query_string}"
    
        # 2. service_login_headers 생성  'secret'=  query_string + secret_key를 해쉬한 값(DB와 일치)
        hashed_secret: str = hash_query_string(query_string, api_key_info['secret_key'])
        service_login_headers = dict(secret=hashed_secret) | additional_headers
        # {'secret': '/6Br4HL0G4QlYbmMvFD35hCQ1BDdD86MzKaAgyNao/Q='}
    
        method_options: dict = dict(headers=service_login_headers) | method_options
    
        # response = await async_client.get(url, headers=service_login_headers, )
        # response = await async_client.get(url, **method_options)
        client_method = getattr(async_client, http_method.lower())
        response = await client_method(url, **method_options)
    
        # assert response.status_code == 200
        assert response.status_code in allowed_status_code
    
        response_body = response.json()
    
        return response_body
    ```
    ```python
    @pytest.fixture(scope="session")
    async def request_service(async_client: AsyncClient, api_key_info: dict[str, str]) -> Any:
        async def func(
            http_method: Literal["get", "post", "put", "delete", "options"],
            service_name: str = "",
            additional_headers: dict = {},
            method_options: dict = {},
            allowed_status_code: tuple = (200, 201),
        ):
    
            # 1. 서비스 요청 url 생성 with access_key -> query_string -> url
            url: str = f"/api/v1/services"
    
            # fastapi에서 마지막 endpoint에 /가 있으면 rediect되도록 인식된다. -> service_name이 있을때만 앞에 '/'를 붙인다.
            if service_name:
                url += f"/{service_name}"
    
            datetime_kst = D.datetime(diff_hours=9)
            timestamp = int(datetime_kst.timestamp())
            params = dict(key=api_key_info['access_key'], timestamp=timestamp)
            query_string: str = to_query_string(params)
    
            url += f"?{query_string}"
    
            # 2. service_login_headers 생성  'secret'=  query_string + secret_key를 해쉬한 값(DB와 일치)
            hashed_secret: str = hash_query_string(query_string, api_key_info['secret_key'])
            service_login_headers = dict(secret=hashed_secret) | additional_headers
            # {'secret': '/6Br4HL0G4QlYbmMvFD35hCQ1BDdD86MzKaAgyNao/Q='}
    
            method_options: dict = dict(headers=service_login_headers) | method_options
    
            # response = await async_client.get(url, headers=service_login_headers, )
            # response = await async_client.get(url, **method_options)
            client_method = getattr(async_client, http_method.lower())
            response = await client_method(url, **method_options)
    
            # assert response.status_code == 200
            assert response.status_code in allowed_status_code
    
            response_body = response.json()
    
            return response_body
    
        return func
    ```
    
    ```python
    async def test_config(request_service):
        # print(await request_service("get"))
        print(await request_service("post", service_name="kakao/send", method_options=dict(
            json=dict(title='zz', message='vvv')
        )))
    
        assert True
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