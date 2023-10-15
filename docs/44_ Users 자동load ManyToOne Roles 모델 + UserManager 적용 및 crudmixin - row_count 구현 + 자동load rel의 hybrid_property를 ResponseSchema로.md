### Roles 모델 생성 (Enum3개 미리 필요)

- Role 생성은 예전 프로젝트를 참고한다: https://github.dev/is2js/2022_sqlalchemy
- fastapi-users를 사용한 프로젝트를
  참고한다: https://github.dev/mixa2130/events_registration_api/commit/788776309efb8e462cbaca70863a78c5dfc62d4d

### Role model 생성용으로 쓰일 Enum 2개 - Permissions, RolePermissions
#### Permissions
1. Permissions는, 가장 상위 숫자를 나머지들의 합으로 이길 수 없게 끔 0부터 2의 n승으로 시작하게 한다.
    - **이 때, NONE = 0은 sqlalchemy execute상황에서 outerjoin시 빈 것을 대체하기 위해 필요했었다.**
    ```python
    class Permissions(int, Enum):
        NONE = 0  # execute상황에서 outerjoin 조인으로 들어왔을 때, 해당 칼럼에 None이 찍히는데, -> 0을 내부반환하고, 그것을 표시할 DEFAULT NONE 상수를 필수로 써야한다.
        FOLLOW = 2 ** 0  # 1
        COMMENT = 2 ** 1  # 2
        WRITE = 2 ** 2  # 4 : USER == PATIENT
        CLEAN = 2 ** 3  # 8
        RESERVATION = 2 ** 4  # 16 : STAFF, DOCTOR
        ATTENDANCE = 2 ** 5  # 32 : CHEIFSTAFF
        EMPLOYEE = 2 ** 6  # 64 : EXECUTIE
        ADMIN = 2 ** 7  # 128 : ADMIN <Permission.ADMIN: 128>
    ```
   
#### RolePermissions: 변수명은 RoleName( enum_value )로 들어갈 예정 -> 소문자로
1. **RolePermissions는 `list value`를 가지는 Enum이다.**
    - permission enum들을 list로 가지고 있다가, **Role 모델을 생성할 때, 해당 `RolePermissions`들을 순회하며 -> 내부 permission list들을
      합한 `int가 실제 db value`로 들어갈 것이다.**
    - **RoleType을 입력받아 -> permission list 을 합산하여 -> permission필드로 입력하게 되면, `입력된 permissio값만 서로 비교`할 수 있다.**
    - **추가로 RoleType마다 max permission을 뽑는 property도 하나 정의해준다.**
    ```python
    class RolePermissions(list, Enum):
        # 각 요소들이 결국엔 int이므로, deepcopy는 생각안해도 된다?
        # 미리 int들을 안더하는 이유는, Roles DB 생성시, RoleType속 permission들을 순회 -> int칼럼에 누적
    
        user: list = [Permissions.FOLLOW, Permissions.COMMENT, Permissions.WRITE]
        staff: list = user + [Permissions.CLEAN, Permissions.RESERVATION]
        doctor: list = list(staff)  # 주소겹치므로 list()로 swallow copy
        chiefstaff: list = doctor + [Permissions.ATTENDANCE]
        executive: list = list(chiefstaff) + [Permissions.ATTENDANCE, Permissions.EMPLOYEE]
        administrator: list = list(executive) + [Permissions.ADMIN]
    
        @property
        def max_permission(self):
            """
            RolePermission.DOCTOR.max_permission
            # 16
            """
            max_permission_enum = self.value[-1]
            return max_permission_enum.value 
    ```
    - **여기서 변수명을 `대문자`가 아닌 `소문자`로 사용한 이유는, RolePermission를 `RolePermissions.__members__.items()`로 순회하면서 나오는 `변수명_str`을 이용해서 
         - `RoleName( str_소문자_value) Enum`객체를 생성할 때, value -> 소문자로 필요로 한다.**
    ```python
    class Roles(BaseModel):
    
        @classmethod
        async def insert_roles(cls, session: AsyncSession = None):
            """
            app 구동시, 미리 DB 삽입 하는 메서드
            """
            for name_str, role_permissions in RolePermissions.__members__.items():
                # name_str: USER - <class 'str'> / role_enum:  RoleType.USER - <enum 'RoleType'>
                role_name = RoleName(name_str)
    ```
    - **`max_permission`은 추후 User가 가진 permission값과, 특정RolePermissions를 비교할 때 쓰일 예정.**
    ```python
    # refactor
    @hybrid_method
    def is_(cls, role_permissions: RolePermissions, mapper=None):
        mapper = mapper or cls
    
        return mapper.total_permission >= role_permissions.max_permission
    ```

