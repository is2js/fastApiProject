import typing

from fastapi import Body
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


def render(request, template_name, context={}, status_code: int = 200, cookies: dict = {}):
    # ctx = context.copy()
    # ctx.update({"request": request})
    ctx = {
        'request': request,
        'user': request.state.user,
        **context
    }
    if request.state.bot_guild_count:
        ctx.update({'bot_guild_count': request.state.bot_guild_count})

    t = templates.get_template(template_name)
    html_str = t.render(ctx)
    response = HTMLResponse(html_str, status_code=status_code)

    response.set_cookie(key='darkmode', value=str(1))
    if len(cookies.keys()) > 0:

        # set httponly cookies
        for k, v in cookies.items():
            response.set_cookie(key=k, value=v, httponly=True)

    # delete coookies
    # for key in request.cookies.keys():
    #     response.delete_cookie(key)

    return response


def hx_vals_schema(schema):
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

        return schema(**form_fields)

    return bytes_body_to_schema
