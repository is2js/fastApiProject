from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from app.database.conn import db
from app.models import Users, UserCalendars, CalendarType, CalendarSyncs
from app.libs.auth.oauth_clients.google import CALENDAR_SCOPES, google_scopes_to_service_name
from app.models import SnsType, RoleName
from app.pages.decorators import oauth_login_required, role_required
from app.schemas.google import CreateCalendarSyncsRequest, DeleteCalendarSyncsRequest
from app.utils.http_utils import render, hx_vals_schema, redirect, is_htmx

router = APIRouter()


@router.get("/calendar_sync")
# @oauth_login_required(SnsType.GOOGLE)
@oauth_login_required(SnsType.GOOGLE, required_scopes=CALENDAR_SCOPES)
@role_required(RoleName.STAFF)
async def sync_calendar(request: Request, session: AsyncSession = Depends(db.session)):
    user: Users = request.state.user
    calendar_service = await user.get_google_service(CALENDAR_SCOPES)
    google_calendars = calendar_service.calendarList().list().execute()

    # 1. 삭제된 user_google_calendars를 찾기 위해 [새캘린더 추가 및 기존캘린더 업뎃] 순회 중에 모음.
    google_calendar_ids: set = set()

    # 2. 새 캘린더라면 추가, 기존 캘린더라면 업데이트
    for calendar in google_calendars['items']:
        google_calendar_ids.add(calendar['id'])

        await UserCalendars.create_or_update(
            session=session, auto_commit=True,  # CUD는 False로 순회하면 저장이 안됨.
            type=CalendarType.GOOGLE,
            google_calendar_id=calendar['id'],
            name=calendar['summary'],  # unique필드로서, 생성/update의 기준이 된다.
            is_deleted=False,  # True로 기존에 지워졌지만, 생성의 기준으로서, 똑같은 name이 있는 경우도 있으니, is_deleted=False로 업데이트해주기
            user_id=user.id,
        )

    # 3. 지워진 google calendar를 찾아 is_deleted=True 표시
    # -> 지워진 달력: user의 is_deleted=False 인 type GOOGLE인 calendar_ids 에는 있지만, 
    #               google의 calendar의 id에는 들어오지 않은 달력
    user_active_google_calendars = await UserCalendars.filter_by(
        session=session,
        user_id=user.id,
        type=CalendarType.GOOGLE,
        is_deleted=False
    ).all()

    user_active_google_calendar_ids: set = {calendar.google_calendar_id for calendar in user_active_google_calendars}

    # 4. db에는 active인데, google에는 없는 달력들 == 지워진 달력으로서, `is_deledted=True`로 삭제마킹 한다.
    deleted_google_calendar_ids: set = user_active_google_calendar_ids - google_calendar_ids
    for deleted_calendar_id in deleted_google_calendar_ids:
        target_calendar = await UserCalendars.filter_by(session=session, google_calendar_id=deleted_calendar_id).first()
        await target_calendar.update(session=session, auto_commit=True, is_deleted=True)

    # 5. view에 뿌려줄 active(is_deleted=False) google calendars
    calenders = await UserCalendars.filter_by(
        session=session,
        user_id=user.id,
        type=CalendarType.GOOGLE,
        is_deleted=False
    ).all()

    context = {
        'calendars': calenders,
    }

    # 6. synced calendars 조회하기
    # TODO: load 구현 후, classmethod로 만들기
    synced_calendars = await session.scalars(
        select(UserCalendars)
        .filter_by(is_deleted=False)  # cls 테이블에 대한 조건. 삭제처리 안된 것만
        .join(UserCalendars.calendar_syncs) \
        .filter(CalendarSyncs.user_id == user.id)
    )  # .all() # "'coroutine' object has no attribute 'all'"
    # TODO: .all()을 쓰려면, Mixin에 연쇄메서드로 정의해야한다.
    #       현재 login_required에서 user를 이미 심어놓고 가져오기 때문에, user에서 바로 synced_calendars를 가져올 순 없다. 따로 조회해야함.

    # print(f"synced_calendars >> {synced_calendars}")
    # sqlalchemy.engine.Engine SELECT usercalendars.type, usercalendars.google_calendar_id, usercalendars.name, usercalendars.is_deleted, usercalendars.last_sync_token, usercalendars.last_error, usercalendars.webhook_enabled, usercalendars.user_id, usercalendars.id, usercalendars.created_at, usercalendars.updated_at
    # FROM usercalendars INNER JOIN calendarsyncs ON usercalendars.id = calendarsyncs.calendar_id
    # WHERE calendarsyncs.user_id = %s
    # synced_calendars >> <sqlalchemy.engine.result.ScalarResult object at 0x0000015406108F40>
    synced_calendars = synced_calendars.all()

    context.update({
        'synced_calendars': synced_calendars,
    })

    return render(request, "dashboard/calendars/calendar-sync.html", context=context)


