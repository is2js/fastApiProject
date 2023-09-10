### ApiKeys, ApiWhiteLists 테이블 model 생성

1. models/user.py에 같이 정의한다.
    - **`fk 칼럼`을 `one테이블을 string`으로 지정하여 ForeignKey("`소문자테이블명`.id") + nullable=False 로 지정한다.**
    - **fk 칼럼 정의시, `one에 대한 relationship`도 같이 정의해주는데, 이때는 `one테이블을 string으로 주되 Class명`이 들어가는 relationship(`클래스명`, )으로
      지정한다**
    - **fk가 여러개 인 다대다 테이블에서 비롯했지만, `relationship 정의시 foreign_keys=[fk칼럼변수]에 fk를 명시적으로 지정`해주자.**
    - **relationship의 대상이 one이면 `uselist=False`로서, list가 아닌 객체로 반환되도록 설정하고,
      각각은 `backref대신 back_populates로 양쪽에서 서로 relationship을 지정`해준다.**

    ```python
    class Users(BaseModel):
        # ...
        keys = relationship("ApiKeys", back_populates="user")
   
    class ApiKeys(BaseModel):
        access_key = Column(String(length=64), nullable=False, index=True)
        secret_key = Column(String(length=64), nullable=False)
        user_memo = Column(String(length=40), nullable=True)
        status = Column(Enum("active", "stopped", "deleted"), default="active")
    
        user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
        # users = relationship("Users", back_populates="keys")
        user = relationship("Users", back_populates="keys",
                            foreign_keys=[user_id],
                            uselist=False,
                            )
    
        is_whitelisted = Column(Boolean, default=False)
        whitelists = relationship("ApiWhiteLists", back_populates="api_key")
    
    
    class ApiWhiteLists(BaseModel):
        ip_addr = Column(String(length=64), nullable=False)
        api_key_id = Column(Integer, ForeignKey("apikeys.id"), nullable=False)
        api_key = relationship("ApiKeys", back_populates="whitelists",
                               foreign_keys=[api_key_id],
                               uselist=False,
                               )
    ```

2. 이 때, ApiKeys테이블에서는
    - apikey에 대한 `access_key`와 `secret_key`가 2개 동시에 생성되어야한다.
    - `user_memo`는 apikey생성시 적어주는 설명이다.

### ApiKeys CRUD

- **유저정보는, `/ or auth관련(회원가입/로그인)`을 제외하고는 access_control에서 `request.state.user`에서 어차피 따오므로, /users/apikeys/로 이어지는 url을
  쓴다.**
- api > v1 > user.py에서 작업한다.

#### Create - reqeust

1. Create시, 필요한 정보는 `user` from `request` 외에 `user_memo`이다. ApiKeyRequest의 schema를 정의한다.
    - 없을 수도 있어서 Optional
    - **`Create`의 `Request`가 SChema가 제일적을 것이기 때문에 `먼저 정의`하고 -> `Create Response`를 정의한다.**
    - user_memo는 없을 수 있다.
    ```python
    class ApiKeyRequest(BaseModel):
        user_memo: Optional[str] = None
    
        class Config:
            from_attributes = True
    ```
    - **이 떄, 2.0버전에서 권장하는 ConfigDict를 사용해서 오류나 워닝을 방지하도록 변경한다.**
    - 일본 참고페이지: https://zenn.dev/tk_resilie/articles/fastapi0100_pydanticv2

##### pydantic v2.0 공부

1. (필수) BaseSettings가 다른 패키지의 pydantic-settings가되었습니다.
    ```python
    from pydantic import BaseSettings
    
    from pydantic_settings import BaseSettings
    ```
2. (필수) 기본값이 None이면 =None 지정이 필수입니다.
    - V1에서 = None을 지정하지 않고 값이 지정되지 않은 경우 암시 적으로 None이 설정되었지만 Python 표준 사양에 맞게 검토되고 기본값이 None이면 = None 지정이 필수가 되었습니다.

    ```python
    class TodoResponse(BaseModel):
        id: str
        title: str
        created_at: datetime.datetime
        updated_at: datetime.datetime | None  # =Noneなしでも、値未指定ならNoneとみなされた
    
    
    #V2
    
    class TodoResponse(BaseModel):
        id: str
        title: str
        created_at: datetime.datetime
        updated_at: datetime.datetime | None = None  # =Noneがない場合は、値の指定が必須になった
    ```

