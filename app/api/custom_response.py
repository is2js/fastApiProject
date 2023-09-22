import typing
from fastapi.responses import JSONResponse

from app.common.config import config


class CustomJSONResponse(JSONResponse):
    def render(self, content: typing.Any) -> bytes:
        return super(CustomJSONResponse, self).render({
            "data": content,
            'version': config.APP_VERSION,
        })