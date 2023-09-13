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
