## 프로젝트 소개

- 비교적 최신 웹 프레임워크인 fastAPI를 이용해서 `소셜로그인 + 알림 API` 어플리케이션을 구현합니다.
    - fastAPI선택 이유: 문서자동화, 역직렬화 속도, 비동기 지원 
    - [참고문서](https://tech.kakaopay.com/post/image-processing-server-framework/)
    - python 3.9 / sqlalchemy 2.0.4 이상(relationship refresh lazy load를 위함.)
- 구현 목표
    - fastAPI, DB 등을 모두 Dockerizing 한다.
    - Test 코드를 작성하고 CI를 활용한다.
    - Raw query대신 sqlalchemy 2.0의 mixin 등을 구현해서 활용한다.

- [참고 프로젝트](https://github.com/riseryan89/notification-api)와 차이점
    - 제작 과정 문서화 + 도커라이징 + 프로젝트 구조 변경(api패키지 도입)
    - DB table 자동 생성 적용
    - schemas.py <-> models.py 구분
    - Sqlalchemy BaseModel <-> Mixin 구분, Sqlalchemy Mixin 고도화(2.0 style + async 적용 등)
        - `Sqlalchemy 2.0 style + async`를 적용한 mixin 구현
        - AsyncSession 사용시 BaseModel의 default칼럼 refresh prevening by `__mapper_args__ = {"eager_defaults": True}`
    - 명확한 변수화(is_exists -> exists_user, reg_info -> user_register_info 등)
    - 코드 간결화(if user: return True + return False -> return True if user else False)
    - `Pydantic v1 -> v2` 적용 및 Schema패키지 도입하여 세분화
        - 참고페이지: https://zenn.dev/tk_resilie/articles/fastapi0100_pydanticv2
        - .from_orm().dict()) -> .model_validate().model_dump()
        - class Config: orm_mode = True -> model_config = ConfigDict(from_attributes=True)
    - 미들웨어 `Exceptions handling 세분화`
    - `Logger 설정 세분화`(api log <-> db log 구분하여 미들웨어에서 logging)

- Todo
    - request_service_sample.py를 test코드로 변경


## 설치

---

1. 도커가 있는 환경
    ```shell
    git clone
    .env.dev -> .env 변경 및 내용 수정
   
    docker-compose up -d (포트 - api:8010, mysdql: 13306)
    ```

2. 도커가 없는 환경
    ```shell
    git clone
    .env.dev -> .env 변경 및 내용 수정 (기본 포트 - api:8010, mysdql: 13306)
    
    venv 가상환경 생성 및 활성화
    pip install -r requirements.txt
    uvicorn app.main:app --host=0.0.0.0 --reload
    ```
