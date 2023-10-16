from starlette import status


class TemplateException(Exception):
    status_code: int
    code: str
    message: str
    detail: str
    exception: Exception

    def __init__(
            self,
            *,
            status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
            code: str = "0000000",
            message: str = "템플릿 서버에 문제가 발생했습니다.",
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


# 403 FORBIDDEN
class ForbiddenException(TemplateException):
    def __init__(self, *, code_number: [str, int] = "0", detail: str = None, exception: Exception = None):
        if not isinstance(code_number, str):
            code_number = str(code_number)

        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code=f"{status.HTTP_403_FORBIDDEN}{code_number.zfill(4)}",
            message="접근 권한이 없습니다.",
            detail=detail,
            exception=exception,
        )
