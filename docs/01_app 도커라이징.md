1. (파이참 생략)pycharm 자동생성이 아니라면
    - 가상환경 생성
    - fastapi 설치
    ```python
    pip install fastapi
    ```

```python
# pycharm 기본 코드 
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}

```

2. uvicorn도 없다면(파이참아닐 경우) 설치 후, import해서, main.py에서 uvicorn으로 실행하도록 변경하기
```shell
pip install uvicorn
```
```python
import uvicorn
from fastapi import FastAPI

app = FastAPI()

# ...
if __name__ == '__main__':
    uvicorn.run("main:app", port=8010, reload=True)

```

- **실행 후, 해당 포트 들어가서 확인**
- **해당포트`/docs`로 swagger 확인하기**

3. 기본 파일 생성하기 .gitignore / readm.md / .env / requirements.txt / Dockerfile 를 생성한다

```powershell
ni .gitignore, readme.md, .env, requirements.txt, Dockerfile, docker-compose.yml
```

4. app폴더 만들고, main.py를 옮긴다
5. docekr > app 폴더를 만들고, Dockerfile을 옮긴다.
    - **루트의 docker-compose에 의해 실행되서 `.`는 root라 생각하고, 작성한다.**
    - RUN이후 `EXPOSE 8000`과, `CMD ["",""]` 는 docker-compose에서 지정해준다.

```dockerfile
FROM python:3.9-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 환경변수 설정
# 시간대 설정
ENV TZ=Asia/Seoul
# RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

#COPY . /app
#WORKDIR /app

# add requirements.txt to the image
# - 여기서 .은 host의 docker-compose가 있는 root경로인다.
ADD ./requirements.txt /app/requirements.txt

# set working directory to /app/
WORKDIR /app

# install python dependencies
#RUN pip install -r requirements.txt

RUN python -m pip install --upgrade pip && \
    pip install -r requirements.txt --root-user-action=ignore && \
    rm -rf /root/.cache/pip && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
```

6. docker-compose.yml에 context는 현재root(.)에서, dockerfile:로 해당경로의 Dockerfile을 지정해서 실행시킬 수 있게 serivces를 구성한다.

- **그 전에, requirements.txt부터 산출한다.**

```powershell
 pip freeze > .\requirements.txt
```
- **app폴더내부 main.py에서 실행파일 작성시에는, 모듈경로가 `main:app`이지만, root->app폴더 볼륨연결하여 루트 상태라고 가정한다면 `app.main:app`**
- 도커이름을 api라고 지었음. 포트는 8010
```dockerfile
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: docker/app/Dockerfile
    restart: always
    env_file:
      - .env
    #environment:
    volumes:
      - .:/app
    command: [
      "uvicorn",
      "app.main:app",
      "--host=0.0.0.0",
      "--reload"
    ]
    ports:
      - "8010:8000"
```

7. docker-compose up -d  or 파이참 서비스탭에서 실행
- 로컬에서는 `localhost:8010` 및 docs로 접속한다.
- 파이참에서 제공되는 test_main.http의 포트도 8010으로 변경해준다.\


8. 메뉴 > VCS > git 저장소 생성 후 `.gitignore`에 venv / .env 걸어주기
    - 우클릭 > git > gitignore에 추가 



### 도커 명령어
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
```