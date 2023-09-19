from __future__ import annotations

import logging
from asyncio import current_task, shield
from typing import AsyncGenerator, Any

from fastapi import FastAPI
from sqlalchemy import Engine, Connection, text, create_engine, NullPool

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, async_scoped_session, \
    AsyncEngine
from sqlalchemy.orm import declarative_base
from sqlalchemy_utils import database_exists, create_database

from app.common.config import config, DOCKER_MODE
from app.database.mysql import MySQL
from app.utils.singleton import SingletonMetaClass


class SQLAlchemy(metaclass=SingletonMetaClass):

    # 1. 애초에 app객체 + 키워드인자들을 받아서 생성할 수 있지만,
    def __init__(self, app: FastAPI = None, **kwargs) -> None:
        self._async_engine: AsyncEngine | None = None
        self._Session: AsyncSession | None = None  # 의존성 주입용 -> depricated
        self._scoped_session: async_scoped_session[AsyncSession] | None = None  # 자체 세션발급용

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

        self._async_engine = create_async_engine(database_url,
                                                 echo=echo,
                                                 pool_recycle=pool_recycle,
                                                 pool_size=pool_size,
                                                 max_overflow=max_overflow,
                                                 pool_pre_ping=True,
                                                 )

        self._scoped_session: async_scoped_session[AsyncSession] | None = \
            async_scoped_session(
                async_sessionmaker(
                    bind=self._async_engine, autocommit=False, autoflush=False, future=True,
                    expire_on_commit=False  # refresh로 대체할려 했으나, 매번 select가 되어 필요시마다 하기로.
                ),
                scopefunc=current_task,
            )

        # for mixin
        Base.scoped_session = self._scoped_session

        # no docker시, database + user 정보 생성
        self.create_database_and_user()

        self.init_app_event(app)

    def create_database_and_user(self):
        SYNC_DB_URL: str = config.DB_URL.replace("aiomysql", "pymysql") \
            .replace(config.MYSQL_USER, 'root') \
            .replace(config.MYSQL_PASSWORD, config.MYSQL_ROOT_PASSWORD)

        if not database_exists(SYNC_DB_URL):
            sync_engine: Engine = create_engine(SYNC_DB_URL, poolclass=NullPool, echo=config.DB_ECHO)
            create_database(sync_engine.url)

            if not MySQL.exists_user(user=config.MYSQL_USER, engine=sync_engine):
                MySQL.create_user(user=config.MYSQL_USER, password=config.MYSQL_PASSWORD, host=config.MYSQL_HOST,
                                  engine=sync_engine)
            if not MySQL.is_user_granted(user=config.MYSQL_USER, database=config.MYSQL_DATABASE, engine=sync_engine):
                MySQL.grant_user(
                    grant="ALL PRIVILEGES",
                    on=f"{config.MYSQL_DATABASE}.*",
                    to_user=config.MYSQL_USER,
                    user_host='%',
                    engine=sync_engine,
                )

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
        return self._async_engine

    def init_app_event(self, app):
        @app.on_event("startup")
        async def start_up():
            # 테이블 생성 추가
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                logging.info("DB create_all.")

        @app.on_event("shutdown")
        async def shut_down():
            # self._Session.close()
            await self._scoped_session.remove()  # async_scoped_session은 remove까지 꼭 해줘야한다.
            await self._async_engine.dispose()
            logging.info("DB disconnected.")


db = SQLAlchemy()
Base = declarative_base()
