from starlette import status


class SQLAlchemyException(Exception):
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
            message: str = "SQLAlchemy Mixin 사용이 잘못되었습니다.",
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


class CUDException(SQLAlchemyException):

    def __init__(self, *, code_number: [str, int] = "0", detail: str = None, exception: Exception = None):
        if not isinstance(code_number, str):
            code_number = str(code_number)

        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code=f"{status.HTTP_400_BAD_REQUEST}{code_number.zfill(4)}",
            message="[Mixin Error] CUD 사용 에러 입니다.",
            detail=detail,
            exception=exception
        )


class TransactionException(CUDException):

    def __init__(self, exception: Exception = None):
        super().__init__(
            code_number=1,
            detail="외부 session이 없다면, CUD시 TR생성을 위해 auto_commit=True를 입력해주세요.",
            exception=exception
        )
