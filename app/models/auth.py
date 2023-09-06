from sqlalchemy import Column, Enum, String, Boolean, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import BaseModel


class Users(BaseModel):
    status = Column(Enum("active", "deleted", "blocked"), default="active")
    email = Column(String(length=255), nullable=True, unique=True)
    pw = Column(String(length=2000), nullable=True)
    name = Column(String(length=255), nullable=True)
    phone_number = Column(String(length=20), nullable=True, unique=True)
    profile_img = Column(String(length=1000), nullable=True)
    sns_type = Column(Enum("FB", "G", "K"), nullable=True)
    marketing_agree = Column(Boolean, nullable=True, default=True)

    # keys = relationship("ApiKeys", back_populates="users")

    @classmethod
    # async def get_by_email(cls, session: Session, email: str):
    async def get_by_email(cls, session: AsyncSession, email: str):
        # result = session.scalars(
        #     select(cls).where(cls.email == email)
        # ).first()

        # result = await session.execute(
        #     select(cls).where(cls.email == email)
        # )
        # result.scalars().first()

        result = await session.scalars(
            select(cls).where(cls.email == email)
        )
        return result.first()

# if __name__ == '__main__':
#     print(Users.test())