#### Roles model의 Enum필드에 쓰일 Enum : RoleName

1. RolePermissions의 순회마녀서, str변수명 -> RoleName의 value와 일치할 때, RoleName( value )으로 Enum객체를 생성할 수 있다. 
    - **이 때, front에서는 `소문자 role_name_str`이 넘어올 것이므로, 소문자로 value를 잡아준다.**
    ```python
    class RoleName(str, Enum):
        USER: str = 'user'
        STAFF: str = 'staff'
        DOCTOR: str = 'doctor'
        CHIEFSTAFF: str = 'chiefstaff'
        EXECUTIVE: str = 'executive'
        ADMINISTRATOR: str = 'administrator'
    ```

### Roles model 만들기


1. id 등은 BaseModel에 있으니, `name` enum필드(RoleName) / **`default` : default role여부**를 필드로 생성해준다.
    - role name으로 검색하므로 `unique=True`로 주고 / role 데이터 중에 default 인 것을 User생성시 기본입력 등으로 할 것 같으니 `index=True`까지 옵션을 준다.
    - **permission은 int며 `default=0`로 주고, 생성메서드에서는 RolePermissions를 순회하며 합친 int를 누적해서 더해서 최종 생성된다.**
    ```python
    class Roles(BaseModel):
        name = Column(Enum(RoleName), default=RoleName.USER, unique=True, index=True)
        default = Column(Boolean, default=False, index=True)
        permissions = Column(Integer, default=0)
    ```
   
### Roles Model은 user객체에서 바로 꺼내 쓸 수 있도록, lazy='joined'(many) or lazy='subquery' (one) 로 relation을 정의한다.
#### Users에 새로운 one모델의 fk/relation 정의하기
1. 보통의 one모델은(Users-ApiKeys)는 **`fk`옵션에 one에 주는 정보로서`ondelete='CASCADE'`를 달아주지만, Role 삭제될일도 없고 별개의 domain으로 취급하여 안준다.**
2. **user에서 바로 꺼내볼 one relationship 모델은**
    - **one에서 쓸 일 이 있으면, back_populates=를 주고**
    - **필수로 foreign_keys=[] 옵션에 fk키를 주입하고**
    - **필수로 one으로서 use_list=False를 주고**
    - **매번 확인해야하면 lazy='subquery'를 준다.**
        - 만약, many가 대상이면 lazy='joined'  
    ```python
    class Users(BaseModel, SQLAlchemyBaseUserTable[int]):
    
        # 1. many에 fk를 CASCADE or 안주고 달아준다.
        # role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
        role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
        
        # 2. many.one 을 단수로 쓰기 위해 uselist=false로 relation을 생성한다.
        # 3. lazy 전략 선택
        # => 추가쿼리를 날리기위한 Query객체 반환 dynamic(안씀) VS eagerload용 default 'select' VS 자동load용 'subquery', 'selectin', 'joined'
        # => 자동load시 대상이 1) many-> 'joined', 2) one -> 'subquery' or 'selectin' 선택
        role = relationship("Roles",  # back_populates="user",
                            foreign_keys=[role_id],
                            uselist=False,
                            lazy='subquery',  # lazy: _LazyLoadArgumentType = "select",
                            )
    ```
   
#### 바로 꺼내 쓸 one relationship 정보는 미리 @hybrid_property로 정의해놓자.
1. **lazy='subquery' 되어 자동 load되는` Roles객체의 name`(Enum-RoleName)을,  `User Response Schema (UserRead)`에서 Roles-name필드 type(RoleName)으로 정의할 수 있게 된다.**
    ```python
    class Users(BaseModel, SQLAlchemyBaseUserTable[int]):
    
        @hybrid_property
        def role_name(self) -> RoleName:
            """
            lazy='subquery' 되어 자동 load되는 Roles객체의 name(Enum-RoleName)을 바로 조회하여
            -> User Response Schema (UserRead)에 Roles-name필드 type(RoleName)으로 정의할 수 있게 된다.
            """
            return self.role.name
    ```
### Roles DB데이터 생성: 애초에 db데이터로 만들어놓고 CRUD하지 않는다.

#### classmethod로 init_script에 작동할 Roles.insert_roles() 메서드 만들기

