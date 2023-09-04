from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.collections import InstrumentedList

from app.database.conn import db
from app.models.mixins.base_mixin import BaseMixin
from app.models.utils import class_property


class ObjectMixin(BaseMixin):
    __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.

    def __init__(self, *args, **kwargs):
        # 필드 추가를 위해, 생성자 재정의 했으면, 기존 부모의 생성자를 args, kwargs로 커버
        super().__init__(*args, **kwargs)
        self._query = None
        self._session = None
        self._served = None  # 공용 session 받은 여부

    # def _set_session(self, session: Session = None):
    async def _set_session(self, session: Session = None):
        """
        공용 session이 따로 안들어오면, 단순조회용으로 db에서 새발급
        """
        if session:
            self._session, self._served = session, True
        else:
            # session = next(db.session())
            # 비동기 AsyncSession는 yield하더라도, # 'async_generator' object is not an iterator 에러가 뜬다.
            # => 제네레이터가 아니라 비동기 제네레이터로서, wait + 제네레이터.__anext__()를 호출한다.
            session = await db.session().__anext__()

            self._session, self._served = session, False

    @property
    def session(self):
        """
         외부 CRUD 메서드 내부
         obj = cls._create_obj() ->  obj.session.add()
        """
        if self._session is not None:
            return self._session

        raise Exception("Can get session.")

    def _set_query(self, query=None):
        """
        query를 따로 안넣으면, select( Users by self.__class__ )
        """
        if query:
            self._query = query
        else:
            self._query = select(self.__class__)

    @property
    def query(self):
        """
         외부 CRUD 메서드 내부
         obj = cls._create_obj() ->  obj.query == select(Users)    에 .xxxx
        """
        return self._query

    @classmethod
    async def _create_obj(cls, session: Session = None, query=None):
        obj = cls()
        # obj._set_session(session=session) # 비동기 session을 받아오는 비동기 호출 메서드로 변경
        await obj._set_session(session=session) # 비동기 session을 받아오는 비동기 호출 메서드로 변경
        obj._set_query(query=query)

        return obj

    # self -> obj.xxxx메서드()  or   user.fill()
    def fill(self, **kwargs):
        """
        create 내부 obj객체   or   외부 model객체.fill() 용 self메서드
        obj = cls._create_obj()
        obj.fill(**kwargs)
        """
        for column_name, new_value in kwargs.items():
            # 1) form.data(dict) 에 더불어 오는 keyword => 에러X 무시하고 넘어가기
            if column_name in ['csrf_token', 'submit'] or column_name.startswith('hidden_'):
                continue
            # 2) settable_attr이 아니라도 -> (@property일 수 있다)
            #    setter/expression을 hasattr()하고 있는 @property는, fill 가능이다.
            #    (settable_attr에 포함되면 바로 통과)
            if not (column_name in self.settable_attributes or self.is_setter_or_expression(column_name)):
                raise KeyError(f'Invalid column name: {column_name}')

            # 3) (settable_attr or property지만) 2개를 포괄하는 column_names 중에
            #    -> 이미 현재 값과 동일한 값이면, continue로 넘어간다.
            if column_name in self.column_names and getattr(self, column_name) == new_value:
                continue

            # 4) 이제 self의 column에 setattr() 해줄 건데, <관계칼럼이면서 & uselist=True>는 append를 해준다.
            if column_name in self.relation_names and isinstance(getattr(self, column_name), InstrumentedList) \
                    and not isinstance(new_value, list):
                getattr(self, column_name).append(new_value)
            else:
                setattr(self, column_name, new_value)

        return self

    # self + async -> session관련 메서드 obj.save() or user.save()
    async def save(self, auto_commit=False):
        """
        obj.fill() -> obj.save() or user.fill() -> user.save()
        1) 공용세션(served) -> merge (add + flush + refresh / update + flush + refresh)
        2) 자체세션 -> add + flush + refresh 까지
        if commit 여부에 따라, commit
        """
        if self.id is not None:
            await self.session.merge(self)
        else:
            self.session.add(self)
            await self.session.flush()

        if auto_commit:
            await self.session.commit()
            await self.session.refresh(self)

        return self
