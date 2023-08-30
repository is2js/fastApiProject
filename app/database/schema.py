from sqlalchemy import Column, Integer, DateTime, func, Enum, String, Boolean
from sqlalchemy.orm import declared_attr, Session

from app.database.conn import Base


class BaseModel(Base):
    __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.

    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, nullable=False, default=func.utc_timestamp())
    updated_at = Column(DateTime, nullable=False, default=func.utc_timestamp(), onupdate=func.utc_timestamp())

    def __init__(self, *args, **kwargs):
        # 필드 추가를 위해, 생성자 재정의 했으면, 기존 부모의 생성자를 args, kwargs로 커버
        super().__init__(*args, **kwargs)
        self._query = None
        self._session = None
        self.served = None

    # id가 아닌 id의 해쉬값
    def __hash__(self):
        return hash(self.id)

    # 기본 CRUD 메서드
    # 1) create -> 새 session발급 없이, [인자] 외부주입 [공용 새 session]으로만 사용해서 그 속에 [객체추가]
    #   + all_columns 메서드 -> 자동으로 주어지는 id, created_at을, [생성시 제외하고 setattr 하기 위함.]
    # 2) get -> 조회는 [공용session 주입 인자] + [내부 next()로 조회용 새session발급]-[조회route는 공용session 주입 없이] 간다?

    def all_columns(self):
        return [c for c in self.__table__.columns if c.primary_key is False and c.name != "created_at"]

    @classmethod
    def create(cls, session: Session, auto_commit=False, **kwargs):
        obj = cls()
        # id, created_at 제외 칼럼들을 돌면서, kwargs로 들어온 것 중에 있는 칼럼명의 경우, setattr()
        for col in obj.all_columns():
            col_name = col.name
            if col_name not in kwargs:
                continue
            setattr(obj, col_name, kwargs.get(col_name))

        session.add(obj)
        # 일단 flush해서 session을 유지하다가, auto_commit=True까지 들어오면, commit하면서 닫기
        session.flush()
        if auto_commit:
            session.commit()

        return obj


class Users(BaseModel):

    status = Column(Enum("active", "deleted", "blocked"), default="active")
    email = Column(String(length=255), nullable=True)
    pw = Column(String(length=2000), nullable=True)
    name = Column(String(length=255), nullable=True)
    phone_number = Column(String(length=20), nullable=True, unique=True)
    profile_img = Column(String(length=1000), nullable=True)
    sns_type = Column(Enum("FB", "G", "K"), nullable=True)
    marketing_agree = Column(Boolean, nullable=True, default=True)
    # keys = relationship("ApiKeys", back_populates="users")