3. (필수) validator의 이름 변경
    - validator의 함수명이 변경되어
    - validator -> field_validator
    - root_validator -> model_validator
    - 와 같이, 보다 명확한 인상이 되었습니다.
    - 또한 V1의 pre=True는 mode='before'로 변경되었습니다.
    - mode는 'before' 이외에 'after'도 지정 가능하며, pydantic에서 타입 체크 전에 validate했을 경우는 before를 지정합니다

    ```python
    
    from pydantic import BaseModel, validator, root_validator
    
    
    class User(BaseModel):
        name: str
    
        @validator('name', pre=True)  # <-
        def validate_name(cls, v):
            return v
    
        @root_validator(pre=True)  # <-
        def validate_root(cls, values):
            return values
    
    
    # V2
    
    from pydantic import BaseModel, field_validator, model_validator
    
    
    class User(BaseModel):
        name: str
    
        @field_validator('name', mode='before')  # <-
        def validate_name(cls, v):
            return v
    
        @model_validator(mode='before')  # <-
        def validate_root(cls, values):
            return values
    ``` 

4. (추가 기능) validator와는 별도로 serializer가 추가되어 json화 될 때의 변환 처리를 정의 할 수있게되었다

   - 종래는 Pydantic의  모델 작성시도, 직렬화시도 같은 validator로 처리되고 있었습니다만, v2로부터는  구별 가능하게 되었습니다.
   - field_serializer
   - model_serializer

5. (권장) class Config 대신 model_config = ConfigDict () 사용
    - 기존의 Config 클래스에서는, 에디터에서의 보완이나 Mypy 체크가 효과가 없고, 잘못되어도 에러가 되지 않는 문제가 있었습니다만 v2에서는 ConfigDict()를 사용하는 것으로, 이 문제가
      해소되었습니다

    ```python
    
    class TodoResponse(BaseModel):
        id: str
    
        class Config:
            ...　  # 設定を記述
    
            # V2
    
            from pydantic import ConfigDict
    
            class TodoResponse(TodoBasBaseModele):
                id: str
    
                model_config = ConfigDict(...)  # 設定を記述
    ```

6. (권장) to_camel 표준 설치 및 allow_population_by_field_name이 populate_by_name으로 변경되었습니다.
    - JSON 시리얼라이즈시의 캬멜 케이스 변환은 V1에서는 외부 라이브러리의 추가가 필요했지만, V2에서는 Pydantic에 표준 탑재되었습니다.
    - 또한 config에서 지정하는 설정의 이름이 allow_population_by_field_name에서 populate_by_name으로 변경되었습니다.
    - 이하에서는 실용예로서, alias_generator와 세트로 사용하는 것으로, 뱀 케이스, 낙타 케이스를 자동적으로 상호 변환하고 있습니다.

    ```python
    
    # V2
    
    from pydantic import BaseModel, ConfigDict
    from pydantic.alias_generators import to_camel  # pydanticに標準搭載された
    
    
    class BaseSchema(BaseModel):
    
    
        """全体共通の情報をセットするBaseSchema"""
    
    # class Configで指定した場合に引数チェックがされないため、ConfigDictを推奨
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,  # V1: allow_population_by_field_name=True
    )
    ```

7. (권장) from_orm이 더 이상 사용되지 않으며 model_validate가 새로 설치되었습니다.
    - V1에서는 ORM 인스턴스에서 Pydantic 인스턴스를 만들 때 orm_mode=True를 설정하고 from_orm으로 처리했지만 V2에서는 from_attributes=True를 설정하고
      model_validate로 처리하도록 변경되었습니다
    - from_orm도 현재는 종래대로 동작합니다.
    ```python
    
    # V2
    
    class TodoResponse(TodoBase):
        id: str
        tags: list[TagResponse] | None = []
        created_at: datetime.datetime | None = None
        updated_at: datetime.datetime | None = None
        
            model_config = ConfigDict(from_attributes=True) # V1: from_mode=True
    
    # ormインスタンスからpydanticインスタンスを生成
    
    TodoResponse.model_validate(orm_obj) # V1: TodoResponse.from_orm(orm_obj)
    ```
8. (권장) dict ()가 더 이상 사용되지 않고 model_dump가 새로 추가되었습니다.
    - dict화하는 처리는 model_dump()가 신설되어 있습니다.
    ```python
    
    # V2
    
    class TodoResponse(TodoBase):
        id: str
        tags: list[TagResponse] | None = []
        created_at: datetime.datetime | None = None
        updated_at: datetime.datetime | None = None
    
        model_config = ConfigDict(from_attributes=True)　# V1: from_mode=True
    
    # ormインスタンスからpydanticインスタンスを生成
    data = TodoResponse.model_validate(orm_obj)
    data.model_dump() # dict化される
    ```