@router.post("/calendar_sync")
async def hx_create_calendar_syncs(
        request: Request,
        is_htmx=Depends(is_htmx),
        # body = Body(...),
        # body =Depends(hx_vals_schema(CreateCalendarSyncsRequest))
        data_and_error_infos=Depends(hx_vals_schema(CreateCalendarSyncsRequest)),
        session: AsyncSession = Depends(db.session),
):
    data, error_infos = data_and_error_infos
    if len(error_infos) > 0:
        # raise BadRequestException()
        error_endpoint = request.url_for('errors', status_code=400)
        error_endpoint = error_endpoint.include_query_params(message=error_infos)
        return redirect(error_endpoint, is_htmx=is_htmx)

    new_sync = await CalendarSyncs.create(
        session=session, auto_commit=True, refresh=True,
        user_id=data.get('user_id'),
        calendar_id=data.get('calendar_id'),
    )

    new_synced_calendar = await UserCalendars.filter_by(session=session, id=new_sync.calendar_id).first()

    # 현재 user의 모든 synced calendars 조회하기 for count
    # synced_calendars_count = await CalendarSyncs.filter_by(session=session, user_id=data.get('user_id')).count()
    # => custom event hx-trigger로 자동 처리

    return render(request, "dashboard/calendars/partials/synced-calendar-tr.html",
                  context={
                      'new_synced_calendar': new_synced_calendar,
                      'user_id': data.get('user_id'),
                      'calendar_id': data.get('calendar_id'),
                      # 'synced_calendars_count': synced_calendars_count,
                      # => custom event hx-trigger로 자동 처리
                  },
                  # 연동되서 호출될 hx custom event를 위한, HX-Trigger headers를 response 추가하는 옵션
                  hx_trigger='synced-calendars-count'
                  )


@router.post("/calendar_sync_cancel")
async def hx_delete_calendar_syncs(
        request: Request,
        is_htmx=Depends(is_htmx),
        data_and_error_infos=Depends(hx_vals_schema(DeleteCalendarSyncsRequest)),
        session: AsyncSession = Depends(db.session),
):
    data, error_infos = data_and_error_infos

    if len(error_infos) > 0:
        error_endpoint = request.url_for('errors', status_code=400)
        error_endpoint = error_endpoint.include_query_params(message=error_infos)
        return redirect(error_endpoint, is_htmx=is_htmx)

    # 1개 요소 delete
    target_sync = await CalendarSyncs.filter_by(
        session=session,
        user_id=data.get('user_id'),
        calendar_id=data.get('calendar_id'),
    ).first()

    await target_sync.delete(session=session, auto_commit=True)

    # htmx 삭제 후, 전체 user calendar 요소 다시 조회후 redner
    # TODO: load 구현 후, classmethod로 만들기
    synced_calendars = await session.scalars(
        select(UserCalendars)
        .filter_by(is_deleted=False)  # cls 테이블에 대한 조건. 삭제처리 안된 것만
        .join(UserCalendars.calendar_syncs) \
        .filter(CalendarSyncs.user_id == data.get('user_id'))
    )
    synced_calendars = synced_calendars.all()

    return render(request, "dashboard/calendars/partials/synced-calendar-table.html",
                  context={
                      'synced_calendars': synced_calendars,
                      'user_id': data.get('user_id'),
                      'calendar_id': data.get('calendar_id'),
                  },
                  hx_trigger='synced-calendars-count'
                  )


@router.get("/synced_calendars_count")
async def hx_get_synced_calendars_count(
        request: Request,
        session: AsyncSession = Depends(db.session),
):
    user = request.state.user

    # TODO: load 구현 후, count() 메서드로 처리되게 하기
    # scalars 객체 조회 : await session.scalars(stmt) + .all() =>
    # scalar count 조회 :
    # 1) stmt -> select( func.count() ).select_from( stmt )  + 2) await session.execute(count_stmt) + 3) .scalar()
    subquery_stmt = (
        select(UserCalendars)
        .filter_by(is_deleted=False)  # cls 테이블에 대한 조건. 삭제처리 안된 것만
        .join(UserCalendars.calendar_syncs)
        .filter(CalendarSyncs.user_id == user.id)
    )
    from sqlalchemy import func
    count_stmt = select(*[func.count()]) \
        .select_from(subquery_stmt)

    # synced_calendars_count_result = await session.scalar(count_stmt)
    # synced_calendars_count = synced_calendars_count_result.scalar()

    # 2) stmt -> select( func.count() ).select_from( stmt )  + 2) await session.scalar(count_stmt)
    synced_calendars_count = await session.scalar(count_stmt)

    return render(request, "dashboard/calendars/partials/synced-calendars-count-span.html",
                  context={
                      'synced_calendars_count': synced_calendars_count,
                  })