1. `RolePermissions` enum을
    - `그냥 순회` -> 내부enum객체들 뿐만 아니라
    - **`.__members__.items()`로 순회 -> `변수명(str)`, `내부enum객체(.name/.value)`를 tuple로 순회하여, 해당 str name과 똑같은 RoleName을 뽑을 수
      있게 순회한다.**
    ```python
    @classmethod
    async def insert_roles(cls, session: AsyncSession = None):
        for name_str, role_permissions in RolePermissions.__members__.items():
            # name_str: USER - <class 'str'> / role_enum:  RoleType.USER - <enum 'RoleType'>
            ...
    ```

2. str변수명을 `EnumClass( str변수명 )`로 생성자에 넣으면, 해당 enum객체를 뽑아쓸 수 있어서, **`RoleName( str변수명 )`의 개별 enum객체도 뽑아낸다.**
    ```python
    @classmethod
    async def insert_roles(cls, session: AsyncSession = None):
        for name_str, role_permissions in RolePermissions.__members__.items():
            # name_str: USER - <class 'str'> / role_enum:  RoleType.USER - <enum 'RoleType'>
            
            role_name = RoleName(name_str)
            # RoleName('USER') -> <RoleName.USER: 'USER'>
    ```

3. cls.filter_by(name=)으로 RoleName객체를 exists로 조회하여, 이미 있다면 생성에서 제외 continue시키고
    - **없다면, cls.create()로 해당 객체를 생성한다. 이 때, `auto_commit=True`를 주지않고, permission 기본값0에서 업뎃가능한 세션객체 상태를 만들어준다.**
    ```python
    @classmethod
    async def insert_roles(cls, session: AsyncSession = None):
        for name_str, role_permissions in RolePermissions.__members__.items():
            # name_str: user - <class 'str'> / role_enum:  RoleType.user - <enum 'RoleType'>
            
            role_name = RoleName(name_str)
            # RoleName('user') -> <RoleName.USER: 'user'>
            
            if await cls.filter_by(name=role_name).exists():
                continue
    
            target_role = await cls.create(session=session, name=role_name)  # default total_permission = 0
    ```

#### 일단 commit없이 create한 session가진 Roles객체를 한번에 .update/.fill이 아닌, 순차적으로 [조건확인 후] permission 누적 후 .save(auto_commit)

1. 이제 target_role객체에 `role_permissions` enum의 .value로 list를 가져와서, 순차적으로 확인후 add한다.
    - **이 때, 자신이 가진 permission 수치보다 작은 permission값이 들어오면 pass하는 `has_permission`을 구현하여 add한다.**
        - 기존까지 쌓인 permissio보다 작은 permission(int)이 들어오면, 누적해서 안쌓이도록 pass한다
    ```python
        def _has_permission(self, permission):
            # self.perm == perm의 확인은, (중복int를 가지는 Perm도 생성가능하다고 생각할 수 있다)
            return self.permission >= permission
    
        def _add_permission(self, permission):
            # 6) 해당 perm(같은int)을 안가지고 잇을때만 추가한다다
            if not self.has_permission(permission):
                self.permission += permission
    ```
    ```python
    for permission in role_permissions.value:
        target_role._add_permission(permission)
    ```
   
2. 마지막으로 Roles의 default=False 칼럼을 `default RoleName인 RoleName.User와 같은지 비교한 조건식`을 대입하여 삽입한 뒤,
    - **ssession살아있는 객체.save(auto_commit=True)로 처리한다.**
    ```python
    class Roles(BaseModel):
        name = Column(Enum(RoleName), default=RoleName.USER, unique=True, index=True)
        default = Column(Boolean, default=False, index=True)
        permission = Column(Integer, default=0)
    
        @classmethod
        async def insert_roles(cls, session: AsyncSession = None):
            for name_str, role_permissions in RolePermissions.__members__.items():
                # name_str: user - <class 'str'> / role_enum:  RoleType.user - <enum 'RoleType'>
    
                role_name = RoleName(name_str)
                # RoleName('user') -> <RoleName.USER: 'user'>
    
                if await cls.filter_by(name=role_name).exists():
                    continue
    
                target_role = await cls.create(session=session, name=role_name)  # default total_permission = 0
    
                # 4) 해당role_name에 해당하는 int permission들을 순회하면서 필드에 int값을 누적시킨다
                for permission in role_permissions.value:
                    target_role._add_permission(permission)
    
                # 7) 해당role에 default role인 User가 맞는지 확인하여 필드에 넣어준다.
                target_role.default = (target_role.name == RoleName.USER)
    
                # session이 끊기지 않은 모댈객체는 update or fill 없이, 직접 변형 후, save 때릴 수 있다.
                await target_role.save(auto_commit=True)
    ```
