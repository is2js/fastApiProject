from app.errors.exceptions import APIException, DBException
from app.models.mixins.errors import SQLAlchemyException
from app.pages.exceptions import TemplateException


async def exception_handler(exception: Exception):
    # 정의 안한 에러 -> 우리정의 APIException(기본 status_code 500, code 0000000, message 서버에 문제 발생) 객체로 변환하되
    # - exception 필드에 해당exception을 통째로 넣어주고
    # - detail은 str(e)값을 넣어준다.

    # if not isinstance(exception, (APIException, SQLAlchemyException)):
    # - 템플릿 에러도 강제변환 없이, 취급하는 것으로 간주하게 추가해준다.
    if not isinstance(exception, (APIException, SQLAlchemyException, DBException, TemplateException)):
        exception = APIException(exception=exception, detail=str(exception))
    ...
    return exception

