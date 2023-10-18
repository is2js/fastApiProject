from fastapi import APIRouter
from starlette.requests import Request

from app.models import Users
from app.libs.auth.oauth_clients.google import CALENDAR_SCOPES, get_google_service_name_by_scopes
from app.models import SnsType, RoleName
from app.pages.decorators import oauth_login_required, role_required
from app.pages.route import TemplateRoute
from app.utils.http_utils import render

router = APIRouter()


@router.get("/calendar_sync")
# @oauth_login_required(SnsType.GOOGLE)
@oauth_login_required(SnsType.GOOGLE, required_scopes=CALENDAR_SCOPES)
@role_required(RoleName.STAFF)
async def sync_calendar(request: Request):
    user: Users = request.state.user
    service_name = get_google_service_name_by_scopes(CALENDAR_SCOPES)
    calendar_service = await user.get_google_service(service_name)
    current_cals = calendar_service.calendarList().list().execute()
    print(f"current_cals['items'] >> {current_cals['items']}")

    return render(request, "dashboard/calendar-sync.html")


    # "GET /auth/callback/google?error=access_denied&state=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJuZXh0IjoiaHR0cDovL2xvY2FsaG9zdDo4MDAwL2dvb2dsZS9jYWxlbmRhcl9zeW5jIiwiYXVkIjoiZmFzdGFwaS11c2VyczpvYXV0aC1zdGF0ZSIsImV4cCI6MTY5NzYxNTg3OH0.SL54dP8E8qJmgvQ2tDnTyxRK7vcGNDPtRJKJr_MKFKY HTTP/1.1" 400 Bad Request