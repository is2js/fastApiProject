import enum
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


class Permissions(int, Enum):
    NONE = 0  # execute상황에서 outerjoin 조인으로 들어왔을 때, 해당 칼럼에 None이 찍히는데, -> 0을 내부반환하고, 그것을 표시할 DEFAULT NONE 상수를 필수로 써야한다.
    FOLLOW = 2 ** 0  # 1
    COMMENT = 2 ** 1  # 2
    WRITE = 2 ** 2  # 4 : USER == PATIENT
    CLEAN = 2 ** 3  # 8
    RESERVATION = 2 ** 4  # 16 : STAFF, DOCTOR
    ATTENDANCE = 2 ** 5  # 32 : CHEIFSTAFF
    EMPLOYEE = 2 ** 6  # 64 : EXECUTIE
    ADMIN = 2 ** 7  # 128 : ADMIN <Permission.ADMIN: 128>


class RolePermissions(set, Enum):
    # 각 요소들이 결국엔 int이므로, deepcopy는 생각안해도 된다?
    # 미리 int들을 안더하는 이유는, Roles DB 생성시, RoleType속 permission들을 순회 -> int칼럼에 누적

    # user: list = list({Permissions.FOLLOW, Permissions.COMMENT, Permissions.WRITE})
    # staff: list = list(set(user + [Permissions.CLEAN, Permissions.RESERVATION]))
    # doctor: list = list(staff)  # 주소겹치므로 list()로 swallow copy
    # chiefstaff: list = list(set(doctor + [Permissions.ATTENDANCE]))
    # executive: list = list(set(chiefstaff + [Permissions.EMPLOYEE]))
    # administrator: list = list(set(executive + [Permissions.ADMIN]))
    user: set = {Permissions.FOLLOW, Permissions.COMMENT, Permissions.WRITE}
    staff: set = user.union({Permissions.CLEAN, Permissions.RESERVATION})
    doctor: set = set(staff)
    chiefstaff: set = doctor.union({Permissions.ATTENDANCE})
    executive: set = chiefstaff.union({Permissions.EMPLOYEE})
    administrator: set = executive.union({Permissions.ADMIN})


class RoleName(str, Enum):
    USER: str = 'user'
    STAFF: str = 'staff'
    DOCTOR: str = 'doctor'
    CHIEFSTAFF: str = 'chiefstaff'
    EXECUTIVE: str = 'executive'
    ADMINISTRATOR: str = 'administrator'

    def get_role_permission_set(self) -> set:
        return getattr(RolePermissions, self.value)

    @property
    def total_permission(self) -> int:
        return sum(self.get_role_permission_set())

    @property
    def max_permission(self) -> Permissions:
        return max(self.get_role_permission_set(), key=lambda x: x.value)
