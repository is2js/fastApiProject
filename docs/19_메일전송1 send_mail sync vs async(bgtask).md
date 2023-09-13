### 동기 vs 비동기 메일 전송
- fastapi 에서 제공하는 background_tasks를 이용하면, 다른 thread로 빠지게 되고, 일을 끝마치지 않아도 return이 온다.
    - router내부 6초 -> bgtask: 0.2초
- **rest api 서비스라면, 오래걸리는 작업은 bg로 빼서 처리해줘야한다.**
    - django, flask는 celery를 따로 써야한다.



1. 일단 router에 post요청으로 `name + email`이 `List`로 들어와야한다.
    - **name+email의 RequestSChema -> 그것을 List로 하는 Schema 2개를 구성한다.**
    ```python
    class EmailRecipient(BaseModel):
        name: str
        email: str
    
    
    class EmailRequest(BaseModel):
        mailing_list: List[EmailRecipient]
    
    ```
    ```python
    @router.post('/email/send_by_gmail_sync')
    async def send_by_gmail_sync(request: Request, email_request: EmailRequest):
        mailing_list = email_request.mailing_list
        #  [EmailRecipient(name='議곗옱�꽦', email='tingstyle@gmail.com'), ...]
        
        return SuccessMessage()
    
    ```
   
2. 이제 `mailing_list`를 인자로 받는 **send_mail모듈의 코드를 작성해야한다.**
    - **그 전에 `yagmail`패키지를 설치하여, 쉽게 admin email과 password로 로그인 -> list 전송까지 한다.**
    ```shell
    pip install yagmail
    
    pip freeze > .\requirements.txt
    
    docker-compose build --no-cache api; docker-compose up -d api;
    ```
