### /calendar_sync route에서  creds를 가진 user의 calendar list 뽑기
- 참고: https://github.dev/PigsCanFlyLabs/cal-sync-magic/blob/main/cal_sync_magic/models.py
- service로 추출한 calendar의 내용
    - **우리는 calendar의 `id` calendar_id + `summary` -> name + `있다면 deleted` -> is_deleted 여부**
```python
    # [
    #     {
    #         "kind":"calendar#calendarListEntry",
    #         "etag":"\"1657577269858000\"",
    #         "id":"addressbook#contacts@group.v.calendar.google.com",
    #         "summary":"�깮�씪",
    #         "description":"Google 二쇱냼濡앹뿉 �벑濡앸맂 �궗�엺�뱾�쓽 �깮�씪, 湲곕뀗�씪, 湲고� �씪�젙 �궇吏쒕�� �몴�떆�빀�땲�떎.",
    #         "timeZone":"Asia/Seoul",
    #         "summaryOverride":"Contacts",
    #         "colorId":"17",
    #         "backgroundColor":"#9a9cff",
    #         "foregroundColor":"#000000",
    #         "accessRole":"reader",
    #         "defaultReminders":[
    #
    #         ],
    #         "conferenceProperties":{
    #             "allowedConferenceSolutionTypes":[
    #                 "hangoutsMeet"
    #             ]
    #         }
    #     },
    #     {
    #         "kind":"calendar#calendarListEntry",
    #         "etag":"\"1657580828523000\"",
    #         "id":"ko.south_korea#holiday@group.v.calendar.google.com",
    #         "summary":"���븳誘쇨뎅�쓽 �쑕�씪",
    #         "description":"���븳誘쇨뎅�쓽 怨듯쑕�씪",
    #         "timeZone":"Asia/Seoul",
    #         "summaryOverride":"���븳誘쇨뎅�쓽 �쑕�씪",
    #         "colorId":"17",
    #         "backgroundColor":"#9a9cff",
    #         "foregroundColor":"#000000",
    #         "accessRole":"reader",
    #         "defaultReminders":[
    #
    #         ],
    #         "conferenceProperties":{
    #             "allowedConferenceSolutionTypes":[
    #                 "hangoutsMeet"
    #             ]
    #         }
    #     },
    # ]
```
```python
@router.get("/calendar_sync")
# @oauth_login_required(SnsType.GOOGLE)
@oauth_login_required(SnsType.GOOGLE, required_scopes=CALENDAR_SCOPES)
@role_required(RoleName.STAFF)
async def sync_calendar(request: Request):
    user: Users = request.state.user
    service_name = get_google_service_name_by_scopes(CALENDAR_SCOPES)
    calendar_service = await user.get_google_service(service_name)
    google_calendars = calendar_service.calendarList().list().execute()

    calendars = []
    for calendar in google_calendars['items']:
        # model을 담기 전, dict list로 뽑아본다.
        calendars.append(dict(
            # google_account_id=user.get_oauth_account(SnsType.GOOGLE).id,  # 추후 FK
            user_id=user.id,  # 추후 FK -> 구글 계정별 calendar도 되지만, 우리는 google계정 1개만 사용 + Users에 딸린 calendar를 바로 찾을 수 있다.
            calendar_id=calendar['id'],
            calendar_name=calendar['summary'],
            is_deleted=calendar.get('deleted', False),  # "deleted"키가 포함되어있고, True면 삭제 된 것. 없을 수 있어서 .get()
        ))

    context = {
        'calendars': calendars
    }
    return render(request, "dashboard/calendar-sync.html", context=context)

```
## DOCEKR, 설정 관련

### 터미널에서 main.py가 아닌 os로 DOCKER_MODE아니라고 신호주고 사용

- **docker -> `mysql`호스트DB접속이 아니라 | local -> `localhost`호스트DB접속시키려면 환경변수를 미리입력해줘야한다.**
- **비동기(`await`)가 가능하려면, python 터미널이 아닌 `ipython`으로 들어와야한다.**

```python
import os;

os.environ['DOCKER_MODE'] = "False";
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