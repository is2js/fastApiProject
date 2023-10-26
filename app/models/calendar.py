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
