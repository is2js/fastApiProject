from starlette import status

"""
400 Bad Request
    -> email or pw 없음, email이미 존재(회원가입), email 존재X + 비밀번호 틀림(로그인) 
    -> 토큰 만료, 토큰 유효성
401 Unauthorized
403 Forbidden
404 Not Found
405 Method not allowed

500 Internal Error
502 Bad Gateway
504 Timeout

200 OK
201 Created
"""


class APIException(Exception):
    status_code: int
    code: str
    message: str
    detail: str
    exception: Exception

    # result_data: dict 도 필요할 수 도

    def __init__(
            self,
            *,
            status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
            code: str = "0000000",
            message: str = "서버에 문제가 발생했습니다.",
            detail: str = None,
            exception: Exception = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message  # 유저에게 바로 보여주는 메세지
        self.detail = detail  # 에러마다의 해당 정보를 보여주는 메세지
        self.exception = exception
        # self.result_data: dict 도 필요할 수 도
        super().__init__(exception)


# 400
class BadRequestException(APIException):

    def __init__(self, *, code_number: [str, int] = "0", detail: str = None, exception: Exception = None):
        if not isinstance(code_number, str):
            code_number = str(code_number)

        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=f"{status.HTTP_400_BAD_REQUEST}{code_number.zfill(4)}",
            message="잘못된 접근입니다.",
            detail=detail,
            exception=exception
        )


class TokenDecodeException(BadRequestException):

    def __init__(self, exception: Exception = None):
        super().__init__(
            code_number=1,
            detail="잘못된 토큰으로 접속하였습니다.",
            exception=exception
        )


class TokenExpiredException(BadRequestException):
    def __init__(self, exception: Exception = None):
        super().__init__(
            code_number=2,
            detail="토큰이 만료되었습니다.",
            exception=exception
        )


class EmailAlreadyExistsException(BadRequestException):
    def __init__(self, exception: Exception = None):
        super().__init__(
            code_number=3,
            detail="이미 존재하는 이메일 입니다.",
            exception=exception
        )


class IncorrectPasswordException(BadRequestException):
    def __init__(self, exception: Exception = None):
        super().__init__(
            code_number=4,
            detail="비밀번호가 틀렸습니다.",
            exception=exception
        )


class NoSupportException(BadRequestException):
    def __init__(self, exception: Exception = None):
        super().__init__(
            code_number=5,
            detail="지원하지 않는 타입입니다.",
            exception=exception
        )


class NoUserMatchException(BadRequestException):
    def __init__(self, exception: Exception = None):
        super().__init__(
            code_number=6,
            detail="매칭되는 유저정보가 없습니다.",
            exception=exception
        )


# 401
class NotAuthorized(APIException):

    def __init__(self, exception: Exception = None):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=f"{status.HTTP_401_UNAUTHORIZED}{'1'.zfill(4)}",
            message="로그인이 필요한 서비스 입니다.",
            detail=f"Authorization Required",
            exception=exception
        )


# 404
class NotFoundException(APIException):

    def __init__(self, *, code_number: [str, int] = "0", detail: str = None, exception: Exception = None):
        if not isinstance(code_number, str):
            code_number = str(code_number)

        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code=f"{status.HTTP_404_NOT_FOUND}{code_number.zfill(4)}",
            message="대상을 찾을 수 없습니다.",
            detail=detail,
            exception=exception
        )


class NotFoundUserException(NotFoundException):
    def __init__(self, user_id=None, exception: Exception = None):
        super().__init__(
            code_number=1,
            detail=f"Not found User ID: {user_id}",
            exception=exception
        )


class NotFoundEmail(NotFoundException):
    def __init__(self, email=None, exception: Exception = None):
        super().__init__(
            code_number=2,
            detail=f"Not found User Email: {email}",
            exception=exception
        )