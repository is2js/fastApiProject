### logger
1. utils 폴더에 `logger.py`를 생성한다
2. common > config.py 에 BASE_DIR에 `logs`를 join하여 `LOG_DIR` 경로를 생성한다.
    ```python
    @dataclass
    class Config:
        """
        기본 Configuration
        """
        BASE_DIR = base_dir
        LOG_DIR = path.join(BASE_DIR, 'logs')
    ```
   
3. logs 폴더를 gitignore에 추가한다.
    ```python
    /.env
    /venv/
    /docker/db/mysql/data/
    /docker/db/mysql/logs/
    /logs/
    ```
4. 환경에 따라, backup 갯수를 다르게 config에 설정한다.
    ```python
    @dataclass
    class LocalConfig(Config):
    
        # log
        LOG_BACKUP_COUNT = 1
        
    @dataclass
    class ProdConfig(Config):
        # log
        LOG_BACKUP_COUNT = 10
    ```
   
#### 1단계 -> logger객체 정의 -> property로 직접 내부 logger를 꺼내서, 직접 찍기
1. **1단계로서, `category app/db 등`에 따라 다른 name을 가진 logger객체를 생성할 수 있는 `class Logger`를 정의한다.**
    - gunicorn logger, logging의 logger도 있지만, fastapi의 logger를 가져와서 작성한다.
    - 선택할 수 있는 최소레벨의 종류를 dict로 `log_levels`로 정의해놓고 고를 수 있게 한다.
    - **생성자에서는, config에 설정된 backup_count를 기본값으로 넣고, `log_name`을 받게 한다.**
        - 생성자 내부에서는, conf에 설정된 LOG_DIR + log_name으로 `logs폴더/log_name폴더`를 생성할 수 있는 경로를 만들고, `os.makdedirs`로 폴더를 생성한다.
        - log_name으로 해당폴더/ `log_name.log`파일을 설정한다. 
        - log파일에 찍힐 dateformat 양식을 설정하고, formatter를 만든 뒤, handler를 생성해 추가한다.
        - **logging의 logger는 싱글톤받식으로 .getLogger(name)메서드로 1개 생성되면 같은 것을 가져오는데, `fastapi의 logger는 .getChild(name)`으로 싱글톤 방식을 흉내내서 가져온다.**
        - log level을 DEBUG로 일단 지정한다. 
    - property `get_logger`로 해당 객체의 숨겨진 _logger를 가져올 수 있게 한다.

    ```python
    import logging
    from logging.handlers import TimedRotatingFileHandler
    from app.common.config import conf
    
    
    class Logger:
        # 선택할 수 있는 최소 레벨 종류
        log_levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
    
        def __init__(self, log_name, backup_count=conf().LOG_BACKUP_COUNT):
            self.log_name = log_name
            # logger의 'APP', "DB" 등 이름에 따라 자체 폴더 경로 + 파일이름 생성
            self.log_dir = os.path.join(conf().LOG_DIR, self.log_name)
            if not os.path.exists(self.log_dir):
                os.makedirs(self.log_dir, exist_ok=True)
            self.log_file = os.path.join(self.log_dir, f'{self.log_name}.log')
            
            self._log_format = '%Y-%m-%d %H:%M:%S'  # .log 파일에만 찍히는 형태
            formatter = logging.Formatter(
                '[%(levelname)s] %(asctime)s %(filename)s:%(lineno)d %(message)s',
                datefmt=self._log_format
            )
            handler = TimedRotatingFileHandler(
                filename=self.log_file,
                backupCount=backup_count,
                when="midnight",
            )
            handler.suffix = "%Y%m%d"  # 오늘이 아니라면, xxx.log.[suffix]형태로 붙음
            handler.setFormatter(formatter)
    
            # fastapi의 logger에 같은 이름이라면 sub logger로 설정
            # - flask + logging 버전
            # - self._logger = logging.getLogger(self.log_name)
            self._logger = logger.getChild(self.log_name) # fastapi 전용
            self._logger.addHandler(handler)
            # 최소 level을 debug로 설정 -> 개별 logger들로 직접 찍을 것을 대비
            # cf) api용 .log()는 info or error만 사용.
            self._logger.setLevel(self.log_levels.get("DEBUG"))
    
        @property
        def get_logger(self):
            return self._logger
    ```
