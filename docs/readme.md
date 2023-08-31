## 프로젝트 소개

- 비교적 최신 웹프레임워크인 fastAPI를 이용해서 `소셜로그인 + 알림 API` 어플리케이션을 구현합니다.

- 구현 목표
    - fastAPI, DB 등을 모두 Dockerizing 한다.
    - Test 코드를 작성하고 CI를 활용한다.
    - Raw query대신 sqlalchemy 2.0의 mixin 등을 구현해서 활용한다.

- [기존 프로젝트](https://github.com/riseryan89/notification-api)와 차이점
    - 제작 과정 문서화
    - 도커라이징(app, db 등) 
    - DB table 자동 생성 적용
    - schema.py <-> models.py 구분
    - Sqlalchemy BaseModel <-> Mixin 구분, Sqlalchemy Mixin 고도화(Repr, CRUD 등)
    - 명확한 변수화(is_exists -> exists_user, reg_info -> user_register_info 등)
    - 코드 간결화(if user: return True + return False -> return True if user else False)
    - Pydantic v1 -> v2 (.from_orm().dict()) -> .model_validate().model_dump())

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