### Roles의 생성은 init_script로서 이미 db에 삽입되어야한다.
#### 데이터가 1개라도 존재하는 검사를 위한 .count()을 row_counts() @classmethod로 구현 in crudmixin
- **실행메서드 count()와 이름이 겹치면, create_obj이후 obj.count()실행메서드를 쓸 때 무한 반복되어버림**
- row_count라는 이름을 짓고, classmethod만 작동하도록 `@class_or_instance_method`을 사용한다
- `@row_count.instancemethod`에서는 메서드이름을 `self.__class__`로, cls까지 접근한 뒤, `.함수.__name__`으로 에러를 뿌려준다.
    ```python
    # app/models/mixins/crud_mixin.py
    @class_or_instance_method
    async def row_count(cls, session: AsyncSession = None, **kwargs):
        """
        데이터 1개라도 존재여부 확인을 위해 구현
        -> if await Roles.row_count()
        """
        obj = await cls.create_obj(session=session, where=kwargs)
        # query= 키워드를 안넣어줬다면, 내부 set_query에서 self._query = select(self.__class__) 입력됨.
    
        # 실행메서드는 외부session없으면 이미 session발급된 obj에서 self.session으로수행
        count_ = await obj.count(session=session)
    
        return count_
    
    @row_count.instancemethod
    async def row_count(self, session: AsyncSession = None):
        raise NotImplementedError(f'객체 상태에서 {self.__class__.row_count.__name__} 메서드를 호출 할 수 없습니다.')
    ```
#### start_up에 등록
1. Roles가 데이터가 없으면, startup에서 생성해준다.
    - 조회할 때, `mixin 실행메서드`는 객체 생성상태에서만 가능하기 때문에, filter_by조건으로 `항상 있어야하는 id가 None`으로 검색하여,  
    ```python
    class SQLAlchemy(metaclass=SingletonMetaClass):
        def init_app(self, app: FastAPI):
    
            @app.on_event("startup")
            async def start_up():
                # 테이블 생성 추가
                async with self.engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
                    logging.info("DB create_all.")
    
                # 초기 모델 -> 없으면 생성
                from app.models import Roles
                if not await Roles.row_count():
                    await Roles.insert_roles()
    ```
   
### UserManager에 create/oauth_callback 내부에 들어오는 user_dict에서 강제로 default fk값 던져주기
- **`create`메서드는 email기반 회원가입시 사용되는데, 이 때, `UserCreate Schema로 부터 user_dict가 완성`되서 들어온다.**
- **하지만 OAuth 로그인할 때 `가입안된 회원이면, 먼저 user부터 만들면서 작동`하는 `oauth_callback`에서는 `자체적으로 간소한 user_dict를 내부에서 생성`하여, user를 생성한다.**
    - **2가지 로직에 모두 `role_id라는 fk`를 채워줘야한다.**
#### 방법1. UserManager의 creaet 뿐만 아니라, oauth_callback에서 등장하는 user_dict에 default role_fk를 넣어주기

```python
    async def create(self, user_create: schemas.UC, safe: bool = False, request: Optional[Request] = None) -> models.UP:

        #### 가입시 추가필드 입력 ####
        # default_role = await Roles.filter_by(default=True).first()
        # print(f"default_role >> {default_role}")

        user_dict["role_id"] = 1
        ############################
        #...
        
    async def oauth_callback(self: "BaseUserManager[models.UOAP, models.ID]", oauth_name: str, access_token: str,
                             account_id: str, account_email: str, expires_at: Optional[int] = None,
                             refresh_token: Optional[str] = None, request: Optional[Request] = None, *,
                             associate_by_email: bool = False, is_verified_by_default: bool = False) -> models.UOAP:

                user_dict = {
                    "email": account_email,
                    "hashed_password": self.password_helper.hash(password),
                    "is_verified": is_verified_by_default,
                }

                #### 추가 필드 처리 ####
                user_dict["role_id"] = 1
                ######################

                user = await self.user_db.create(user_dict)
                user = await self.user_db.add_oauth_account(user, oauth_account_dict)
                await self.on_after_register(user, request)
            
```
- 해당하는 부분만 보면

