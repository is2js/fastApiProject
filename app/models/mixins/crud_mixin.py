from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mixins.object_mixin import ObjectMixin


class CRUDMixin(ObjectMixin):
    __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.

    @classmethod
    async def create(cls, session: AsyncSession = None, auto_commit=False, **kwargs):
        obj = await cls._create_obj(session=session)
        if kwargs:
            obj.fill(**kwargs)

        return await obj.save(auto_commit=auto_commit)
