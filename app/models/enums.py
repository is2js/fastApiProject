from enum import Enum


class UserStatus(str, Enum):
    admin = "admin"
    active = "active"
    deleted = "deleted"
    blocked = "blocked"


class ApiKeyStatus(str, Enum):
    active = "active"
    stopped = "stopped"
    deleted = "deleted"
