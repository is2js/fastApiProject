from typing import Optional, List

from pydantic import BaseModel


class KakaoMessageRequest(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None


class EmailRecipient(BaseModel):
    name: str
    email: str


class EmailRequest(BaseModel):
    mailing_list: List[EmailRecipient]


class SESRequest(BaseModel):
    recipients: Optional[List[str]] = None

    mail_title: Optional[str] = None  # 메일 제목

    greetings: Optional[str] = None  # 고객님, xxxx !
    introduction: Optional[str] = None  # yyyyy

    title: Optional[str] = None  # 잇슈 제목
    description: Optional[str] = None  # 잇슈 내용
