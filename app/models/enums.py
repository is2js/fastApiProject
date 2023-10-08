from enum import Enum


class UserStatus(str, Enum):
    ADMIN = "admin"
    ACTIVE = "active"
    DELETED = "deleted"
    BLOCKED = "blocked"


class SnsType(str, Enum):
    EMAIL: str = "email"
    # FACEBOOK: str = "facebook"
    GOOGLE: str = "google"
    KAKAO: str = "kakao"
    DISCORD: str = "discord"

    @classmethod
    def contains(cls, oauth_name):
        return oauth_name in cls.__members__.values()


class Gender(str, Enum):
    MALE = "male"
    FEMAIL = "female"


class ApiKeyStatus(str, Enum):
    ACTIVE = "active"
    STOPPED = "stopped"
    DELETED = "deleted"
