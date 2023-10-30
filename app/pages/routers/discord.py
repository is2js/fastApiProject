import datetime

import discord
from fastapi import APIRouter, Depends, HTTPException
from fastapi_users import BaseUserManager, models
from fastapi_users.exceptions import UserAlreadyExists
from fastapi_users.router import ErrorCode
from fastapi_users.router.oauth import generate_state_token
from starlette import status
from starlette.requests import Request

from app.common.config import DISCORD_CLIENT_ID, JWT_SECRET, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from app.libs.auth.oauth_clients import get_oauth_client
from app.libs.auth.oauth_clients.discord import DiscordClient
from app.libs.auth.oauth_clients.google import CALENDAR_SCOPES
from app.libs.auth.strategies import get_jwt_strategy
from app.libs.auth.transports import get_cookie_redirect_transport
from app.libs.discord.bot.ipc_client import discord_ipc_client
from app.pages.exceptions import DiscordBotNotConnectedException
from app.pages.oauth_callback import get_discord_callback, DiscordAuthorizeCallback
from app.models import SnsType, RoleName,  OAuthAccount
from app.api.dependencies.auth import get_user_manager
from app.errors.exceptions import TokenExpiredException, OAuthProfileUpdateFailException
from app.pages.decorators import oauth_login_required, role_required
from app.schemas.discord import GuildLeaveRequest
from app.utils.date_utils import D
from app.utils.http_utils import render, redirect, is_htmx, hx_vals_schema

# router = APIRouter(route_class=DiscordRoute)
router = APIRouter()


