from app.errors.exceptions import APIException


async def exception_handler(exception: Exception):
    # 정의 안한 에러 -> 우리정의 APIException(기본 status_code 500, code 0000000, message 서버에 문제 발생) 객체로 변환하되
    # - exception 필드에 해당exception을 통째로 넣어주고
    # - detail은 str(e)값을 넣어준다.
    if not isinstance(exception, APIException):
        exception = APIException(exception=exception, detail=str(exception))
    # ...
    return exception

