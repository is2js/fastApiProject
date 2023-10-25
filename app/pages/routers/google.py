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
    google_calendars = calendar_service.calendarList().list().execute()

    calendars = []
    for calendar in google_calendars['items']:
        # model을 담기 전, dict list로 뽑아본다.
        calendars.append(dict(
            # google_account_id=user.get_oauth_account(SnsType.GOOGLE).id,  # 추후 FK
            user_id=user.id,  # 추후 FK -> 구글 계정별 calendar도 되지만, 우리는 google계정 1개만 사용 + Users에 딸린 calendar를 바로 찾을 수 있다.
            calendar_id=calendar['id'],
            name=calendar['summary'],
            is_deleted=calendar.get('deleted', False),  # "deleted"키가 포함되어있고, True면 삭제 된 것. 없을 수 있어서 .get()
        ))

    # print(f"current_cals['items'] >> {current_cals['items']}")

    # [
    #     {
    #         "kind":"calendar#calendarListEntry",
    #         "etag":"\"1657577269858000\"",
    #         "id":"addressbook#contacts@group.v.calendar.google.com",
    #         "summary":"�깮�씪",
    #         "description":"Google 二쇱냼濡앹뿉 �벑濡앸맂 �궗�엺�뱾�쓽 �깮�씪, 湲곕뀗�씪, 湲고� �씪�젙 �궇吏쒕�� �몴�떆�빀�땲�떎.",
    #         "timeZone":"Asia/Seoul",
    #         "summaryOverride":"Contacts",
    #         "colorId":"17",
    #         "backgroundColor":"#9a9cff",
    #         "foregroundColor":"#000000",
    #         "accessRole":"reader",
    #         "defaultReminders":[
    #
    #         ],
    #         "conferenceProperties":{
    #             "allowedConferenceSolutionTypes":[
    #                 "hangoutsMeet"
    #             ]
    #         }
    #     },
    #     {
    #         "kind":"calendar#calendarListEntry",
    #         "etag":"\"1657580828523000\"",
    #         "id":"ko.south_korea#holiday@group.v.calendar.google.com",
    #         "summary":"���븳誘쇨뎅�쓽 �쑕�씪",
    #         "description":"���븳誘쇨뎅�쓽 怨듯쑕�씪",
    #         "timeZone":"Asia/Seoul",
    #         "summaryOverride":"���븳誘쇨뎅�쓽 �쑕�씪",
    #         "colorId":"17",
    #         "backgroundColor":"#9a9cff",
    #         "foregroundColor":"#000000",
    #         "accessRole":"reader",
    #         "defaultReminders":[
    #
    #         ],
    #         "conferenceProperties":{
    #             "allowedConferenceSolutionTypes":[
    #                 "hangoutsMeet"
    #             ]
    #         }
    #     },
    # ]

    context = {
        'calendars': calendars
    }
    return render(request, "dashboard/calendar-sync.html", context=context)