@router.get("/")
async def discord_home(request: Request):
    """
    `Discord Bot Dashboard Home`
    """

    # from google.oauth2.credentials import Credentials
    # from googleapiclient.discovery import build

    # user = request.state.user

    # 비로그인 허용이지만, 1) 로그인 된 상태고 2) 구글 계정 정보가 있을 때,
    # => 구글 계정정보 중 [access_token + refresh_token] + 구글 config정보 [GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET]
    #    + cred객체 생성후  build객체로 [서비스 요청할 scopes 범위] 총 5개 인자로 creds를 만든다.
    # if user and user.get_oauth_access_token(SnsType.GOOGLE) and await user.has_google_creds_and_scopes(CALENDAR_SCOPES):
    #     creds = await user.get_google_creds()
    #     calendar_service = build('calendar', 'v3', credentials=creds)
    #     current_cals = calendar_service.calendarList().list().execute()
    #     print(f"current_cals['items'] >> {current_cals['items']}")
    #



        # skewed_expiry = self.expiry - _helpers.REFRESH_THRESHOLD
        # TypeError: unsupported operand type(s) for -: 'str' and 'datetime.timedelta'
        # current_cals['items'] >> [{'kind': 'calendar#calendarListEntry', 'etag': '"1657577269858000"', 'id': 'addressbook#contacts@group.v.calendar.google.com', 'summary': '�깮�씪', 'description': 'Google 二쇱냼濡앹뿉 �벑濡앸맂 �궗�엺�뱾�쓽 �깮�씪, 湲곕뀗�씪, 湲고� �씪�젙 �궇吏쒕�� �몴�떆�빀�땲�떎.', 'timeZone': 'Asia/Seoul', 'summaryOverride': 'Contacts', 'colorId': '17', 'backgroundColor': '#9a9cff', 'foregroundColor': '#000000', 'accessRole': 'reader', 'defaultReminders': [], 'conferenceProperties': {'allowedConferenceSolutionTypes': ['hangoutsMeet']}}, {'kind': 'calendar#calendarListEntry', 'etag': '"1657580828523000"', 'id': 'ko.south_korea#holiday@group.v.calendar.google.com', 'summary': '���븳誘쇨뎅�쓽 �쑕�씪', 'description': '���븳誘쇨뎅�쓽 怨듯쑕�씪', 'timeZone': 'Asia/Seoul', 'summaryOverride': '���븳誘쇨뎅�쓽 �쑕�씪', 'colorId': '17', 'backgroundColor': '#9a9cff', 'foregroundColor': '#000000', 'accessRole': 'reader', 'defaultReminders': [], 'conferenceProperties': {'allowedConferenceSolutionTypes': ['hangoutsMeet']}}, {'kind': 'calendar#calendarListEntry', 'etag': '"1657580830000000"', 'id': 'tingstyle1@gmail.com', 'summary': 'tingstyle1@gmail.com', 'timeZone': 'Asia/Seoul', 'colorId': '19', 'backgroundColor': '#c2c2c2', 'foregroundColor': '#000000', 'selected': True, 'accessRole': 'owner', 'defaultReminders': [{'method': 'popup', 'minutes': 30}], 'notificationSettings': {'notifications': [{'type': 'eventCreation', 'method': 'email'}, {'type': 'eventChange', 'method': 'email'}, {'type': 'eventCancellation', 'method': 'email'}, {'type': 'eventResponse', 'method': 'email'}]}, 'primary': True, 'conferenceProperties': {'allowedConferenceSolutionTypes': ['hangoutsMeet']}}]


        # google_account: OAuthAccount = user.get_oauth_account(SnsType.GOOGLE)

        # creds = Credentials.from_authorized_user_info(
        #     info=dict(
        #         token=google_account.access_token,
        #         refresh_token=google_account.refresh_token,
        #         client_id=GOOGLE_CLIENT_ID,
        #         client_secret=GOOGLE_CLIENT_SECRET,
        #         scopes=["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/calendar.events"],
        #     )
        # )

        # request.session['scopes'] = ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/calendar.events"],

        # print(f"creds.to_json() >> {creds.to_json()}")
        # {"token": "ya29.a0AfB_byByOvMA-SAPdTeGm5l0m-8KRz2VyKp2sfzywEVET7h_eyXhDeUgCc_biqM2lL7aYCofItTn_BvGE7who26vKCeDXygjM8NKs51HrfN6wtWH5wNy3yjXkLsO2I0-mBo_kBV3JJZqt5HN9Far0MM595sJGokgljKWaCgYKAdoSARMSFQGOcNnCidI5bFBF40m-_22UWGahkw0171",
        # "refresh_token": "1//0exwiXWbWorZVCgYIARAAGA4SNwF-L9IrIUlrd3NEga5mc05ODo_CY1alWJjwp_HYsrqZzVCtZuh8JOX02q83LHsEHaH5UE3uWr0",
        # "token_uri": "https://oauth2.googleapis.com/token",
        # "client_id": "622493818735-g9gp89jisli2igf2qhkmanp4vgdtkbs4.apps.googleusercontent.com",
        # "client_secret": "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",
        # "scopes": ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/calendar.events"],
        # "expiry": "2023-10-17T07:41:11.290729Z"}
        # 2023-10-17T07:41:31.317022070Z
        

        # print(f"creds >> {creds}")
        # creds >> <google.oauth2.credentials.Credentials object at 0x0000017E670BB0A0>

        # google_client = get_oauth_client(SnsType.GOOGLE)
        # refreshed_access_token = await google_client.refresh_token(google_account.refresh_token)
        # print(f"token >> {refreshed_access_token}")
        # token >> {'access_token': 'ya29.a0AfB_byBVs9aGnup0mC95okB0R-CMVKjIZhTzHqciJQWsjhvv44QHcnNUofyilz2eOFk1bYAKZ94B5c4A6f_FgzNhv0YXV11YAzaCPPlm26BfyTUJrT2A0hQz3fR5pa7hF17wFwmDA6IAu_sdfukIfD9I4Difpr9RdRJXaCgYKAZ0SARMSFQGOcNnClCFeAErrUax3U9DcG6lM_A0171', 'expires_in': 3599, 'scope': 'openid https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/user.phonenumbers.read https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/user.birthday.read https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/user.gender.read', 'token_type': 'Bearer', 'id_token': 'eyJhbGciOiJSUzI1NiIsImtpZCI6IjdkMzM0NDk3NTA2YWNiNzRjZGVlZGFhNjYxODRkMTU1NDdmODM2OTMiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20iLCJhenAiOiI2MjI0OTM4MTg3MzUtZzlncDg5amlzbGkyaWdmMnFoa21hbnA0dmdkdGticzQuYXBwcy5nb29nbGV1c2VyY29udGVudC5jb20iLCJhdWQiOiI2MjI0OTM4MTg3MzUtZzlncDg5amlzbGkyaWdmMnFoa21hbnA0dmdkdGticzQuYXBwcy5nb29nbGV1c2VyY29udGVudC5jb20iLCJzdWIiOiIxMDg1MDk4NDM1Mzc2NTI4MDM5NDUiLCJlbWFpbCI6InRpbmdzdHlsZTFAZ21haWwuY29tIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsImF0X2hhc2giOiJ5MzZEQjQxRWlsUVYxZm9QUXcyc2NRIiwiaWF0IjoxNjk3NDY2MTY2LCJleHAiOjE2OTc0Njk3NjZ9.eM3VThkyYrLNzX2sMmYARveSr4BChyHKBFWmvHdHtNdL-m75Qn0NHvX1CQF4Ep1mm9vjocVLVYb8PKUB4TiEwq56GOFnfITePwZkYV0DiGNp0GoSNDNCMUnQ672t_K68zZvWe9o0Aw5OeKAn58EH5BPjX3f90kamlLGYErcI-Ztyu3NzMuD9yYcVqY0wGIZ9O0UuZap5LsF1Fd6DX0BHombxVkqk0Gt-iJIGbLGhvOjTnIPwPExUduQzq-_x4Rg_Iv8Q-at1zNQ8njzwcLAouIsd2o2HZL9kc0y2Qqlw7QTngXw4c0uAnJ3PpmQ1QYQNoWCPRSKdykzinnnE-nOKyA', 'expires_at': 1697469766}

        # calendar_service = build('calendar', 'v3', credentials=creds)


        # Call the Calendar API
        #### events ####
        # now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time

        # print('Getting the upcoming 10 events')

        # events_result = calendar_service.events().list(
        #     calendarId='primary',
        #     timeMin=now,
        #     maxResults=10, singleEvents=True,
        #     orderBy='startTime') \
        #     .execute()
        #
        # events = events_result.get('items', [])

        # print(f"events >> {events}")
        # events >> [
        # {
        #     "kind":"calendar#event",
        #     "etag":"\"3222264627100000\"",
        #     "id":"chh68oj16som8b9g69ijcb9kc5j6ab9o60r6cb9g61ij8oj275im8e1l60_20231020T043000Z",
        #     "status":"confirmed",
        #     "htmlLink":"https://www.google.com/calendar/event?eid=Y2hoNjhvajE2c29tOGI5ZzY5aWpjYjlrYzVqNmFiOW82MHI2Y2I5ZzYxaWo4b2oyNzVpbThlMWw2MF8yMDIzMTAyMFQwNDMwMDBaIHRpbmdzdHlsZTFAbQ",
        #     "created":"2020-03-02T23:26:11.000Z",
        #     "updated":"2021-01-20T08:45:13.550Z",
        #     "summary":"마통상품20만원 출금",
        #     "colorId":"5",
        #     "creator":{
        #         "email":"tingstyle1@gmail.com",
        #         "self":true
        #     },
        #     "organizer":{
        #         "email":"tingstyle1@gmail.com",
        #         "self":true
        #     },
        #     "start":{
        #         "dateTime":"2023-10-20T13:30:00+09:00",
        #         "timeZone":"Asia/Seoul"
        #     },
        #     "end":{
        #         "dateTime":"2023-10-20T14:30:00+09:00",
        #         "timeZone":"Asia/Seoul"
        #     },
        #     "recurringEventId":"chh68oj16som8b9g69ijcb9kc5j6ab9o60r6cb9g61ij8oj275im8e1l60",
        #     "originalStartTime":{
        #         "dateTime":"2023-10-20T13:30:00+09:00",
        #         "timeZone":"Asia/Seoul"
        #     },
        #     "iCalUID":"chh68oj16som8b9g69ijcb9kc5j6ab9o60r6cb9g61ij8oj275im8e1l60@google.com",
        #     "sequence":0,
        #     "reminders":{
        #         "useDefault":true
        #     },
        #     "eventType":"default"
        # },
        # ]

        #### calendar list ####
        # current_cals = calendar_service.calendarList().list().execute()
        # print(f"current_cals >> {current_cals}")
        # {
        #     "kind":"calendar#calendarList",
        #     "etag":"\"p328bp1t5gro820o\"",
        #     "nextSyncToken":"CJC8h6WG8IEDEhR0aW5nc3R5bGUxQGdtYWlsLmNvbQ==",
        #     "items":[
        #         {
        #             "kind":"calendar#calendarListEntry",
        #             "etag":"\"1657577269858000\"",
        #             "id":"addressbook#contacts@group.v.calendar.google.com",
        #             "summary":"생일",
        #             "description":"Google 주소록에 등록된 사람들의 생일, 기념일, 기타 일정 날짜를 표시합니다.",
        #             "timeZone":"Asia/Seoul",
        #             "summaryOverride":"Contacts",
        #             "colorId":"17",
        #             "backgroundColor":"#9a9cff",
        #             "foregroundColor":"#000000",
        #             "accessRole":"reader",
        #             "defaultReminders":[
        #
        #             ],
        #             "conferenceProperties":{
        #                 "allowedConferenceSolutionTypes":[
        #                     "hangoutsMeet"
        #                 ]
        #             }
        #         },
        #         {
        #             "kind":"calendar#calendarListEntry",
        #             "etag":"\"1657580828523000\"",
        #             "id":"ko.south_korea#holiday@group.v.calendar.google.com",
        #             "summary":"대한민국의 휴일",
        #             "description":"대한민국의 공휴일",
        #             "timeZone":"Asia/Seoul",
        #             "summaryOverride":"대한민국의 휴일",
        #             "colorId":"17",
        #             "backgroundColor":"#9a9cff",
        #             "foregroundColor":"#000000",
        #             "accessRole":"reader",
        #             "defaultReminders":[
        #
        #             ],
        #             "conferenceProperties":{
        #                 "allowedConferenceSolutionTypes":[
        #                     "hangoutsMeet"
        #                 ]
        #             }
        #         },
        #         {
        #             "kind":"calendar#calendarListEntry",
        #             "etag":"\"1657580830000000\"",
        #             "id":"tingstyle1@gmail.com",
        #             "summary":"tingstyle1@gmail.com",
        #             "timeZone":"Asia/Seoul",
        #             "colorId":"19",
        #             "backgroundColor":"#c2c2c2",
        #             "foregroundColor":"#000000",
        #             "selected":true,
        #             "accessRole":"owner",
        #             "defaultReminders":[
        #                 {
        #                     "method":"popup",
        #                     "minutes":30
        #                 }
        #             ],
        #             "notificationSettings":{
        #                 "notifications":[
        #                     {
        #                         "type":"eventCreation",
        #                         "method":"email"
        #                     },
        #                     {
        #                         "type":"eventChange",
        #                         "method":"email"
        #                     },
        #                     {
        #                         "type":"eventCancellation",
        #                         "method":"email"
        #                     },
        #                     {
        #                         "type":"eventResponse",
        #                         "method":"email"
        #                     }
        #                 ]
        #             },
        #             "primary":true,
        #             "conferenceProperties":{
        #                 "allowedConferenceSolutionTypes":[
        #                     "hangoutsMeet"
        #                 ]
        #             }
        #         }
        #     ]
        # }



    return render(request, "dashboard/home.html")


