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