```python
user_dict = (
    user_create.create_update_dict()
    if safe
    else user_create.create_update_dict_superuser()
)
password = user_dict.pop("password")
user_dict["hashed_password"] = self.password_helper.hash(password)
```
```python
user_dict = {
    "email": account_email,
    "hashed_password": self.password_helper.hash(password),
    "is_verified": is_verified_by_default,
}

#### 추가 필드 처리 ####
user_dict["role_id"] = 1

user = await self.user_db.create(user_dict)
user = await self.user_db.add_oauth_account(user, oauth_account_dict)
await self.on_after_register(user, request)
```
### user_dict를 만드는 UserCreate에 검색용 unique칼럼인 name을 추가해서 -> 내부 user_dict에 `role_name`이 꼽히도록 Schema 재정의


1. UserCreate에는, 이미정해진 Roles의 unique 칼럼인 RoleName(정해진 종류 - Enum)을 string(value)로 받아 자동 변환시킨다.
    - **Request Schema에서, `type을 : Enum`으로 해주면 -> `front의 enum_value("user")입력`을 -> route에서는 `Enum객체`로 자동 변환해준다.**
    ```python
    class UserCreate(BaseUserCreate):
        # model_config = ConfigDict(use_enum_values=True, )
        sns_type: Optional[SnsType] = "email"
        
        # Request 에서 type을 : Enum으로 해주면 -> front의 enum_value("user")입력을 -> Enum객체로 자동변환해준다.
        # : front "user" 입력 -> RoleName.USER 자동변환
        role_name: Optional[RoleName] = None 
    ```
3. UserManager create 메서드 / oauth_callback 내부 Cerate Account에서는 **`role_id`을 직접 꽂는 대신 `role_name` -> Roles객체를 찾아서 넣어준다.**
    - user_dict 속 `role_name` -> pop -> `Roles 모델 조회`한 것을 Users 데이터 생성에 `role= Roles객체`가 들어가도록 조회해서 넣어준다.
    - **hybrid_property -> setter로 만들어봤지만, `sqlalchemy setter는 객체.setter = 값`만 허용하고 생성자로 들어갈 dict 속 role_name은 필드가 아니라서 허용안했다.**
    - **user_dict속 `role_name`은 Optional이므로, `.pop`으로 꺼내돼 기본값 `None`으로 없으면 None으로 판단하고 기본Role을 넣어줄 준비를 한다.**
    ```python
    class UserManager(IntegerIDMixin, BaseUserManager[Users, int]):
    
        async def create(self, user_create: schemas.UC, safe: bool = False, request: Optional[Request] = None) -> models.UP:
    
            #### 가입시 추가필드 입력 ####
            role_name: RoleName = user_dict.pop("role_name", None)
            if not role_name:
                user_dict["role"] = await Roles.filter_by(default=True).first()
            else:
                user_dict["role"] = await Roles.filter_by(name=role_name).first()
            ############################
            created_user = await self.user_db.create(user_dict)
    
    ```
#### oauth_callback에서 Create Account할때는 role_name을 받는게 아니라, 기본값 Role객체를 만들어 넣어준다.
```python
async def oauth_callback(self: "BaseUserManager[models.UOAP, models.ID]", oauth_name: str, access_token: str,
                         account_id: str, account_email: str, expires_at: Optional[int] = None,
                         refresh_token: Optional[str] = None, request: Optional[Request] = None, *,
                         associate_by_email: bool = False, is_verified_by_default: bool = False) -> models.UOAP:

    try:

        user = await self.get_by_oauth_account(oauth_name, account_id)

    except exceptions.UserNotExists:

            user_dict = {
                "email": account_email,
                "hashed_password": self.password_helper.hash(password),
                "is_verified": is_verified_by_default,
            }

            #### 추가 필드 처리 ####
            # user_dict["role_id"] = 1
            user_dict["role"] = await Roles.filter_by(default=True).first()
            ######################
            user = await self.user_db.create(user_dict)
```

### Users 생성후, Response Schema인 UserRead에 relationship을 추가해서 확인
1. UserCreate로 들어온 뒤, Users가 role을 추가해서 create되고, 그 반환데이터는 `UserRead` Response Schema를 통해 반환되는데
    - **relationship인 `Roles`모델을 내포dict로 반환하려면, `Sqlalchemy model을 response하는 Schema옵션`을 이용해서 해당SChema를 추가해줘야한다.**
2. **relationship Roles객체를 반하는 `RolesResponse` Schema를 만들고, 이제 생성시 필수이니 필수 field로 필드Type으로 정해서 반환한다.**
    - **이 대, `from_attributes=True`를 넣어줘서, role relationship이 자동으로 `model -> schema`로 변환되게 해야한다.**
    - permission빼고 name만 적용되게 해보자.
    ```python
    class RolesResponse(BaseModel):
        #  Input should be a valid dictionary or instance of Role [type=model_type, input_value=<Roles#1>, input_type=Roles]
        model_config = ConfigDict(from_attributes=True)
        name: str
    ```
