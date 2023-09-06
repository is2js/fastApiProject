import logging

from fastapi import FastAPI
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base


class SQLAlchemy:

    # 1. 애초에 app객체 + 키워드인자들을 받아서 생성할 수 있지만,
    def __init__(self, app: FastAPI = None, **kwargs) -> None:
        self._engine = None
        self._Session = None
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
        database_url = kwargs.get("DB_URL")
        pool_recycle = kwargs.setdefault("DB_POOL_RECYCLE", 900)
        echo = kwargs.setdefault("DB_ECHO", True)

        # self._engine = create_engine(database_url, echo=echo, pool_recycle=pool_recycle, pool_pre_ping=True, )
        # self._Session = sessionmaker(bind=self._engine, autocommit=False, autoflush=False,)
        self._engine = create_async_engine(database_url, echo=echo, pool_recycle=pool_recycle,
                                           pool_pre_ping=True, )
        # expire_on_commit=False가 없으면, commit 이후, Pydantic Schema에 넘길 때 에러난다.
        self._Session = async_sessionmaker(bind=self._engine, autocommit=False, autoflush=False,
                                           expire_on_commit=False, # 필수 for schema
                                           )

        self.init_app_event(app)

        # table 자동 생성
        from app.models import Users
        # Base.metadata.create_all(bind=self._engine)
        # Base.metadata.create_all(bind=self._engine.sync_engine)

    # def get_db(self):
    async def get_db(self):

        # 초기화 X -> Session cls없을 땐 에러
        if self._Session is None:
            raise Exception("must be called 'init_app'")

        # 세션 객체를 만들고, yield한 뒤, 돌아와서는 close까지 되도록
        # -> 실패시 rollback 후 + raise e 로 미들웨어에서 잡도록
        db_session = self._Session()
        # db_session = None
        try:
            yield db_session
        except Exception as e:
            # db_session.rollback()
            await db_session.rollback()
            raise e
        finally:
            # db_session.close()

            #  sqlalchemy.exc.IllegalStateChangeError: Method 'close()' can't be called here; method '_connection_for_bind()' is already in progress and this would cause an unexpected state change to <SessionTransactionState.CLOSED: 5>
            # 비동기session은 -> 이미 커밋 또는 롤백이 발생했을 때만 세션을 닫음
            if db_session.is_active:
                await db_session.close()

    # get_db를 프로퍼티명()으로 호출할 수 있게, 호출전 함수객체를 return하는 프로퍼티
    @property
    def session(self):
        return self.get_db

    # 이것은 수정불가능한 내부 객체를 가져와야만 할 때
    @property
    def engine(self):
        return self._engine

    def init_app_event(self, app):
        @app.on_event("startup")
        async def start_up():
            self._engine.connect()
            logging.info("DB connected.")

            # 테이블 생성 추가
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                logging.info("DB create_all.")

        @app.on_event("shutdown")
        async def shut_down():
            # self._Session.close()
            await self._engine.dispose()
            logging.info("DB disconnected.")


db = SQLAlchemy()
Base = declarative_base()
