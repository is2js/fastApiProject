from dataclasses import asdict

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app import api
from app.common.config import Config
from app.database.conn import db
from app.middlewares.access_control import AccessControl
from app.middlewares.trusted_hosts import TrustedHostMiddleware
from app.routers import index


def create_app(config: Config):
    """
    앱 함수 실행
    :return:
    """
    app = FastAPI()

    db.init_app(app, **asdict(config))

    # 미들웨어 추가 (실행순서는 반대)
    app.add_middleware(AccessControl)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOWED_SITES,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.TRUSTED_HOSTS, except_path=["/health"])

    # route 등록
    app.include_router(index.router)  # template or test
    app.include_router(api.router, prefix='/api')

    return app
