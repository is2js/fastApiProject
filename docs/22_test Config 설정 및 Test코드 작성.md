### TestConfig 작성
1. sqlalchemy class에서, is_test_mode면, 을 추가해서, 
    - self._engine.url의 db_url이 localhost여야한다. -> 아니면 에러
    - 새롭게 임시엔진을 만든다.
    - database가 있으면 drop하고, 다시 생성한다
    - 임시엔진을 .dispose()한다.

2. TestConfig에서는 database가 test용으로 notification_test 등으로 만들어야한다.
    - 이 때, travis를 쓸거면, travis@`localhost`를 db host로 써야한다.
3. pytest를 돌릴 때, Config객체가 testconfig로 들어가야한다.
    - config객체에 따라서 sqlalchemy 내부에서 초기화되는게 다르다.

4. conftest.py 
    - 일단 app객체를 만들 때, os.environ['API_ENV'] = "test"로 환경변수를 덮어쓴다.
    - 그다음에 해당엔진으로 table을 생성 + TestClient(app=app)생성을 동시에 한다.
5. session을 1개 뽑아와야하는데, Depends를 오버라이딩해서 처리해본다.
    - yield session이 돌아오면, 커밋을 하지 않고, 해당 sess로 table데이터를 다 삭제한 뒤, rollback을 해준다.
    - 이 때, table데이터 삭제시 해당session으로 fk제한을 제거시켜서 삭제한다.
6. login은 해당session으로 유저객체를 미리 생성 -> 토큰 생성 -> headers형태의 dict(Authorization=) 반환해준다.
7. pytest패키지를 설치 후, pytest만 명령해도 바로 가능하다.
8. 테스트코드는 실패의 경우도 다룬다.
9. 만약, kakao_token을 받는 테스트를 만들려면, mocking을 해야한다.
10. 실행편집 > `+` > Pytest 체크 후 > 경로 설정
11. 
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