3. 이제 UserRead(Resopnse Schema)에 해당 **RolesResponse를 type으로 하는 모델 속 `role` relationship이 같이 반환**되게 한다.
    - UserRead는 이미 부모에서 from_attributes=True 설정이 되어있고, `role: 모델SchemaType`을 넣어주면 알아서 같이 반환된다.
    ```python
    class UserRead(BaseUser[int]):
    
        role: RolesResponse
        # "role": {
        #       "name": "USER"
        #     }
    ```

#### 자동load relationship 특권으로서, @hybrid_prorperty를 Schema에서 추출해서 가져갈 수 있다.
1. **자동load relationship에서 필요한 필드만 뽑아주는 `@hybrid_property`로 정의해놓고**
    ```python
    class Users(BaseModel, SQLAlchemyBaseUserTable[int]):
        #...
        @hybrid_property
        def role_name(self) -> RoleName:
            """
            lazy='subquery' 되어 자동 load되는 Roles객체의 name(Enum-RoleName)을 바로 조회하여
            -> User Response Schema (UserRead)에 Roles-name필드 type(RoleName)으로 정의할 수 있게 된다.
            """
            return self.role.name
    ```
   
2. **마치 Users모델의 field인냥 hybrid_property를 Schema에  rel의 필드를 type과 함께 명시해놓으면, `{}모델이 아닌 rel 특정필드만` 반환시킬 수 있다.**
    ```python
    class UserRead(BaseUser[int]):
    
        # role: RolesResponse
        # "role": {
        #       "name": "USER"
        #     }
    
        # 자동load relationship(role=, Roles)를
        # 1) @hybrid_property로 필요한 필드만 정의하고
        # 2) 모델의 Response Schema에 반환타입 함께 명시하면,
        # => relationship모델의 특정 필드만 반환시킬 수 있다.
        role_name: RoleName
        # "role_name": "user"
    ```
   

### create/read가 끝났으면, UserManager의 update도 재정의해서, UserUpdate Schema role_name input -> role객체를 relationship에 넣어줘야한다.
1. **user관련 route들 정의시 사용되는 UserUpdate (request) 스키마에 role_name을 넣어주고**
```python
class UserUpdate(BaseUserUpdate):
    #...
    role_name: Optional[RoleName] = None # 내부에서 기본값 넣어주는 처리 됨.

```
2. UserManager의 update메서드를 재정의하여 schema -> dict 속 role_name을 role객체로 만들어서 넣어준다. 
    - 업데이트는 있을 때만 처리하게 한다. 없어도 default값 배정X(생성시 이미 함)
```python
class UserManager(IntegerIDMixin, BaseUserManager[Users, int]):
    #...
    async def update(self, user_update: schemas.UU, user: models.UP, safe: bool = False,
                     request: Optional[Request] = None) -> models.UP:
        # return await super().update(user_update, user, safe, request)
        if safe:
            updated_user_data = user_update.create_update_dict()
        else:
            updated_user_data = user_update.create_update_dict_superuser()

        #### 추가 필드 처리 ####
        role_name: RoleName = updated_user_data.pop("role_name", None)

        if role_name:
            updated_user_data["role"] = await Roles.filter_by(name=role_name).first()
        ########################

        updated_user = await self._update(user, updated_user_data)

        await self.on_after_update(updated_user, updated_user_data, request)
        return updated_user
```

### 관리자메일을 환경변수에 받고, 가입email과 일치하면, role을 ADMINISTRATOR로 배정
1. dotenv 정의
    ```dotenv
    # admin user role
    ADMIN_EMAIL="tingstyle1@gmail.com"
    ```
2. config.py에 Config class에 기본으로 받아 정의
    - post_init에서 활용될게 아니므로 상수로 안받는다?
    ```python
    @dataclass
    class Config(metaclass=SingletonMetaClass):
        # admin user for role
        ADMIN_EMAIL = environ.get("ADMIN_EMAIL")
    ```
   