@router.get("/guilds")
@oauth_login_required(SnsType.DISCORD)
@role_required(RoleName.ADMINISTRATOR)
# @permission_required(Permissions.ADMIN)
async def guilds(request: Request):
    access_token = request.state.user.get_oauth_access_token(SnsType.DISCORD)

    oauth_client: DiscordClient = get_oauth_client(SnsType.DISCORD)
    user_guilds = await oauth_client.get_guilds(access_token)

    # TODO: dipc client class를 만들어서, 요청시 예외처리 넣기 ?
    # TODO: ipc client도 lifespan에 넣어서, 전역변수로서 활용해보기
    # TODO: ipc client도 비동기 on_ready? https://pypi.org/project/discord-ipc/
    #       - 이전버전엔 bot class에서 처리 https://pypi.org/project/discord-ipc/0.0.4/
    #       - 현재clinet의 구식버전: https://github.com/lgaan/discord-ext-ipc
    try:
        guild_ids = await discord_ipc_client.request('guild_ids')
    except Exception as e:
        # "[Errno 10061] Connect call failed ('127.0.0.1', 20000)"
        raise DiscordBotNotConnectedException(
            message='현재 discord bot이 연결되지 않아 사용할 수 없습니다.',
            exception=e,
        )

    # guild_ids.response >> {'guild_ids': [1156511536316174368]}
    guild_ids = guild_ids.response['guild_ids']

    # https://discord.com/developers/docs/resources/user#get-current-user-guilds
    for guild in user_guilds:
        # 해당user의 permission으로 guild 관리자인지 확인
        # (1) discord.Permissions( guild['permissions'] ).administrator   or  (2) guild['owner']
        is_admin: bool = discord.Permissions(guild['permissions']).administrator or guild.get('owner')
        if not is_admin:
            continue

        # (2) icon 간편주소를 img주소로 변경
        if guild.get('icon', None):
            guild['icon'] = 'https://cdn.discordapp.com/icons/' + guild['id'] + '/' + guild['icon']
        else:
            guild['icon'] = 'https://cdn.discordapp.com/embed/avatars/0.png'

        # (3) user의 guild id가 bot에 포함되면, use_bot 속성에 True, 아니면 False를 할당하자.
        # => user_guilds의 guild마다 id는 string으로 적혀있으니 int로 변환해서 확인한다. (서버반환은 guild_ids는 int)
        guild['use_bot'] = (int(guild['id']) if isinstance(guild['id'], str) else guild['id']) in guild_ids

        # (4) 개별guild 접속에 필요한 guild['id'] -> guild['url] 만들어서 넘겨주기
        guild['url'] = str(request.url_for('get_guild', guild_id=guild['id']))

    # bool을 key로 주면, False(0) -> True(1) 순으로 가므로, reverse까지 해줘야함
    user_guilds.sort(key=lambda x: x['use_bot'], reverse=True)

    context = {
        'user_guilds': user_guilds,
    }

    return render(
        request,
        "dashboard/guilds.html",
        context=context
    )