2. 객체 logger 테스트는 category(name)별로 객체를 미리 생성해놓고, .get_logger프로퍼티로 `.debug(), .info()`등을 main에서 찍어보면 된다.
    ```python
    app_logger = Logger("app").get_logger
    db_logger = Logger("db").get_logger
    if __name__ == '__main__':
        ...
        app_logger.debug("test")
        app_logger.info("test")
    ```
   

#### 2단계: logger객체.log(req, res or error)로 자동으로 info/error를 찍는 async 메서드 만들기
1. `async def log()`메서드를 정의하고 `request는 필수`, response와 error는 선택이므로 keyword로 정의한다.
```python
class Logger:
    #...
    async def log(self, request: Request, response=None, error=None):
        time_format = "%Y/%m/%d %H:%M:%S" # log_dict용 
        t = time.time() - request.state.start # access_control에서 찍었던 시간과 비교해서, response 직전의 시간차
        status_code = error.status_code if error else response.status_code # error가 들어왔다면, status_code 추출
        error_log = None # 채우기 전에 초기화
        if error:
            # 핸들링이 빡센 except: 내부에서 채워짐.
            if request.state.inspect:
                frame = request.state.inspect
                error_file = frame.f_code.co_filename
                error_func = frame.f_code.co_name
                error_line = frame.f_lineno
            else:
                error_file = error_func = error_line = "UNKNOWN"

            error_log = dict(
                errorFunc=error_func,
                location="{} line in {}".format(str(error_line), error_file),
                raised=str(error.__class__.__name__),
                message=str(error.exception),
                detail=error.detail,
            )
        # user(UserToken) schema
        # - ip + user_id + email 마스킹버전
        user = request.state.user
        email = user.email.split("@") if user and user.email else None
        user_log = dict(
            client=request.state.ip,
            user=user.id if user and user.id else None,
            email="**" + email[0][2:-1] + "*@" + email[1] if user and user.email else None,
        )
        # 최종 dict 
        # - UTC와 KST를 각각 time_format으로 지정
        log_dict = dict(
            url=request.url.hostname + request.url.path,
            method=str(request.method),
            statusCode=status_code,
            errorDetail=error_log,
            client=user_log,
            processedTime=str(round(t * 1000, 5)) + "ms", # time.time()의 차이를 x1000 후, round(,5)로 하면, ms가 나온다.
            datetimeUTC=datetime.utcnow().strftime(time_format),
            datetimeKST=(datetime.utcnow() + timedelta(hours=9)).strftime(time_format),
        )
        # 400대 에러는 핸들링된 에러라서, info로 찍는다.
        # -> 만든 dict를 json으로 변환한 뒤, -> logger로 찍는다.
        if error and error.status_code >= 500:
            self._logger.error(json.dumps(log_dict))
        else:
            self._logger.info(json.dumps(log_dict))
```
2. test에서는 Logger객체에서 .get_logger로 직접 꺼내지말고, 일단 객체로만 생성해놓고 -> 필요한 곳에서 `.log()`호출
```python
# app_logger = Logger("app").get_logger
# db_logger = Logger("db").get_logger
app_logger = Logger("app")
db_logger = Logger("db")
```
#### access_control에서 async 자동 log 찍기
- awati call_next() 밑에 api(view func, router)가 다 실행되고 난 뒤), response 응답 전 api log찍는다.
1. except_path에서 응답전에 찍을 때는, `/` index가 아닐때 찍어준다.
    ```python
    from app.utils.loggers import app_logger
    #...
    try:
        # 통과(access) 검사 시작 ------------
        # (1) except_path url 검사 -> 해당시, token없이 접속가능(/docs, /api/auth ~ 등) -> token 검사 없이 바로 endpoint(await call_next(request)) 로
        if await url_pattern_check(url, EXCEPT_PATH_REGEX) or url in EXCEPT_PATH_LIST:
            response = await call_next(request)
            # logging -> except_path 중에서는 index를 제외하고 찍기
            if url != "/":
                await app_logger.log(request=request, response=response)
            return response
    ```