3. **create/oauth_callback의 dict에서 user_dict['email']과 비교하여 맞으면 무조건 role relationship에 Roles 중 관리자로 배정한다**
```python
class UserManager(IntegerIDMixin, BaseUserManager[Users, int]):

    async def create(self, user_create: schemas.UC, safe: bool = False, request: Optional[Request] = None) -> models.UP:

        #### 가입시 추가필드 입력 ####
        if user_dict['email'] == config.ADMIN_EMAIL:
            # 관리자 메일과 동일하면, 관리자 Role로 등록
            user_dict["role"] = await Roles.filter_by(name=RoleName.ADMINISTRATOR).first()
        else:
            role_name: RoleName = user_dict.pop("role_name", None)
            if not role_name:
                user_dict["role"] = await Roles.filter_by(default=True).first()
            else:
                user_dict["role"] = await Roles.filter_by(name=role_name).first()
        ############################
        
        
    async def oauth_callback(self: "BaseUserManager[models.UOAP, models.ID]", oauth_name: str, access_token: str,
                             account_id: str, account_email: str, expires_at: Optional[int] = None,
                             refresh_token: Optional[str] = None, request: Optional[Request] = None, *,
                             associate_by_email: bool = False, is_verified_by_default: bool = False) -> models.UOAP:
        """
        Users 생성시, role 추가를 위해 재정의(user_dict)
        """
        #### 추가 필드 처리 ####
        # 관리자 메일과 동일하면, 관리자 Role로 등록
        if user_dict['email'] == config.ADMIN_EMAIL:
            user_dict["role"] = await Roles.filter_by(name=RoleName.ADMINISTRATOR).first()

        # 아니라면, oauth로그인으로 인한 가입은 기본 Roles("user") 배정
        else:
            user_dict["role"] = await Roles.filter_by(default=True).first()
        ######################
```

### Role renewal 이후 -> permission_required / role_required
#### RolePermission를 set으로 변경
```python
class RolePermissions(set, Enum):

    user: set = {Permissions.FOLLOW, Permissions.COMMENT, Permissions.WRITE}
    staff: set = user.union({Permissions.CLEAN, Permissions.RESERVATION})
    doctor: set = set(staff)
    chiefstaff: set = doctor.union({Permissions.ATTENDANCE})
    executive: set = chiefstaff.union({Permissions.EMPLOYEE})
    administrator: set = executive.union({Permissions.ADMIN})
```
#### RoleName에서 value에 해당하는 RolePermissions를 getattr()로 가져온 뒤, 미리 sum과 max를 property로 수행
- **Max Permission을 구할 땐, `max( int enum set)`으로 돌릴 수 있지만, `응답시 외부로 int enum인 Permissions`를 내보낼 수 있게**
    - **`max( iter, key=)`를 통해 max의 기준을 `lambda x:x.value`로 하고 x인 enum으로 반환되게 하자.**
```python
class RoleName(str, Enum):
    USER: str = 'user'
    STAFF: str = 'staff'
    DOCTOR: str = 'doctor'
    CHIEFSTAFF: str = 'chiefstaff'
    EXECUTIVE: str = 'executive'
    ADMINISTRATOR: str = 'administrator'
    
    def get_role_permission_set(self) -> set:
        return getattr(RolePermissions, self.value)

    @property
    def total_permission(self):
        return sum(self.get_role_permission_set())
    
    @property
    def max_permission(self) -> Permissions:
        return max(self.get_role_permission_set(), key=lambda x: x.value)
```

#### Roles.insert_roles() 할 때, RolePermission가 아닌 RoleName을 순회해서 property를 이용하여 누적없이 바로 정의

```python
class Roles(BaseModel):
    name = Column(Enum(RoleName), default=RoleName.USER, unique=True, index=True)
    default = Column(Boolean, default=False, index=True)
    permission = Column(Integer, default=0)

    @classmethod
    async def insert_roles(cls, session: AsyncSession = None):
        """
        app 구동시, 미리 DB 삽입 하는 메서드
        """
        for role_name in RoleName:

            if await cls.filter_by(name=role_name).exists():
                continue

            await cls.create(
                session=session,
                auto_commit=True,
                name=role_name,
                permission=role_name.total_permission,
                default=(role_name == RoleName.USER)
            )
```