@router.get("/guilds/{guild_id}")
@oauth_login_required(SnsType.DISCORD)
async def get_guild(request: Request, guild_id: int):
    ...
    guild_stats = await discord_ipc_client.request('guild_stats', guild_id=guild_id)
    guild_stats = guild_stats.response  # 비었으면 빈 dict

    # user 관리 서버 중, bot에 없는 guild -> [bot 추가 url with state에 돌아올 주소 encode ]을 만들어준다.
    if not guild_stats:
        return redirect(
            f'https://discord.com/oauth2/authorize?'
            f'&client_id={DISCORD_CLIENT_ID}'
            f'&scope=bot&permissions=8'
            f'&guild_id={guild_id}'
            f'&response_type=code'
            f'&redirect_uri={str(request.url_for("template_oauth_callback", sns_type=SnsType.DISCORD.value))}'
            f'&state={generate_state_token(dict(next=str(request.url)), JWT_SECRET)}'
        )

    return render(request, 'dashboard/guild-detail.html', context={**guild_stats})


@router.post("/guilds/delete")
@oauth_login_required(SnsType.DISCORD)
async def hx_delete_guild(
        request: Request,
        # guild_id: int = Form(...),
        # body: GuildLeaveRequest, # 422 Entity error <- hx_vals를 pydantic이 route에서 바로 못받는다.
        # body = Body(...),
        # body >> b'guild_id=1161106117141725284&member_count=3'
        body=Depends(hx_vals_schema(GuildLeaveRequest)),
        is_htmx=Depends(is_htmx),
):
    # print(f"body >> {body}")
    # body >> guild_id=1161106117141725284
    # body >> guild_id=1161106117141725284 member_count=3

    # leave_guild = await discord_ipc_client.request('leave_guild', guild_id=guild_id)
    leave_guild = await discord_ipc_client.request('leave_guild', guild_id=body.guild_id)
    leave_guild = leave_guild.response

    # user 관리 서버 중, bot에 없는 guild -> [bot 추가 url]을 만들어준다.
    if not leave_guild['success']:
        raise

    # return redirect(request.url_for('guilds'))
    return redirect(request.url_for('guilds'), is_htmx=is_htmx)