9. (새 기능) computed_field
    - 필드끼리의 계산에 의해 세트 되는 필드는 computed_field 로 정의할 수 있습니다.
    - V1에서는 root_validator 등으로 구현하는 경우가 많았습니다만, 보다 알기 쉬운 기능으로서 독립한 형태입니다.
    ```python
    
    # V2🆕
    
    from pydantic import BaseModel, computed_field
    
    
    class Rectangle(BaseModel):
        width: int
        length: int
    
        @computed_field
        @property
        def area(self) -> int:
            return self.width * self.length
    
    
    print(Rectangle(width=3, length=2).model_dump())
    #> {'width': 3, 'length': 2, 'area': 6}
    ```
10. (권장) strict = True를 지정하면 더 엄격하게 유형을 확인할 수 있습니다.
    - strict=True 를 지정하면, str -> int 의 암묵적인 변환이 에러가 되는 등, 엄밀한 체크를 실시할 수 있습니다.

    ```python
    
    # V2
    
    class BaseSchema(BaseModel):
        """全体共通の情報をセットするBaseSchema"""
    
        model_config = ConfigDict(
          strict=True
        )
    ```

11. (권장) __fields__가 더 이상 사용되지 않고 model_fields가 새로 추가되었습니다.
    - 필드 정보를 얻으려면 model_fields를 사용합니다.
    - 다음 예제에서는 필드 이름을 나열합니다.
    ```python
    
    # V1
    
    list(TodoResponse.__fields__.keys())
    
    # V2
    
    list(TodoResponse.model_fields.keys())
    ```
#### 다시 back

2. create router에서 **생성하기 전에 `user별 api key를 가질 수 있는 최대 갯수 : 3(상수 정의필요)`를 체크해야한다.**
    ```python
    @router.post('/apikeys', status_code=201)
    async def create_api_key(request: Request, api_key_request: ApiKeyRequest, session: AsyncSession = Depends(db.session)):
        """
        API KEY 생성
        :param request:
        :param api_key_request:
        :param session:
        :return:
        """
        # api max count 확인
        user = request.state.user
    
        user_api_key_count = ApiKeys.filter_by(session=session, user_id=user.id, status='active').count()
        print(user_api_key_count)
        if user_api_key_count >= MAX_API_KEY_COUNT:
            raise MaxKeyCountException()
        
        return user_api_key_count
    ```
    ```python
    # consts.py
    
    # API KEY
    MAX_API_KEY_COUNT = 3
    ```
    - api가 넘었는데 생성요청은 400 BadRequest하위클래스 예외로 만들어준다.
    ```python
    class MaxAPIKeyCountException(BadRequestException):
        def __init__(self, exception: Exception = None):
            super().__init__(
                code_number=6,
                detail=f"API 키 생성은 {MAX_API_KEY_COUNT}개 까지 가능합니다.",
                exception=exception,
            )
    ```
    - swagger에서 로그인 후, 테스트를 해서 count가 제대로 찍히는지 확인한다.
        - **ApiKey 전용으로서 classmethod로 따로 추출해서 사용되도록 한다**
    ```python
    
    # api max count 확인
    await ApiKeys.check_max_count(user, session=session)
    
    class ApiKeys(BaseModel):
        # ... 
        @classmethod
        async def check_max_count(cls, user, session=None):
            user_api_key_count = await cls.filter_by(session=session, user_id=user.id, status='active').count()
            if user_api_key_count >= MAX_API_KEY_COUNT:
                raise MaxAPIKeyCountException()
    
    ```
3. count가 3개 미만인 상태면 통과되어어서, request -> user -> `user.id` 외에 **`access_key`, `secret_key`를 직접 만들어서 들고간다.**
    - secret_key(랜덤40글자) 생성 by alnums + random
    - access_key( uuid4 끝 12개 + uuid4 전체)로 생성 후, db에서 exists로 존재하지 않을때까지 무한반복 후 -> db에 없는 key일 때 통과
    - **access_key는 유일해야하므로 `unique 칼럼으로 정의하면 좋겠지만, 유지보수에 힘들어진다. 직접 코드나 함수로 존재안함을 확인후  생성`한다.**
    ```python
    @router.post('/apikeys', status_code=201)
    async def create_api_key(request: Request, api_key_request: ApiKeyRequest, session: AsyncSession = Depends(db.session)):
        """
        API KEY 생성
        :param request:
        :param api_key_request:
        :param session:
        :return:
        """
        user = request.state.user
    
        # api max count 확인
        user_api_key_count = await ApiKeys.filter_by(session=session, user_id=user.id, status='active').count()
        # print(user_api_key_count)
        if user_api_key_count >= MAX_API_KEY_COUNT:
            raise MaxAPIKeyCountException()
    
        # secret_key(랜덤40글자) 생성 by alnums + random
        # ex> ''.join(random.choice(alnums) for _ in range(40)) -> 'JYx5Ww7h7l6q8cPut1ODLgCoVaqVz3R8owExnsLO'
        alnums = string.ascii_letters + string.digits
        secret_key = ''.join(random.choices(alnums, k=40))
    
        # access_key( uuid4 끝 12개 + uuid4 전체)
        # ex> f"{str(uuid4())[:-12]}{str(uuid4())}" -> 'b485bb0e-d5eb-4e09-8076-e170bf05-935d-431f-a0ec-21d5b084db6f'
        # => 빈값(None) 가변변수로 채워질 때까지(while not 가변변수)로 무한반복, 조건만족시 가변변수 채우기
        access_key = None
        while not access_key:
            access_key_candidate = f"{str(uuid4())[:-12]}{str(uuid4())}"
            exists_api_key = await ApiKeys.filter_by(session=session, access_key=access_key_candidate).exists()
            if not exists_api_key:
                access_key = access_key_candidate
    
        return secret_key, access_key
    ```