### decorator
#### 일단은 개별 Permissions를 @permission_required로 만든다
```python
class Permissions(int, Enum):
    NONE = 0  # execute상황에서 outerjoin 조인으로 들어왔을 때, 해당 칼럼에 None이 찍히는데, -> 0을 내부반환하고, 그것을 표시할 DEFAULT NONE 상수를 필수로 써야한다.
    FOLLOW = 2 ** 0  # 1
    COMMENT = 2 ** 1  # 2
    WRITE = 2 ** 2  # 4 : USER == PATIENT
    CLEAN = 2 ** 3  # 8
    RESERVATION = 2 ** 4  # 16 : STAFF, DOCTOR
    ATTENDANCE = 2 ** 5  # 32 : CHEIFSTAFF
    EMPLOYEE = 2 ** 6  # 64 : EXECUTIE
    ADMIN = 2 ** 7  # 128 : ADMIN <Permission.ADMIN: 128>
```
1. 외부에서 Permissions객체가 들어오면, request.state.user가 가진 `role 속 permission(total)`이 **특정 Permission보다 큰지 확인한다.**
    - **이 때, 개별 role객체 속 permission의 합이 한 단계 위 Permissions의 합에 못미치기 때문에 total VS 1개 permission으로 비교할 수 있다.**
    ```python
    def permission_required(permission: Permissions):
        def decorator(func):
            @wraps(func)
            async def wrapper(request: Request, *args, **kwargs):
                user: Users = request.state.user
    
                if not user.has_permission(permission):
                    # TODO: template error페이지
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
                return await func(request, *args, **kwargs)
            return wrapper
        return decorator
    ```
   
2. Users 모델에 `.has_permission()`의 메서드를 만들어준다.
    ```python
    class Users(BaseModel, SQLAlchemyBaseUserTable[int]):
        #...
        def has_permission(self, permission: Permissions) -> bool:
            """
            lazy='subquery' 되어 자동 load되는 Roles객체의 total_permission 합을 조회하여, 단독 Permission과 int비교
            @permission_required( ) 에서 사용될 예정.
            """
            #  9 > Permissions.CLEAN
            # True
            # => int Enum은 int와 비교 가능하다.(value로 비교)
    
            return self.role.permission >= permission
    ```
   
#### Permissions말고 RoleName으로 @role_required 만들기
1. **user가 가진 자동load role객체 속 permission VS `해당RoleName이 가진 total_permission or max_permission`을 비교하면 되는데**
    - **굳이 total할 필요없이, 특정 RoleName -> RolePermissions `set` 중 `가장 큰 permission`을 `input되는 Permissions객체`로 간주하고, has_permission을 비교하면 된다.**
    - **즉 `RoleName -> .max_permission(Permissions enum 1개)` VS `user.role.permission(total)`**
    - 이 때, max_permission(Permisssions ENUM)이 반환되면, 위에서 정의한 `has_permission`을 그대로 이용해서 처리한다.
    ```python
    class Users(BaseModel, SQLAlchemyBaseUserTable[int]):
        #...
        def has_role(self, role_name: RoleName) -> bool:
            return self.has_permission(role_name.max_permission)
    ```
   
2. 이제 user.has_role( RoleName )을 이용해 `role_required` 데코레이터를 정의한다.
    ```python
    def role_required(allowed_role_name: RoleName):
        def decorator(func):
            @wraps(func)
            async def wrapper(request: Request, *args, **kwargs):
                user: Users = request.state.user
                
                # 내부에서 user.has_permission을 이용
                if not user.has_role(allowed_role_name):
                    # TODO: template error페이지
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    
                return await func(request, *args, **kwargs)
            return wrapper
        return decorator
    
    ```

### 이제 /guilds 라우터는 @login_require 아래쪽에서 @role or @permission으로 검사를 추가한다.

```python
@router.get("/guilds")
@oauth_login_required(SnsType.DISCORD)
@role_required(RoleName.ADMINISTRATOR)
# @permission_required(Permissions.ADMIN)
async def guilds(request: Request):
    #...
```
### test용 user_info Faker Provider에서 request로 들어갈 role_name 추가
```python
class UserProvider(BaseProvider):
    #..
    def create_user_info(self, **kwargs):
        _faker = self.generator
        #...
        role_name = _faker.random_element(RoleName).value

        return dict(
            email=fake_profile['mail'],
            hashed_password=hash_password("string"),
            phone_number=phone_number,
            name=fake_profile['name'],
            nickname=fake_profile['username'],
            birthday=fake_profile['ssn'][:6],
            age=age,
            status=status,
            gender=gender,
            sns_type=sns_type,
            role_name=role_name,
        ) | kwargs
```

## DOCEKR, 설정 관련

### 터미널에서 main.py가 아닌 os로 DOCKER_MODE아니라고 신호주고 사용
- **docker -> `mysql`호스트DB접속이 아니라 | local -> `localhost`호스트DB접속시키려면 환경변수를 미리입력해줘야한다.**
- **비동기(`await`)가 가능하려면, python 터미널이 아닌 `ipython`으로 들어와야한다.**
```python
import os;os.environ['DOCKER_MODE']="False";
from app.models import Users
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