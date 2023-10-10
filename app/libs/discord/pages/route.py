from typing import Callable

from fastapi import HTTPException
from fastapi.routing import APIRoute
from fastapi_users.router.oauth import generate_state_token
from starlette import status
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse

from app.common.config import JWT_SECRET
from app.libs.auth.oauth_clients import get_oauth_client
from app.models import SnsType


# from prometheus_client import Counter
# system_fail_count = Counter('system_fail_count', 'Counts the number of system fail')

class DiscordRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            app = request.app
            try:
                return await original_route_handler(request)
            except Exception as e:
                # if exc.status_code == status.HTTP_401_UNAUTHORIZED:
                if isinstance(e, HTTPException) and e.status_code == status.HTTP_401_UNAUTHORIZED:

                    state_data = dict(next=str(request.url))
                    state = generate_state_token(state_data, JWT_SECRET) if state_data else None

                    oauth_client = get_oauth_client(SnsType.DISCORD)
                    authorization_url: str = await oauth_client.get_authorization_url(
                        redirect_uri=str(request.url_for('discord_callback')),
                        state=state
                    )
                    return RedirectResponse(authorization_url)

                raise e

            # except RedirectException as exc:
            # system_fail_count.inc()
            # app.logger.warning('{}'.format(exc.detail))
            # return RedirectResponse(exc.redirect_url)

        return custom_route_handler
