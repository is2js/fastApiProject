import json
import typing

from fastapi import Body
from pydantic import error_wrappers, BaseModel, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, HTMLResponse, Response

from app.common.config import config
from app.pages.routers import templates


class CustomJSONResponse(JSONResponse):
    def render(self, content: typing.Any) -> bytes:
        return super(CustomJSONResponse, self).render({
            "data": content,
            'version': config.APP_VERSION,
        })


def is_htmx(request: Request):
    return request.headers.get("hx-request") == 'true'


def redirect(path, cookies: dict = {}, logout=False, is_htmx=False):
    # htmx 요청을 redirect할 경우 -> RedirectResponse (X) Response + 302 + HX-Redirect에 path
    if is_htmx:
        response: Response = Response(status_code=302)
        response.status_code = 302
        response.headers['HX-Redirect'] = str(path) if not isinstance(path, str) else path
    else:
        response = RedirectResponse(path, status_code=302)

    for k, v in cookies.items():
        response.set_cookie(key=k, value=v, httponly=True)

    if logout:
        # response.set_cookie(key='session_ended', value=str(1), httponly=True)
        response.delete_cookie('Authorization')

    return response


def render(request, template_name, context={}, status_code: int = 200, cookies: dict = {},
           hx_trigger: str = None,
           # htmx 관련 response headers 추가. hx_target: str = None, hx_swap: str = None, hx_push_url: str = None,
           ):
    # ctx = context.copy()
    # ctx.update({"request": request})
    ctx = {
        'request': request,
        'user': request.state.user,
        **context
    }

    # dashboard에서 bog_guild_count를 항상 표시하기 위해
    # request.state에 discord의 bot의 guild count를 요청하면, ctx에 박아서
    # 뿌려주게 함.
    if request.state.bot_guild_count:
        ctx.update({'bot_guild_count': request.state.bot_guild_count})

    t = templates.get_template(template_name)
    html_str = t.render(ctx)
    response = HTMLResponse(html_str, status_code=status_code)

    # htmx 관련 response headers에 HX-trigger 추가
    if hx_trigger:
        response.headers["HX-Trigger"] = hx_trigger

    response.set_cookie(key='darkmode', value=str(1))
    if len(cookies.keys()) > 0:

        # set httponly cookies
        for k, v in cookies.items():
            response.set_cookie(key=k, value=v, httponly=True)

    # delete coookies
    # for key in request.cookies.keys():
    #     response.delete_cookie(key)

    return response


def hx_vals_schema(schema: BaseModel):
    """
    route의 의존성 주입 함수로 사용

    view의 post with hx-vals를 -> Body(...)의 bytes문자열을 디코딩하여
    -> dict로 변환 -> try: Schema(**dict)로 넣어 validation
    -> except: 변환시 에러나면 errors = list 추가하여 반환
    => 튜플 (data, errors)를 반환하는데, Depends()에서는 튜플 언패킹이 안되어
       data_and_errors로 받아서, 함수내에서 data, errors = data_and_errors로 받아서 사용

    @router.post("/calendar_sync")
    async def hx_create_calendar_syncs(
        request: Request,
        is_htmx=Depends(is_htmx),
        data_and_errors=Depends(hx_vals_schema(CreateCalendarSyncsRequest)),
    ):
        data, errors = data_and_errors

    """

    def bytes_body_to_schema(body: bytes = Body(...)):
        # print(f"body >> {body}")
        # body >> b'guild_id=1161106117141725284'
        # body >> b'guild_id=1161106117141725284&member_count=3'

        # bytes.decode() -> 문자열로 디코딩
        # body_str = body.decode("utf-8")
        # body_str >> guild_id=1161106117141725284

        form_fields = {}
        for param in body.decode('utf-8').split('&'):
            key, value = param.split('=')
            form_fields[key] = value

        # form_fields >> {'guild_id': '1161106117141725284'}
        # form_fields >> {'guild_id': '1161106117141725284', 'member_count': '3'}
        # return form_fields

        # return schema(**form_fields)

        data = {}
        errors = []
        error_str = None

        try:
            data = schema(**form_fields).model_dump()
        # except error_wrappers.ValidationError as e:
        # `pydantic.error_wrappers:ValidationError` has been moved to `pydantic:ValidationError`.
        #   warnings.warn(f'`{import_path}` has been moved to `{new_location}`.')
        except ValidationError as e:
            error_str = e.json()

        if error_str is not None:
            try:
                errors = json.loads(error_str)
            except Exception as e:
                errors = [{"loc": "non_field_error", "msg": "Unknown error"}]

        # [{'type': 'missing', 'loc': ['loop_index'], 'msg': 'Field required', 'input': {'user_id': '3', 'calendar_id': '20'}, 'url': 'https://errors.pydantic.dev/2.3/v/missing'}]
        # return data, errors

        #     {% for error in errors %}
        #         <li>{% if error.loc[0] != "__root__" %}<b>{{ error.loc[0] }}</b>:{% endif %} {{ error.msg }}</li>
        #     {% endfor %}
        error_infos = ""
        for error in errors:
            error_info = "<li>"
            if error.get('loc')[0] != "__root__":
                error_infos += f"{error.get('loc')[0]}: {error.get('msg')}"
            else:
                error_infos += f"{error.get('msg')}"
            error_info += "</li>"

        return data, error_infos

    return bytes_body_to_schema
