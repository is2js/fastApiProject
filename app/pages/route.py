from typing import Callable

from fastapi import HTTPException
from fastapi.routing import APIRoute
from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from app.errors.exceptions import APIException
from app.utils.http_utils import redirect


# from prometheus_client import Counter
# system_fail_count = Counter('system_fail_count', 'Counts the number of system fail')
class TemplateRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            app = request.app
            print(f"request.path_params >> {request.path_params}")

            try:
                return await original_route_handler(request)
            except Exception as e:
                if isinstance(e, APIException) and e.status_code == status.HTTP_401_UNAUTHORIZED:

                    # response = redirect(str(request.url_for('template_login', next=request.url), logout=True)
                    # response = redirect(f"/login?next={request.url}", logout=True)
                    response = redirect(str(request.url_for('discord_home')), logout=True)
                    return response

                raise e

            # except RedirectException as exc:
            # system_fail_count.inc()
            # app.logger.warning('{}'.format(exc.detail))
            # return RedirectResponse(exc.redirect_url)

        return custom_route_handler
