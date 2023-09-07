from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mixins.object_mixin import ObjectMixin
from app.models.utils.async_chain import async_chain
from app.models.utils.class_or_instance_method import class_or_instance_method


class CRUDMixin(ObjectMixin):
    __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.

    # @classmethod
    @class_or_instance_method
    async def create(cls, session: AsyncSession = None, auto_commit=False, **kwargs):
        obj = await cls.create_obj(session=session)
        if kwargs:
            obj.fill(**kwargs)

        return await obj.save(auto_commit=auto_commit)

    @create.instancemethod
    async def create(self, session: AsyncSession = None, auto_commit=False, **kwargs):
        raise NotImplementedError(f'객체 상태에서 create메서드를 호출 할 수 없습니다.')

    # @classmethod
    @class_or_instance_method
    async def get(cls, *ids_, session: AsyncSession = None, **kwargs):
        """
        1. id(pk)로  1개만 검색하는 경우 => where(id칼럼 == ) + first()
            User.get(1) => <User> or None
        2. id(pk)   2개로 검색하는 경우 => where(id칼럼.in_() ) + .all()
            User.get(1, 2) => [<User>, <.User object at 0x000002BE16C02FD0>]
        3. kwargs의 경우, pk or unqiue 로 검색 => where(email=, id=)
        """
        # 인자 검증1) ids_ or kwargs가 들어와야함. &  둘다 들어오면 안됨.
        if not (ids_ or kwargs) or (ids_ and kwargs):
            raise KeyError(f'id or 키워드는 primary key or unique 칼럼 1개만 입력해주세요.')

        # 인자 검증2) kwargs가 들어왔는데, 그 값이 pk + unique list 안에 포함되지 않는다면, 탈락이다.
        cls.check_pk_or_unique_keyword(kwargs)

        obj = await cls.create_obj(session=session)

        # 1) id 1~여러개가 들어오는 경우 -> 기본query(select(cls))에 .where(id칼럼.in( list ))를 이용해서 stmt만들기
        if ids_ and not kwargs:
            ids_ = list(set(ids_))  # 중복제거

            # 검증) id는 정수임을 확인
            if not any(type(id_) == int for id_ in ids_):
                raise KeyError(f'id(pk)를 정수로 입력해주세요.')

            # stmt 생성 -> 2개이상 시 where in ids / 1개 wehre id칼럼 == ids[0]
            if len(ids_) > 1:
                obj.set_query(where=dict(id__in=ids_))
            else:
                obj.set_query(where=dict(id=ids_[0]))

            # 2개이상의 id를 입력한 경우, 들어온 id의 갯수 vs 결과 갯수가 다르면 ->  Error
            # - 중간 count라면, session=인자로 신호주기
            count = await obj.count(session=obj.session)

            # 2개이상 검색 & 결과가 [] 0개가 아닌데, id갯수 != 결과갯수가 다르면 에러를 낸다.
            # ex> .get(1,2) 검색 -> 1개 / .get(1,2,3) -> 2개
            if len(ids_) > 1 and count != 0 and len(ids_) != count:
                raise KeyError(f'유효하지 않은 id or 중복된 id가 포함되어 있습니다.')

            # 결과 추출 -> 1개일땐 first( 객체 or None) 2개이상 all ( 객체list or [] )
            if len(ids_) > 1:
                result = await obj.all()
            else:
                # id 1개 조회에서는 none이 나올 경우, 에러를 발생시켜야한다.
                result = await obj.one_or_none()
                if not result:
                    raise KeyError(f'{obj.__class__} with id "{ids_[0]}" was not found')


        # 2) kwargs(pk or unique 칼럼)로 조회
        else:
            # 현재 kwargs의 key는 모두 pk or unique key들로 검증된 상태다.
            obj.set_query(where=kwargs)

            # keyword 여러개 입력해도, 갯수가 1개 초과면, get()에서는 에러가 나야함.
            result = await obj.one_or_none()
            if not result:
                raise KeyError(f'{obj.__class__} with keyword "{kwargs.keys()}" was not found')

        return result

    @get.instancemethod
    async def get(self, *ids_, session: AsyncSession = None, **kwargs):
        raise NotImplementedError(f'객체 상태에서 create메서드를 호출 할 수 없습니다.')

    @class_or_instance_method
    @async_chain
    async def filter_by(cls, session: AsyncSession = None, **kwargs):
        """
        Users.filter_by( id=1) - kwargs
            -> obj.create_obj(where= kwargs) or obj.set_query(where=kwargs)
        .first() / .all() 을 추가로 입력하도록 obj를 return
        """
        obj = await cls.create_obj(session=session, where=kwargs)
        return obj

    @filter_by.instancemethod
    @async_chain
    async def filter_by(self, **kwargs):

        self.set_query(where=kwargs)

        return self

    @class_or_instance_method
    @async_chain
    async def order_by(cls, *args, session: AsyncSession = None):
        """
        Users.order_by("-id")
        Users.order_by("-id", "email")
        """
        cls.check_order_by_args(args)

        obj = await cls.create_obj(session=session, order_by=args)
        return obj

    @order_by.instancemethod
    @async_chain
    async def order_by(self, *args):
        self.check_order_by_args(args)

        self.set_query(order_by=args)

        return self

    @classmethod
    def check_order_by_args(self, args):
        if not all(isinstance(column_name, str) for column_name in args):
            raise KeyError(f'column명을 string으로 입력해주세요 ex> order_by("id", "-id") ')

    ###################
    # Update -        # -> only self method => create_obj없이 model_obj에서 [최초호출].init_obj()로 초기화
    ###################
    @class_or_instance_method
    async def update(self, session: AsyncSession = None, auto_commit: bool = False, **kwargs):
        raise NotImplementedError(f'update 메서드는 객체상태에서만 호출 할 수 있습니다.')

    @update.instancemethod
    async def update(self, session: AsyncSession = None, auto_commit: bool = False, **kwargs):
        """
        c = Category.get(1) # c.name '카테고리1'
        c.update(name='카테고리1, auto_commit=True) # False ->  '값의 변화가 없어서 업데이트 실패'

        - 만약, fill시 데이터가 변하지 않으면 -> None이 반환되고
        - is_filled True -> save 까지 성공 -> 업데이트된 객체가 반환된다.

        """
        # 자체 create이후 & no commit은 session을 넣을 필요가 없다.
        # -> 외부session or 이미 자체sess발급된 객체가 + 이전에 auto_commit되어 session이 None일 때만, session을 넣는다.
        # if not(not session and getattr(self, '_session')):
        # if session or not getattr(self, '_session'):
        await self.set_session(session=session)

        is_filled = self.fill(**kwargs)

        if not is_filled:
            return None

        return await self.save(auto_commit=auto_commit)