4. **request 정보(user_memo)의 `Schema객체`를 `.model_dump()`로 dict로 변환하여 `create에 **dict로 keywrod입력되게 한다.`**
    ```python
    @router.post('/apikeys', status_code=201)
    async def create_api_key(request: Request, api_key_request: ApiKeyRequest, session: AsyncSession = Depends(db.session)):
        #....
    
        # request schema정보를 -> .model_dump()로 dict로 변환하여 **를 통해 키워드로 입력하여 create한다.
        additional_info = api_key_request.model_dump()
        
        return additional_info
    ```

5. **이제 request에서 뽑은 one에 대한 fk인 `user.id`와 `key 2개`, `request schema정보 -> dict변환후 **dicy로 keyword입력`시켜 create한다**
    ```python
    @router.post('/apikeys', status_code=201)
    async def create_api_key(request: Request, api_key_request: ApiKeyRequest, session: AsyncSession = Depends(db.session)):
        #...
    
        additional_info = api_key_request.model_dump()
    
        new_api_key = await ApiKeys.create(session=session, auto_commit=True,
                                           user_id=user.id,
                                           secret_key=secret_key,
                                           access_key=access_key,
                                           **additional_info)
        return "ok"
    ```
   

#### create response Schema

1. **create `response` schema부터는 `Config설정 및 및 request로 들어왔던 필요정보 user_memo`를 포함해야하기 때문에 상속해서 정의한다**
    - user_memo(optional)을 포함한, 객체로부터 오는 id, access_key, created_at은 필수정보라 옵션을 안준다.
    ```python
    class ApiKeyRequest(BaseModel):
        model_config = ConfigDict(from_attributes=True)
    
        user_memo: Optional[str] = None
    
    
    class ApiKeyResponse(ApiKeyRequest):
        id: int
        access_key: str
        created_at: datetime
    ```

2. router에 reponse_model로 schema를 지정한 뒤, return에서는 해당 orm객체를 반환하면 된다.
    ```python
    @router.post('/apikeys', status_code=201, response_model=ApiKeyResponse)
    
    async def create_api_key(request: Request, api_key_request: ApiKeyRequest, session: AsyncSession = Depends(db.session)):
        #...
        new_api_key = await ApiKeys.create(session=session, auto_commit=True,
                                           user_id=user.id,
                                           secret_key=secret_key,
                                           access_key=access_key,
                                           **additional_info)
        return new_api_key
    ```

3. **이 때, `Create시 (첫 api생성)시에만 secret_key를 포함`시켜줘야한다.**
    - **따로 First를 붙인 Schema를 만들어서, create(post) router에서 사용하도록 한다.**
```python
class ApiKeyFirstTimeResponse(ApiKeyResponse):
    secret_key: str


@router.post('/apikeys', status_code=201, response_model=ApiKeyFirstTimeResponse)
#...
```
- **users/apikeys로서, `1명의 유저당 여러개의 apikey가 반환`되어야하므로, `1개의 apikey response`만 일단 정의해놓고, 사용시 `List[]`로 지정해준다**

4. create가 완료되었으므로, `super().create()`를 내부에서 이용한 create overide를 한다.
    - 이 때, request schema -> model_dump()로 dict한 것을 인자로 넘기기 위해, 위쪽으로 뺀 뒤, 메서드화 해서 넘긴다.
    - **super().create()는 BaseModel의 Mixin에서 정의해준 create가 올 것이기 때문에, `기존 ApiKeys.create()를 super().create()로 바꿔준다.`**
### read
1. user에 달린 apikeys는 request schema가 없이, request에서 user정보만 추출해서 처리하면 된다. 대신 **Response Schema를 `List[]`에 넣어서 list로 반환되어야한다**
2. 

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

- 참고
    - 이동: git clone 프로젝트 커밋id 복사 -> `git reset --hard [커밋id]`
    - 복구: `git reflog` -> 돌리고 싶은 HEAD@{ n } 복사 -> `git reset --hard [HEAD복사부분]`