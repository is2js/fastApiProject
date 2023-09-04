from sqlalchemy import Column, Integer, DateTime, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declared_attr, Session, RelationshipProperty

from app.database.conn import Base, db
from app.models.mixins.crud_mixin import CRUDMixin
from app.models.utils import class_property


class BaseModel(CRUDMixin):
    __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.

    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, nullable=False, default=func.utc_timestamp())
    updated_at = Column(DateTime, nullable=False, default=func.utc_timestamp(), onupdate=func.utc_timestamp())

    # def __init__(self, *args, **kwargs):
    #     self._query = None
    #     self._session = None
    #     self._served = None # 공용 session 받은 여부
    #     # 필드 추가를 위해, 생성자 재정의 했으면, 기존 부모의 생성자를 args, kwargs로 커버
    #     super().__init__(*args, **kwargs)

    # id가 아닌 id의 해쉬값
    def __hash__(self):
        return hash(self.id)

    # 기본 CRUD 메서드
    # 1) create -> 새 session발급 없이, [인자] 외부주입 [router 공용 session]으로만 사용해서 그 속에 [객체추가]
    #   + all_columns 메서드 -> 자동으로 주어지는 id, created_at을, [생성시 제외하고 setattr 하기 위함.]
    #   - autocommit이 안들어가는 경우, 1session으로 여러가지 작업을 이어서 나가야하기 때문에 -> 받은 session으로만 사용
    # 2) get -> 조회는 [router 공용 session 주입 인자] + [내부  next() session 새 발급] - route 공용세션 없는, 메서드 상황에서 단독조회까지 가능하게 한다
    #   + if 내부 새발급session이라면, .close()로 조회만 하고 객체만 반환하여 닫는다.
    #   - commit개념이 없고, 데이터 조회만 하는 경우 -> 내부 새 세션 / 작업이 이어지는 경우 -> 외부 세션

    def all_columns(self):
        return [c for c in self.__table__.columns if c.primary_key is False and c.name != "created_at"]

    # @classmethod
    # async def create(cls, session: AsyncSession, auto_commit=False, **kwargs):
    #     obj = cls()
    #     # id, created_at 제외 칼럼들을 돌면서, kwargs로 들어온 것 중에 있는 칼럼명의 경우, setattr()
    #     for col in obj.all_columns():
    #         col_name = col.name
    #         if col_name not in kwargs:
    #             continue
    #         setattr(obj, col_name, kwargs.get(col_name))
    #
    #     session.add(obj)
    #     # 일단 flush해서 session을 유지하다가, auto_commit=True까지 들어오면, commit하면서 닫기
    #     await session.flush()
    #     if auto_commit:
    #         await session.commit()
    #         # await session.refresh(obj)
    #
    #     return obj

    @classmethod
    async def create_test(cls, session: Session = None, auto_commit=False, **kwargs):
        obj = await cls._create_obj(session=session)
        # print(obj.__dict__)
        # print(obj.session)  # property
        # print(obj.query)
        # print(obj.settable_attributes)  # ['status', 'email', 'pw', 'name', 'phone_number', 'profile_img', 'sns_type', 'marketing_agree', 'updated_at']
        if kwargs:
            obj.fill(**kwargs)

        return await obj.save(auto_commit=auto_commit)

    @classmethod
    def get(cls, session: Session = None, **kwargs):
        # 1) router 공용 session이 없다면, 새 session을 바급한다.
        local_session = next(db.session()) if not session else session
        # 2) session.query(cls)로 연쇄 query의 첫번째 요소로 만든다.
        query = local_session.query(cls)
        # 3) kwarg로 들어오는 검색요소key=value를 순회하면서,
        #    getattr(cls, key)로 column을 꺼내고, filter()를 연쇄한다.
        for key, value in kwargs.items():
            column = getattr(cls, key)
            query = query.filter(column == value)

        # 4) query.count()를 쳐서 1개 이상이면, get에 안어울려 에러는 낸다.
        if query.count() > 1:
            raise Exception("Only one row is supposed to be returned, but got more than one. ")
        result = query.first()

        # 5) 외부주입 session이 아니라면, 조회후 새발급 session을 끊어버린다.
        if not session:
            local_session.close()

        return result
