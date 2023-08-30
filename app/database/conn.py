import logging

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


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

        self._engine = create_engine(database_url, echo=echo, pool_recycle=pool_recycle, pool_pre_ping=True, )
        self._Session = sessionmaker(bind=self._engine, autocommit=False, autoflush=False, )

        @app.on_event("startup")
        def start_up():
            self._engine.connect()
            from .schema import Users
            Base.metadata.create_all(bind=self._engine)
            logging.info("DB connected.")

        @app.on_event("shutdown")
        def shut_down():
            self._Session.close_all()
            self._engine.dispose()
            logging.info("DB disconnected.")


    def get_db(self):
        """
        요청시마다 DB세션 1개만 사용되도록 yield 후 close까지
        :return:
        """
        # 초기화 X -> Session cls없을 땐 에러
        if self._Session is None:
            raise Exception("must be called 'init_app'")

        # 세션 객체를 만들고, yield한 뒤, 돌아와서는 close까지 되도록
        db_session = None
        try:
            db_session = self._Session()
            yield db_session
        finally:
            db_session.close()

    # get_db를 프로퍼티명()으로 호출할 수 있게, 호출전 함수객체를 return하는 프로퍼티
    @property
    def session(self):
        return self.get_db

    # 이것은 수정불가능한 내부 객체를 가져와야만 할 때
    @property
    def engine(self):
        return self._engine






db = SQLAlchemy()
Base = declarative_base()

