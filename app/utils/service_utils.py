import time
from typing import List

import boto3
import yagmail
from botocore.exceptions import ClientError

from app.common.config import ADMIN_GMAIL, ADMIN_GMAIL_APP_PASSWORD, ADMIN_GMAIL_NICKNAME, KAKAO_SEND_ME_IMAGE_URL, \
    AWS_SES_AUTHORIZED_EMAIL, AWS_ACCESS_KEY, AWS_SECRET_KEY
from app.common.consts import EMAIL_CONTENTS_FORMAT
from app.schemas import EmailRecipient


def send_mail(
        mailing_list: List[EmailRecipient],
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


async def send_mail_by_ses(
        recipients: List[str] = None,
        sender: str = f"인증앱 admin<{ADMIN_GMAIL}>",
        mail_title: str = "안녕하세요! 한의원 인증앱 입니다.",
        template_greetings="아래 사항을 확인해주세요.",
        template_introduction="문제가 발견되었습니다.",
        template_title="ISSUE",
        template_description="해당 링크 <a href='https://hani.chojaeseong.com'>공지사항</a>를 통해 확인해주세요",
        template_image_url=KAKAO_SEND_ME_IMAGE_URL,
):
    # sender = f"인증앱 admin<admin@{HOST_MAIN}>" # host의 메일서버가 있을 때.
    if recipients is None:
        # sandbox 상태에서는 인증된 메일만 받기 가능
        recipients: List[str] = [AWS_SES_AUTHORIZED_EMAIL]

    region = "ap-northeast-2"  # 한국/서울

    # body에 링크만 있으면, 스팸으로 인식됨. 글자도 충분히 있어야한다.
    body_text = mail_title + "\r\n HTML 버전만 지원합니다!"
    body_html = EMAIL_CONTENTS_FORMAT.format(
        name="고객",
        greetings=template_greetings,
        introduction=template_introduction,
        title=template_title,
        description=template_description,
        image_url=template_image_url,
    )

    charset = "UTF-8"

    client = boto3.client(
        "ses",
        region_name=region,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
    )

    try:
        response = client.send_email(
            Source=sender,
            Destination={"ToAddresses": recipients},
            Message={
                "Body": {
                    "Html": {"Charset": charset, "Data": body_html},
                    "Text": {"Charset": charset, "Data": body_text},
                },
                "Subject": {"Charset": charset, "Data": mail_title},
            },
        )
    except ClientError as e:
        # TODO: 실패시 어디다가 보내기
        print(e.response['Error']['Message'])
    else:

        # TODO: 성공시 어디다가 알리기?
        print(f"Email sent! Message ID: {response['MessageId']}"),
        # Email sent! Message ID: 010c018a9382e4a4-2d7561d2-b429-449b-9f20-8155790b963e-000000
