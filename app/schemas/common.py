from pydantic import BaseModel


class Message(BaseModel):
    message: str = None


class SuccessMessage(BaseModel):
    message: str = "ok"


class FailMessage(BaseModel):
    message: str = "fail"
