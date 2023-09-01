from datetime import datetime, timedelta, date


class D:
    # class메서드들용으로서, 메서드 호출 -> 내부 cls() 인스터싱 -> 현재시각을 얻게 된다.
    def __init__(self) -> None:
        self.utc_now = datetime.utcnow()
        self.timedelta = 0

    @classmethod
    def datetime(cls, diff_hours: int = 0) -> datetime:
        # 차이시간이 0보다 크면 현재시각에 + / 음수면, 현재시각에서 - 한 datetime
        return cls().utc_now + timedelta(hours=diff_hours) if diff_hours > 0 else \
            cls().utc_now - timedelta(hours=diff_hours)

    # 위의 diff한 datetime을 date로 변환
    @classmethod
    def date(cls, diff_hours: int = 0) -> date:
        return cls.datetime(diff_hours=diff_hours).date()

    # 위의 diff한 date를 문자열20220101로 변환 후 -> 정수 20220101로
    @classmethod
    def date_number(cls, diff_hours: int = 0) -> int:
        date_string = cls.date(diff_hours=diff_hours).strftime('%Y%m%d')
        return int(date_string)

