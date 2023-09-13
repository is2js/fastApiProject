from typing import Optional

from pydantic import BaseModel


class KakaoMessageRequest(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
