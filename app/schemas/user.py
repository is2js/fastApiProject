from typing import Optional

from pydantic import BaseModel


class UserMe(BaseModel):
    id: int
    email: str = None

    name: Optional[str] = None
    phone_number: Optional[str] = None
    profile_img: Optional[str] = None
    sns_type: Optional[str] = None

    class Config:
        # orm_mode = True
        from_attributes = True
