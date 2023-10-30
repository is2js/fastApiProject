from sqlalchemy import Column, String, Boolean, func, DateTime, Integer, ForeignKey, Enum
from sqlalchemy.orm import relationship

from app.models import BaseModel
from app.models.enums import CalendarType


class UserCalendars(BaseModel):
    # google_calendar_id = Column(String(length=500), nullable=False)
    type = Column(Enum(CalendarType), default=CalendarType.DEFAULT, index=True)
    google_calendar_id = Column(String(length=500), nullable=True)

    # name = Column(String(length=500), nullable=True)
    name = Column(String(length=500), nullable=False, unique=True)

    is_deleted = Column(Boolean, default=False)
    last_sync_token = Column(String(length=500), nullable=True)
    last_error = Column(DateTime, default=func.utc_timestamp(), nullable=True)
    webhook_enabled = Column(Boolean, default=False)  # See https://developers.google.com/calendar/api/guides/push

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user = relationship("Users", back_populates="calendars",
                        foreign_keys=[user_id],
                        uselist=False,
                        )

    calendar_syncs = relationship("CalendarSyncs", back_populates="calender",
                                cascade="all, delete-orphan",
                                lazy=True  # 'select'로서 자동load아님.
                                )


class CalendarSyncs(BaseModel):
    # session.delete( sync )시, fk테이블인 여기에서 where = dept.id update set NULL이 자동으로 이루어진다.
    # (1) one이 삭제될 수도 있다면(실제 검증에서 삭제안하게 할 건데), 부가적으로 발생하는 update에 대비해서
    #     nullable=False를 지워 nullabe한 칼럼으로 fk를 작성한다.
    # (2) 또한 ondelete="SET NULL"을 줘서, 자동으로 이뤄지는 where = dept.id update set NULL에 대비한다.
    # user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # user = relationship("Users", back_populates="calendar_syncs",
    #                     foreign_keys=[user_id],
    #                     uselist=False,
    #                     index=True,
    #                     )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user = relationship("Users", back_populates="calendar_syncs",
                        foreign_keys=[user_id],
                        uselist=False,
                        )

    # department_id = Column(Integer, ForeignKey('departments.id', ondelete='SET NULL'), index=True,
    #                        nullable=True)
    #
    # department = relationship("Department", foreign_keys=[department_id],
    #                           # backref=backref("employee_departments", passive_deletes=True),
    #                           # lazy='joined', # fk가 nullable하지 않으므로, joined를 줘도 된다.
    #                           back_populates='employee_departments'
    #                           )

    calendar_id = Column(Integer, ForeignKey('usercalendars.id', ondelete='CASCADE'), index=True, nullable=False)
    calender = relationship("UserCalendars", back_populates="calendar_syncs",
                            foreign_keys=[calendar_id],
                            uselist=False,
                            )
