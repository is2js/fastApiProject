from sqlalchemy import select, text, Table, Subquery, Alias, and_, or_, func, exists, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.orm.collections import InstrumentedList

from app.database.conn import db
from app.errors.exceptions import SaveFailException
from app.models.mixins.base_mixin import BaseMixin
from app.models.mixins.consts import Clause, OPERATOR_SPLITTER, Logical, ORDER_BY_DESC_PREFIX
from app.models.mixins.maps import operator_map


class ObjectMixin(BaseMixin):
    __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.

    def __init__(self, *args, **kwargs):
        # 필드 추가를 위해, 생성자 재정의 했으면, 기존 부모의 생성자를 ids_, kwargs로 커버
        super().__init__(*args, **kwargs)
        self._query = None
        self._session = None
        self._served = None  # 공용 session 받은 여부

    # def _set_session(self, session: Session = None):
    async def set_session(self, session: Session = None):
        """
        외부 공용 session -> 덮어쓰기 + served
        외부 공용 session X ->  
            1) 필드x or session None -> 새발급
            2) 필드o and session값도 not None(no close, no commit) -> 기존 session 이용
            
        따로 안들어오면, 단순조회용으로 db에서 새발급
        """
        # 외부 X and 자신O(필드 + session) -> 아예 실행도 X
        if not session and getattr(self, '_session', None):
            return
       
        # 외부 O or 자신X
        if session:
            # (외부 O) & (자신O or 자신X 노상관) -> 무조건 덮어쓰기
            self._session, self._served = session, True
        else:
            # (외부 X) and 자신X -> 새 발급
            self._session = await db.session().__anext__()
            self._served = False

    @property
    def session(self):
        """
         외부 CRUD 메서드 내부
         obj = cls._create_obj() ->  obj.session.add()
        """
        if self._session is not None:
            return self._session

        raise Exception("Can get session.")

    @session.setter
    def session(self, session):
        self._session = session

    @property
    def query(self):
        """
         외부 CRUD 메서드 내부
         obj = cls._create_obj() ->  obj.query == select(Users)    에 .xxxx
        """
        return self._query

    @query.setter
    def query(self, stmt):
        """
        """
        self._query = stmt

    def set_query(self, **clause_map):
        """
        obj.set_query(where=dict(id=77))
        obj.set_query(order_by="-id")
        """
        # keyword로 입력되는 cluase_map의 key검사 -> Clause 안에 있어야한다.
        # -> create_obj시  clause_map이 없을 수도 있으니, 있을때만 검증하게 한다
        #   clause_map없이 select()만 초기화 하는 경우가 있다.
        if clause_map and not Clause.is_valid_dict(clause_map):
            raise KeyError(f'keyword는 {", ".join(Clause.values)} 중 하나여야합니다. : {", ".join(clause_map.keys())}')

        # query(select) 등은 is None 으로만 검증할 것(not self._query 시 에러)
        if self._query is None:
            self._query = select(self.__class__)

        # clause의 종류에 따라 각각 체이닝
        for clause_, value_ in clause_map.items():
            if clause_ == Clause.WHERE:
                # where value = dict( id=1 )
                self.chain_where_query(value_)
                continue

            elif clause_ == Clause.ORDER_BY:
                # order_by value = str tuple ("id") or ("-id") or ("-id, email")
                self.chain_order_by_query(value_)
                continue

    def chain_order_by_query(self, args: tuple):
        # column_exprs = self.create_order_by_exprs(args)
        column_exprs_generator = self.create_order_by_exprs(args)

        # .order_by(*column_exprs)
        self.query = (
            self.query
            .order_by(*column_exprs_generator)
        )

    def create_order_by_exprs(self, args: tuple):
        """
        order_by('id') -> args:  ('id',)
        order_by('id', '-id') -> args: ('id', '-id')
        """
        if not isinstance(args, (list, tuple, set)):
            args = tuple(args)

        # order_by_exprs = []

        for attr_name_ in args:
            order_by_prefix = ""
            if ORDER_BY_DESC_PREFIX in attr_name_:
                order_by_prefix = ORDER_BY_DESC_PREFIX
                attr_name_ = attr_name_.lstrip(ORDER_BY_DESC_PREFIX)

            order_func = desc if order_by_prefix else asc
            column_expr = self.get_column(self.__class__, attr_name_)
            order_by_expr = order_func(column_expr)  # desc(Users.id)

            # order_by_exprs.append(order_by_expr)
            yield order_by_expr

        # return order_by_exprs

    def chain_where_query(self, attr_name_and_value_map):
        condition_exprs_generator = self.create_condition_exprs_recursive(attr_name_and_value_map)

        self.query = (
            self.query
            .where(*condition_exprs_generator)
        )

    # dict -> list(key+value통합) 메서드에, {재귀key: dict-value}를 추가함에 따라, 재귀메서드로 처리하기
    # for where, having
    def create_condition_exprs_recursive(self, attr_name_and_value_map: dict):
        # 1) 재귀key가 포함될지도 모르니 다시 순회한다
        for attr_name_, value_ in attr_name_and_value_map.items():
            #    1개의 통합expression로서 yield하여 -> 외부 비재귀 list의 요소가 1개씩 yield될 때, 같은 급으로 and_(), or_() 가 줄슨다.
            if attr_name_.lower().startswith((Logical.AND, Logical.OR)):
                # 2-1) and_냐 or_냐 따라서, 재귀dict-value의 결과물 list를 1개로 통합하여
                #      전체적 generator의 1개요소로서 반환되게 한다.
                if attr_name_.lower().startswith(Logical.AND):
                    # yield from으로 나가는 expression 1개와 동급으로 and_(*list)로 통합해서 yied로 반환하자.
                    # -> 재귀메서드를 호출하되, 인자는 재귀key에 대한 dict value다.
                    yield and_(*self.create_condition_exprs_recursive(value_))
                elif attr_name_.lower().startswith(Logical.OR):
                    yield or_(*self.create_condition_exprs_recursive(value_))

                continue

            # 3) 재귀가 아닌 key + value는, **원래 인자에서 재귀key를 통과한 No재귀key + value를 dict로 전달해줘야한다.**
            #  - list를 추출하는 메서드를 호출한 뒤, yield from으로 반환 -> 1개씩 요소들이 방출되게 한다.
            #    (재귀 결과물 list -> 통합 1개요소 들과 같이 줄 세우기 위함)
            no_recursive_map = {attr_name_: value_}
            yield from self.create_condition_exprs(no_recursive_map)

    # 재귀로 조건식들을 반환
    # for where, having
    def create_condition_exprs(self, attr_name_and_value_map: dict):
        condition_exprs = []

        for attr_name_, value_ in attr_name_and_value_map.items():
            if OPERATOR_SPLITTER in attr_name_:
                attr_name_, op_name = attr_name_.split(OPERATOR_SPLITTER, maxsplit=1)
                # split해서 만든 op_name 검증
                self.check_op_name(attr_name_, op_name)

            else:
                attr_name_, op_name = attr_name_, 'eq'

            op_func = operator_map[op_name]
            column_expr = self.get_column(self.__class__, attr_name_)
            condition_expr = op_func(column_expr, value_)

            condition_exprs.append(condition_expr)

        return condition_exprs

    def check_op_name(self, attr_name_, op_name):
        if op_name not in operator_map:
            raise KeyError(f'잘못된 칼럼 연산자를 입력하였습니다. {attr_name_}__{op_name}')

    @property
    def served(self):
        return self._served

    @served.setter
    def served(self, is_served):
        self._served = is_served

    @classmethod
    # async def _create_obj(cls, session: Session = None, query=None):
    async def create_obj(cls, session: Session = None, **kwargs):
        obj = cls()
        await obj.set_session(session=session)  # 비동기 session을 받아오는 비동기 호출 메서드로 변경

        # create_obj()에 들어오는 kwargs 중에, Clause.values(상수필드의 'where' 등의 value)에 해당하는 것만 추출해서,
        # set_query()에 입력해준다.
        clause_kwargs = Clause.extract_from_dict(kwargs)  # {'where': {'id__ne': None}} or {}
        obj.set_query(**clause_kwargs)

        return obj

    # self -> obj.xxxx메서드()  or   user.fill()
    def fill(self, **kwargs):
        """
        create 내부 obj객체   or   외부 model객체.fill() 용 self메서드
        obj = cls._create_obj()
        obj.fill(**kwargs) -> True or False (is_filled)
        """
        is_filled = False

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

            is_filled = True

        # return self
        return is_filled

    # self + async -> session관련 메서드 obj.save() or user.save()
    # for cls create
    async def save(self, auto_commit=False):
        """
        obj.fill() -> obj.save() or user.fill() -> user.save()
        1) 공용세션(served) -> merge (add + flush + refresh / update + flush + refresh)
        2) 자체세션 -> add + flush + refresh 까지
        if commit 여부에 따라, commit
        """
        try:
            # id를 가진 조회된객체(자체sess)상태에서 + 외부 공용sess 주입 상태일때만 merge
            if self.id is not None and self.served:
                await self.session.merge(self)
            else:
                self.session.add(self)
                await self.session.flush()

            if auto_commit:
                await self.session.commit()
                self._session = None
                self._served = False

            return self

        except Exception as e:
            raise SaveFailException(cls_=self.__class__, exception=e)

    @classmethod
    def get_column(cls, model, attr):
        # for expression
        if isinstance(model, str):
            return text(model + '.' + attr)

        # for join expression
        if isinstance(model, (Table, Subquery, Alias)):
            return getattr(model.c, attr, None)

        return getattr(model, attr, None)

    @classmethod
    def check_pk_or_unique_keyword(cls, kwargs):
        identity_columns = cls.primary_key_names + cls.unique_names
        if not all(attr in identity_columns for attr in kwargs.keys()):
            raise KeyError(f'primary key or unique 칼럼을 입력해주세요.')

    async def count(self, session: AsyncSession = None):
        # count는, 자체발급세션에서도, 단순 마지막 처리가 아닌, 중간처리용으로 호출할 수 있기 때문에
        # -> 단순 1model 처리를 위한, 자체발급sesson(not served)라도, [자체발급 자기 session을 session=]인자로 받을 수 있게 한다.
        #    인자session(외부공용일수도 or 자체 발급session 신호용)으로, flush/close를 자체적으로 결정짓는다.
        #    => 인자보고 close판단해야한다면, self.close()는 session인자 없을 때만 마지막처리로서 호출하게 한다.
        # 조회후 flush()만 되면, 이 때 조회된 객체들은 close()가 안되어, 외부session의 identity_map에 남아있는데
        # close안될 위험이 있기 때문에, 최대한 close + 외부인자session(공용 or 자체)가 있을 때만 flush를 해준다.
        # -> session인자가 없다면, close()를 한번 더 호출해서, served여부에 따라 close되게 한다.
        count_stmt = select(*[func.count()]) \
            .select_from(self.query)

        # 중간에 호출될 수 있는 조회메서드count() <-> first, all 등
        # 자체발급session이라도 중간count면, 인자로 들어와 -> flush만 하고 안닫도록
        # 외부 session인자(공용or자체발급) 신호를 보여주지 않으면, 최종 조회로 판단하고, session close()
        if session:
            # 공용session or 자체session인데 close방지용*****
            result = await session.execute(count_stmt)
            await session.flush()
        else:
            result = await self.session.execute(count_stmt)
            await self.close()

        count_ = result.scalar()

        return count_

    async def exists(self, session: AsyncSession = None):
        """
        obj.set_query()
        obj.exists()
        :param session:
        :return:  True or False
        """
        # EXISTS (
        #   SELECT users.status, users.email, users.pw, users.name, users.phone_number, users.profile_img, users.sns_type, users.marketing_agree, users.id, users.created_at, users.updated_at
        #   FROM users
        #   WHERE users.id = %s
        # ) AS anon_1
        exists_stmt = exists(self._query) \
            .select()

        if session:
            # 공용session or 자체session인데 close방지용*****
            result = await session.execute(exists_stmt)
            await session.flush()
        else:
            result = await self.session.execute(exists_stmt)
            await self.close()

        exists_ = result.scalar()

        return exists_

    async def close(self):
        # 내부session을 -> 조회라도 항상 close()
        # => 내부공용세션이라도, 매번 여러객체를 조회하기 때문에, 매번 close해준다.
        #    변경사항이 필요한 경우, close되더라도, 어차피 merge로 인해 session올라가서 처리된다.
        # * 내부 공용세션이라고 close안해주면 => sqlalchemy.exc.TimeoutError:
        #   QueuePool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00

        #  내부session이면, 조회한 객체들은 공용session의 identity_map에서 없애, 조회 후 obj 변화는 반영안된다.
        if not self.served:
            await self._session.close()
            # 추가 / close된 객체의 자체발급 session은 더이상 안쓰도록 직접 변수에서 제거해 -> 추가호출시 에러나게 한다.
            self.session = None

        # 외부session이면 close할 필요없이 반영만  [외부 쓰던 session은 close 대신] -> [flush()로 db 반영시켜주기]
        # -> 외부session이면, 금방 사라지거나, 맨마지막 놈이 commit되어 자동close()되므로 flush()만 해준다.
        # 외부session이면, 금방 사라지거나, 맨마지막 놈이 commit되어 자동close()되므로 flush()만 해준다.
        #     # -> 이 때 조회된 객체들은 close()가 안되어, 외부session의 identity_map에 남아있다
        else:
            await self._session.flush()

    async def first(self):
        result = await self.session.execute(self.query)
        _first = result.scalars().first()

        await self.close()
        return _first

    async def all(self):
        result = await self.session.execute(self.query)
        _all = result.scalars().all()

        await self.close()
        return _all

    async def one_or_none(self):
        result = await self.session.execute(self.query)
        _one_or_none = result.scalars().one_or_none()

        await self.close()
        return _one_or_none
