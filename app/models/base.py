from sqlalchemy import Column, Integer, DateTime, func

from sqlalchemy.orm import declared_attr

from app.models.mixins.crud_mixin import CRUDMixin
from app.models.mixins.repr_mixin import ReprMixin


# 최상위 Mixin + ReprMixin
class BaseModel(CRUDMixin, ReprMixin):
    __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.
    __mapper_args__ = {"eager_defaults": True}  # default 칼럼 조회시마다 refresh 제거 (async 필수)

    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, nullable=False, default=func.utc_timestamp())
    updated_at = Column(DateTime, nullable=False, default=func.utc_timestamp(), onupdate=func.utc_timestamp())

    # id가 아닌 id의 해쉬값
    def __hash__(self):
        return hash(self.id)
