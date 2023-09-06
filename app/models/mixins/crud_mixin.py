from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mixins.object_mixin import ObjectMixin


class CRUDMixin(ObjectMixin):
    __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.

    @classmethod
    async def create(cls, session: AsyncSession = None, auto_commit=False, **kwargs):
        obj = await cls.create_obj(session=session)
        if kwargs:
            obj.fill(**kwargs)

        return await obj.save(auto_commit=auto_commit)

    @classmethod
    async def get(cls, *ids_, session: AsyncSession = None, **kwargs):
        """
        1. id(pk)로  1개만 검색하는 경우 => where(id칼럼 == ) + first()
            User.get(1) => <User> or None
        2. id(pk)   2개로 검색하는 경우 => where(id칼럼.in_() ) + .all()
            User.get(1, 2) => [<User>, <.User object at 0x000002BE16C02FD0>]
        3. kwargs(unique key or pk) key1개, values list 가능 우 -> filter_by(where)로 1개 .first() / 여러개 .all()
            User.get(username='admin')
            Category.get(name=['123', '12345'])
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