3. 이제 email을 보낼 admin sender 의 gmail과 pw가 필요하다. .dotenv에 정의후 가져온다
    ```python
    @router.post('/email/send_by_gmail_sync')
    async def send_by_gmail_sync(request: Request, email_request: EmailRequest):
        mailing_list = email_request.mailing_list
        #  [EmailRecipient(name='議곗옱�꽦', email='tingstyle@gmail.com'), ...]
    
        # 메일을 보내는 sender의 계정/password
        sender_gmail = os.getenv('ADMIN_GMAIL', None)
        sender_gmail_app_pw = os.getenv('ADMIN_GMAIL_APP_PASSWORD', None)
        sender_gmail_nickname = os.getenv('ADMIN_GMAIL_NICKNAME', None)

    
        return SuccessMessage()
    ```
    ```dotenv
    # ADMIN -
    ADMIN_GMAIL="tingstyle11@gmail.com" # send_by_gmail 호출시 필요함.
    ADMIN_GMAIL_APP_PASSWORD="app비밀번호"
    ADMIN_GMAIL_NICKNAME="한의원인증앱"
    ```
   - **[이 링크](https://myaccount.google.com/u/1/lesssecureapps)로 가서, `수시로, 풀릴 수 있으니, 낮은 수준 앱 활성화`를 체크해줘야한다.**
       - 보안 > 2단계인증 후 클릭 -> 맨 밑에 앱 비밀번호(`notification_api: vqrt caer eruu tbvo`)
       - **`이 때 발급되는 비밀번호`를 중간에 space를 제거하고 yag에 넣어줘야하는 비밀번호다.**
4. 로그인 후, `yag.send()`의 3번째 인자로 contents를 list로 건네준다.
    - EMAIL_CONTENT_FORMAT에는 .format()으로 recipient.name이 들어갈 것이다.
    ```python
    @router.post('/email/send_by_gmail_sync')
    
    async def send_by_gmail_sync(request: Request, email_request: EmailRequest):
    
     import time
        t = time.time()
    
        EMAIL_CONTENTS_FORMAT = "{name}님 안녕하세요"
    
        mailing_list = email_request.mailing_list
        #  [EmailRecipient(name='議곗옱�꽦', email='tingstyle@gmail.com'), ...]
    
        # 메일을 보내는 sender의 계정/password
        sender_gmail = os.getenv('ADMIN_GMAIL', None)
        sender_gmail_app_pw = os.getenv('ADMIN_GMAIL_APP_PASSWORD', None)
        sender_gmail_nickname = os.getenv('ADMIN_GMAIL_NICKNAME', None)
        # https://myaccount.google.com/u/1/lesssecureapps
    
        # 1) 받는사람이 있는 경우에만 로그인 시도
        if mailing_list:
            try:
                yag = yagmail.SMTP(
                    {sender_gmail: sender_gmail_nickname}, sender_gmail_app_pw
                )
                for recipient in mailing_list:
                    contents = [
                        EMAIL_CONTENTS_FORMAT.format(name=recipient.name)
                    ]
                    yag.send(recipient.email, '제목', contents)
    
            except Exception as e:
                print(e)
    
        # print(str(round((time.time() - t) * 1000, 5)) + "ms")
        # 2398.16141ms 2초
        return SuccessMessage()
    ```
5. **이제 로그인을 시도하고 실패할 경우, `해당 모듈은 추후 background_tasks`로 실행될거고, 이미 rest api response는 빠져나가기 때문에, `에러가 로그만 찍히`기 때문에, 따로 알려줘야한다.**
    - **kakao든, sentry든 누군가에게 알려야한다.**
    - **또한, 너무 빠르게 보내면 google에서 컷하기 때문에 `sleep(1)`을 걸어주고**
    - **실패했다면, 에러나기 직전 `last_mail_name=''`가변 변수에 매번 찍어주고, except에서 찍어준다.**
    ```python
    last_email = ''
    # 1) 받는사람이 있는 경우에만 로그인 시도
    if mailing_list:
        try:
            yag = yagmail.SMTP(
                {sender_gmail: sender_gmail_nickname}, sender_gmail_app_pw
            )
            for recipient in mailing_list:
                contents = [
                    EMAIL_CONTENTS_FORMAT.format(name=recipient.name)
                ]
                time.sleep(1)
                yag.send(recipient.email, '제목', contents)
                last_email = recipient.email

        except Exception as e:
            print(e)
            print(last_email)
    ```
   
6. 이제 word -> 에디터편지기 붙혀넣기를 통해서, email 양식 html코드를 얻는다.
    - **생성된 html을 consts.py에 templates으로서 정의하고 변수들을 뺀다.**
    ```python
    ## TEMPLATE
    # email - {name}{greetings}{introduction}{title}{description}{image_url}
    EMAIL_CONTENTS_FORMAT = (
        "<div style='margin-top:0cm;margin-right:0cm;margin-bottom:10.0pt;margin-left:0cm"
        ';line-height:115%;font-size:15px;font-family:"Calibri",sans-serif;border:none;bo'
        "rder-bottom:solid #EEEEEE 1.0pt;padding:0cm 0cm 6.0pt 0cm;background:white;'>\n\n<"
        "p style='margin-top:0cm;margin-right:0cm;margin-bottom:11.25pt;margin-left:0cm;l"
        'ine-height:115%;font-size:15px;font-family:"Calibri",sans-serif;background:white'
        ";border:none;padding:0cm;'><span style='font-size:25px;font-family:\"Helvetica Ne"
        "ue\";color:#11171D;'>안녕하세요, {name}님! {greetings}</spa"
        "n></p>\n</div>\n\n<p style='margin-top:0cm;margin-right:0cm;margin-bottom:11.25pt;m"
        'argin-left:0cm;line-height:17.25pt;font-size:15px;font-family:"Calibri",sans-ser'
        "if;background:white;vertical-align:baseline;'><span style='font-size:14px;font-f"
        'amily:"Helvetica Neue";color:#11171D;\'>{introduction}</span></p>'
        "\n\n<p style='margin-top:0cm;margin-right:0cm;margin-bottom:10.0pt;margin-left:0cm"
        ';line-height:normal;font-size:15px;font-family:"Calibri",sans-serif;background:w'
        "hite;'><strong><span style='font-size:24px;font-family:\"Helvetica Neue\";color:#1"
        "1171D;'>{title}</span></stron"
        "g></p>\n\n<p style='margin-top:0cm;margin-right:0cm;margin-bottom:11.25pt;margin-l"
        'eft:0cm;line-height:17.25pt;font-size:15px;font-family:"Calibri",sans-serif;back'
        "ground:white;vertical-align:baseline;'><span style='font-size:14px;font-family:\""
        "Helvetica Neue\";color:#11171D;'>{description}</span></p>\n\n<p style='margin-top:0cm;margin-right:0cm;margin"
        '-bottom:11.25pt;margin-left:0cm;line-height:17.25pt;font-size:15px;font-family:"'
        "Calibri\",sans-serif;text-align:center;background:white;vertical-align:baseline;'"
        "><span style='font-size:14px;font-family:\"Helvetica Neue\";color:#11171D;'><img w"
        'idth="378" src="{image_url}" alt="sample1.jpg" class='
        '"fr-fic fr-dii"></span></p>\n\n<p>\n<br>\n</p>'
    )
    ```

7. 환경변수에서 가져오는 변수들은 config.py에 전역상수로 정의한다.
    ```python
    # consts.py
    
    # email
    ADMIN_GMAIL = os.getenv('ADMIN_GMAIL', None)
    ADMIN_GMAIL_APP_PASSWORD = os.getenv('ADMIN_GMAIL_APP_PASSWORD', None)
    ADMIN_GMAIL_NICKNAME = os.getenv('ADMIN_GMAIL_NICKNAME', None)
    ```

8. 메일보내는 코드를 utils > `service_utils.py`를 정의해서 메서드로 정의한다.
    - **전역상수들은 메서드의 keyword기본값으로 넣어준다.**
    - **메일 제목도 변수 mail_title로 빼주고, template에 들어갈 변수들은 template_xxx로 키워드로 기본값을 넣어준다.**
    ```python
    # utils > service_utils.py
    import time
    
    import yagmail
    
    from app.common.config import ADMIN_GMAIL, ADMIN_GMAIL_APP_PASSWORD, ADMIN_GMAIL_NICKNAME, KAKAO_SEND_ME_IMAGE_URL
    from app.common.consts import EMAIL_CONTENTS_FORMAT
    
    
    def send_mail(
            mailing_list,
            sender_gmail=ADMIN_GMAIL,
            sender_gmail_app_pw=ADMIN_GMAIL_APP_PASSWORD,
            sender_gmail_nickname=ADMIN_GMAIL_NICKNAME,
            mail_title="안녕하세요. 한의원인증앱입니다.",
            template_greetings="오늘은 어떠셨나요?",
            template_introduction="저희는 한의원 인증앱입니다^^😁",
            template_title="회원가입을 축하드립니다!",
            template_description="실시간 진료정보와 다양한 컨텐츠들을 만나보세요!",
            template_image_url=KAKAO_SEND_ME_IMAGE_URL,
    ):
        # https://myaccount.google.com/u/1/lesssecureapps
    
        last_email = ''
        # 1) 받는사람이 있는 경우에만 로그인 시도
        if mailing_list:
            try:
                yag = yagmail.SMTP(
                    {sender_gmail: sender_gmail_nickname}, sender_gmail_app_pw
                )
                for recipient in mailing_list:
                    contents = [
                        EMAIL_CONTENTS_FORMAT.format(
                            name=recipient.name,
                            greetings=template_greetings,
                            introduction=template_introduction,
                            title=template_title,
                            description=template_description,
                            image_url=template_image_url,
                        )
                    ]
                    time.sleep(1)
                    yag.send(recipient.email, mail_title, contents)
                    last_email = recipient.email
    
            except Exception as e:
                print(e)
                print(last_email)  # 실패직전까지 보낸 마지막 email
    
        # TODO: kakao or slack or sentry로 비동기(타 쓰레드) -> 미들웨어 안탐. 에러만 남음. 알려줘야함.
        print('알림이 필요합니다.')
    
    ```
   
#### async로 오래걸리는 동기유틸메서드를 수행 by BackgroundTask를 주입해서 사용
```python
from starlette.background import BackgroundTasks

@router.post('/email/send_by_gmail_async')
async def send_by_gmail_sync(request: Request, email_request: EmailRequest, background_tasks: BackgroundTasks):
    mailing_list = email_request.mailing_list

    background_tasks.add_task(
        send_mail, mailing_list=mailing_list
    )

    return SuccessMessage()
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

- 참고
    - 이동: git clone 프로젝트 커밋id 복사 -> `git reset --hard [커밋id]`
    - 복구: `git reflog` -> 돌리고 싶은 HEAD@{ n } 복사 -> `git reset --hard [HEAD복사부분]`