2. api/렌더링 token검사 후 response를 return하기 전 log를 찍는다. 
    - **`try: 내부 성공 response`는 -> `request + response`를 인자로 넣으면 -> 자동으로 내부에서 `.info()`를 찍는다.**
    - **`except: 내부 에러 response`는 -> `request + error(APIException)`를 인자로 넣으면 -> 자동으로 내부에서 `.error()`를 찍는다.**
    ```python
     from app.utils.loggers import app_logger
     #...
     try:
        # ...
        # [1] api 접속 -> headers에 token정보 -> decode 후 user정보를 states.user에 심기
        if url.startswith('/api'):
            # ...
        # [2] 템플릿 레더링 -> cookies에서 token정보 -> decode 후 user정보를 states.user에 심기
        else:
            # ...
        
        response = await call_next(request)
        # 응답 전 logging
        await app_logger.log(request, response=response)
    except Exception as e:
        response = JSONResponse(status_code=error.status_code, content=error_dict)
        # 응답 전 logging
        await app_logger.log(request, error=error)
    
    return response
    ```

3. 이제 /test (템플릿 렌더링으로 넘어감) + `임시cookie 적용`에서 에러를 내서 로깅을 찍어보자.
    - authorization 없이 -> 401 에러 -> info(not error)
    ```python
    INFO: fastapi.app:{"url": "localhost/test", "method": "GET", "statusCode": 401,
                       "errorDetail": {"errorFunc": "UNKNOWN", "location": "UNKNOWN line in UNKNOWN",
                                       "raised": "NotAuthorized", "message": "None", "detail": "Authorization Required"},
                       "client": {"client": "172.25.0.1", "user": null, "email": null}, "processedTime": "0.26774ms",
                       "datetimeUTC": "2023/09/02 17:17:29", "datetimeKST": "2023/09/03 02:17:29"}
    ```
    - cookie 임시 적용(401해결) -> info + 200코드
    ```python
    INFO: fastapi.app:{"url": "localhost/test", "method": "GET", "statusCode": 200, "errorDetail": null,
                       "client": {"client": "172.25.0.1", "user": 2, "email": "**e*@example.com"},
                       "processedTime": "0.57054ms", "datetimeUTC": "2023/09/02 17:21:44",
                       "datetimeKST": "2023/09/03 02:21:44"}
    ```
4. test) cookie 임시 적용(401해결) + 강제 에러 + **inspect의 currentframe as frame**을 import해서, state.inpsect에 삽입까지
    - 핸들링 하기 어려운 에러는 이렇게 `currentframe()`을 호출해서 적용하면 에러난 위치를 확인할 수 있다.
    ```python
    from inspect import currentframe as frame
    @router.get("/test")
    async def test(request: Request):
    
        try:
            a = 1/0
        except Exception as e:
            request.state.inspect = frame()
            raise e
    
        current_time = datetime.utcnow()
        return Response(f"Notification API (UTC: {current_time.strftime('%Y.%m.%d %H:%M:%S')})")
    ```
    ```python
    ERROR: fastapi.app:{"url": "localhost/test", "method": "GET", "statusCode": 500,
                        "errorDetail": {"errorFunc": "test", "location": "40 line in /app/app/router/index.py",
                                        "raised": "APIException", "message": "division by zero",
                                        "detail": "division by zero"},
                        "client": {"client": "172.25.0.1", "user": 2, "email": "**e*@example.com"},
                        "processedTime": "0.51689ms", "datetimeUTC": "2023/09/02 17:25:56",
                        "datetimeKST": "2023/09/03 02:25:56"}
    
    ```
#### AWS Cloudwatch
1. Elastic Beanstalk에 로그를 적재함
2. 자동으로 LogRotation을 지원
3. S3에 텍스트파일로 저장
4. CloudWatch에서 로그 조회 검색 가능
5. 텍스트 파일은 DB가 아니라서, 좀 비싼 Athena라는 서비스를 이용할 수 있음.
    - 개인플젝에 쓰기 부담 -> S3에 쌓은 뒤, dynamoDb나 ec2 몽고db에 담아서 -> nosql로 쌓인 로그를 60일치 정도만 담기 나머지는 S3에 쌓아두기
    - 6개월 지난 로그 -> 블래시어 서비스 archive에 저장 **결제로그가 담기면, 5년이상 보관하면 된다.**
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