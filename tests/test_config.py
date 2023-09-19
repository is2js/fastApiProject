from sqlalchemy import text, select

from app.models import Users


async def test_config(app, session):
    print(session)
    result = await session.execute(
        text("select * from users;")
    )
    result = await session.execute(
        select(Users)
    )
    _all = result.scalars().all()
    print(_all)
    assert True
