from dataclasses import asdict

from fastapi import FastAPI, Depends
from starlette.middleware.cors import CORSMiddleware

from app import api
from app.api.dependencies.auth import active_user
# from app.api.dependencies.auth import fastapi_users, auth_backend, active_user, cookie_backend
from app.common.config import Config
from app.database.conn import db
from app.middlewares.access_control import AccessControl
from app.middlewares.trusted_hosts import TrustedHostMiddleware
from app.models import Users
from app.routers import index
from app.schemas import UserRead, UserCreate


def create_app(config: Config):
    """
    앱 함수 실행
    :return:
    """
    app = FastAPI(
        version=config.APP_VERSION,
        title=config.APP_TITLE,
        description=config.APP_DESCRIPTION,
    )

    db.init_app(app)

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

    # fastapi-users
    # app.include_router(fastapi_users.get_auth_router(backend=auth_backend), tags=['auth']) # /login/logout
    # app.include_router(fastapi_users.get_register_router(user_schema=UserRead, user_create_schema=UserCreate), tags=['auth'])
    #
    # app.include_router(fastapi_users.get_auth_router(backend=cookie_backend), tags=['auth'], prefix='/cookie') # /login/logout

    @app.get("/authenticated-route")
    async def authenticated_route(user: Users = Depends(active_user)):
        return dict(
            message=f"Hello, {user.id}"
        )

    return app
