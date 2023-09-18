from __future__ import annotations

import logging
from asyncio import current_task, shield
from typing import AsyncGenerator

from fastapi import FastAPI

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, async_scoped_session, \
    AsyncEngine
from sqlalchemy.ext.declarative import declarative_base

from app.utils.singleton import SingletonMetaClass


class SQLAlchemy(metaclass=SingletonMetaClass):

    # 1. 애초에 app객체 + 키워드인자들을 받아서 생성할 수 있지만,
    def __init__(self, app: FastAPI = None, **kwargs) -> None:
        self._engine: AsyncEngine | None = None
        self._Session: AsyncSession | None = None  # 의존성 주입용 -> depricated
        self._scoped_session: async_scoped_session[AsyncSession] | None = None  # 자체 세션발급용

        self._is_test_mode: bool = False# 테스트 여부

        # 2. app객체가 안들어올 경우, 빈 객체상태에서 메서드로 초기화할 수 있다.
        if app is not None:
            self.init_app(app=app, **kwargs)

    def init_app(self, app: FastAPI, **kwargs):
        """
        DB 초기화
        :param app:
        :param kwargs:
        :return:
        """
        database_url = kwargs.get("DB_URL",
                                  "mysql+aiomysql://travis:travis@mysql:13306/notification_api?charset=utf8mb4")
        pool_recycle = kwargs.setdefault("DB_POOL_RECYCLE", 900)
        echo = kwargs.setdefault("DB_ECHO", True)
        pool_size = kwargs.setdefault("DB_POOL_SIZE", 5)
        max_overflow = kwargs.setdefault("DB_MAX_OVERFLOW", 10)

        self._is_test_mode = kwargs.get('TEST_MODE', False)

        # self._engine = create_engine(database_url, echo=echo, pool_recycle=pool_recycle, pool_pre_ping=True, )
        # self._Session = sessionmaker(bind=self._engine, autocommit=False, autoflush=False,)
        self._engine = create_async_engine(database_url,
                                           echo=echo,
                                           pool_recycle=pool_recycle,
                                           pool_size=pool_size,
                                           max_overflow=max_overflow,
                                           pool_pre_ping=True,
                                           )

        # expire_on_commit=False가 없으면, commit 이후, Pydantic Schema에 넘길 때 에러난다.
        # self._Session: async_sessionmaker[AsyncSession] = \
        #     async_sessionmaker(
        #         bind=self._engine, autocommit=False,
        #         autoflush=False,
        #         expire_on_commit=False,  # 필수 for schema
        #     )

        self._scoped_session: async_scoped_session[AsyncSession] | None = \
            async_scoped_session(
                async_sessionmaker(
                    bind=self._engine, autocommit=False, autoflush=False, future=True,
                    expire_on_commit=False  # refresh로 대체할려 했으나, 매번 select가 되어 필요시마다 하기로.
                ),
                scopefunc=current_task,
            )

        # 자체 session 발급을 위해 Base에도 추가 -> object_mixin set_session에서 async with로 사용
        Base.scoped_session = self._scoped_session
        # print(f"self._scoped_session >> {self._scoped_session}") # async_scoped_session
        # print(f"self._scoped_session() >> {self._scoped_session()}") # AsyncSession  + async with에서 호출 가능.

        self.init_app_event(app)

        # table 자동 생성
        from app.models import Users
        # Base.metadata.create_all(bind=self._engine)
        # Base.metadata.create_all(bind=self._engine.sync_engine)

    # async def get_db(self) -> AsyncGenerator[AsyncSession, None]:
    #     async with self._Session() as session:
    #         yield session
    #         await session.close()

    # => 이렇게 사용하면, try/except가 안되고 rollback이 안됨. 억지로 try except를 넣는 들
    # => 비동기 컨텍스트 관리자를 사용할 때, 컨텍스트가 끝날 때 자동으로 __aexit__ 메서드가 호출되며,
    #    이 때 세션을 닫는 작업이 수행됩니다. 그러나 여기서 발생하는 문제는 세션을 닫은 후에도 예외가 발생하여 예외 처리 블록이 두 번 실행된다는 것입니다.

    # async def get_db(self):
    #     # 초기화 X -> Session cls없을 땐 에러
    #     if self._Session is None:
    #         raise Exception("must be called 'init_app'")
    #
    #     # 세션 객체를 만들고, yield한 뒤, 돌아와서는 close까지 되도록
    #     # -> 실패시 rollback 후 + raise e 로 미들웨어에서 잡도록
    #     db_session = self._Session()
    #     # db_session = None
    #     try:
    #         yield db_session
    #     except Exception as e:
    #         # db_session.rollback()
    #         await db_session.rollback()
    #         raise e
    #     finally:
    #         # db_session.close()
    #         #  sqlalchemy.exc.IllegalStateChangeError: Method 'close()' can't be called here; method '_connection_for_bind()' is already in progress and this would cause an unexpected state change to <SessionTransactionState.CLOSED: 5>
    #         # 비동기session은 -> 이미 커밋 또는 롤백이 발생했을 때만 세션을 닫음
    #         if db_session.is_active:
    #             await db_session.close()

    async def get_db(self) -> AsyncGenerator[AsyncSession, str]:
        # 초기화 X -> Session cls없을 땐 에러
        if self._scoped_session is None:
            raise Exception("must be called 'init_app'")

        async with self._scoped_session() as transaction:
            try:
                yield transaction
            except Exception as e:
                # shield는 rollback에서 예외가 발생하더라도, 밑에서 로그를 찍거나 할 수 있게 해준다.
                await shield(transaction.rollback())
                # logging
                raise e

    # router Depends() 주입용
    @property
    def session(self):
        return self.get_db

    # non router -> async with 발급 용
    @property
    def scoped_session(self):
        return self._scoped_session

    # 이것은 수정불가능한 내부 객체를 가져와야만 할 때
    @property
    def engine(self):
        return self._engine

    def init_app_event(self, app):
        @app.on_event("startup")
        async def start_up():
            # self._engine.connect()
            logging.info("DB connected.")

            # 테이블 생성 추가
            async with self.engine.begin() as conn:
                # 테스트모드라면, 테이블 삭제하고 생성하기
                if self._is_test_mode:
                    await conn.run_sync(Base.metadata.drop_all)
                    logging.info("TEST DB drop_all.")

                await conn.run_sync(Base.metadata.create_all)
                logging.info("TEST" if self._is_test_mode else "" + "DB create_all.")

        @app.on_event("shutdown")
        async def shut_down():
            # self._Session.close()
            await self._scoped_session.remove() # async_scoped_session은 remove까지 꼭 해줘야한다.
            await self._engine.dispose()
            logging.info("DB disconnected.")


db = SQLAlchemy()
Base = declarative_base()