# @app.route("/dashboard")
# async def dashboard():
# 	if not await discord.authorized:
# 		return redirect(url_for("login"))
#
# 	guild_count = await ipc_client.request("get_guild_count")
# 	guild_ids = await ipc_client.request("get_guild_ids")
#
# 	user_guilds = await discord.fetch_guilds()
#
# 	guilds = []
#
# 	for guild in user_guilds:
# 		if guild.permissions.administrator:
# 			guild.class_color = "green-border" if guild.id in guild_ids else "red-border"
# 			guilds.append(guild)
#
# 	guilds.sort(key = lambda x: x.class_color == "red-border")
# 	name = (await discord.fetch_user()).name
# 	return await render_template("dashb


@router.get("/callback", name='discord_callback')
async def discord_callback(
        request: Request,
        # code: str,
        # state: Optional[str] = None,
        access_token_and_next_url: DiscordAuthorizeCallback = Depends(
            get_discord_callback(route_name='discord_callback')
        ),  # 인증서버가 돌아올떄 주는 code와 state를 내부에서 받아 처리
        user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
):
    """
    `Discord callback for Developer OAuth Generated URL`
    """
    oauth2_token, next_url = access_token_and_next_url

    # 2. 응답받은 oauth2_token객체로 만료를 확인하고
    if oauth2_token.is_expired():
        raise TokenExpiredException()

    oauth_client = get_oauth_client(SnsType.DISCORD)
    account_id, account_email = await oauth_client.get_id_email(oauth2_token["access_token"])

    # 4-1. fastapi-users callback route 로직
    # - venv/Lib/site-packages/fastapi_users/router/oauth.py
    try:
        user = await user_manager.oauth_callback(
            oauth_name='discord',
            access_token=oauth2_token.get("access_token"),
            account_id=account_id,
            account_email=account_email,
            expires_at=oauth2_token.get("expires_at"),
            refresh_token=oauth2_token.get("refresh_token"),
            request=request,
            associate_by_email=True,  # sns로그인시, 이미 email가입이 있어도, oauth_account로 등록을 허용한다.
            # is_verified_by_default=False,
            is_verified_by_default=True,  # sns로그인한 사람이라면 email인증을 안거쳐도 된다고 하자.
        )

    except UserAlreadyExists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorCode.OAUTH_USER_ALREADY_EXISTS,
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorCode.LOGIN_BAD_CREDENTIALS,
        )

    # 4-3. backend에서 oauth_client에서 못가져온 추가정보 가져오는 로직도 추가한다.
    # - app/libs/auth/backends/oauth/discord.py
    try:
        oauth_client = get_oauth_client(SnsType.DISCORD)
        if profile_info := await oauth_client.get_profile_info(oauth2_token["access_token"]):
            await user.update(
                auto_commit=True,
                **profile_info,
                sns_type='discord',
                last_seen=D.datetime(),  # on_after_login에 정의된 로직도 가져옴
            )
    except Exception as e:
        raise OAuthProfileUpdateFailException(obj=user, exception=e)

    # 5. 쿠키용 user_token을 jwt encoding하지않고, fastapi-users의 Strategy객체로 encoding하기
    # token_data = UserToken.model_validate(user).model_dump(exclude={'hashed_password', 'marketing_agree'})
    # token = await create_access_token(data=token_data)
    jwt_strategy = get_jwt_strategy()
    user_token_for_cookie = await jwt_strategy.write_token(user)
    # {
    #   "sub": "4",
    #   "aud": [
    #     "fastapi-users:auth"
    #   ],
    #   "exp": 1696397563
    # }

    # 6. 직접 Redirect Response를 만들지 않고, fastapi-users의 쿠키용 Response제조를 위한 Cookie Transport를 Cusotm해서 Response를 만든다.
    # 3. 데이터를 뿌려주는 api router로 Redirect시킨다.
    # return RedirectResponse(url='/guilds')
    # try:
    #     decode_jwt(state, JWT_SECRET, [STATE_TOKEN_AUDIENCE])
    #     next_url = decode_jwt(state, JWT_SECRET, [STATE_TOKEN_AUDIENCE])['next'] if state \
    #         else str(request.url_for('discord_dashboard'))
    # except jwt.DecodeError:
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    cookie_redirect_transport = get_cookie_redirect_transport(
        # redirect_url=request.url_for('guilds')  # 로그인 성공 후 cookie정보를 가지고 돌아갈 곳.
        redirect_url=next_url  # 로그인 성공 후 cookie정보를 가지고 돌아갈 곳.
        # redirect_url=request.url_for('discord_dashboard')  # 로그인 성공 후 cookie정보를 가지고 돌아갈 곳.
    )
    response = await cookie_redirect_transport.get_login_response(user_token_for_cookie)

    return response
