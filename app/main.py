from dataclasses import asdict

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.common.config import conf
from app.database.conn import db
from app.middlewares.access_control import AccessControl
from app.middlewares.trusted_hosts import TrustedHostMiddleware
from app import api
from app.routers import index


def create_app():
    """
    앱 함수 실행
    :return:
    """
    app = FastAPI()

    config = conf()
    print("config", config)
    config_dict = asdict(config)
    print("config_dict", config_dict)
    db.init_app(app, **config_dict)

    # 미들웨어 추가 (실행순서는 반대)
    app.add_middleware(AccessControl)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOW_SITE,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.TRUSTED_HOSTS, except_path=["/health"])

    # route 등록
    app.include_router(index.router) # template or test
    app.include_router(api.router, prefix='/api')
    # app.include_router(auth.router, tags=["Authentication"], prefix="/api")
    # app.include_router(user.router, tags=["Users"], prefix="/api", dependencies=[Depends(API_KEY_HEADER)])

    return app


app = create_app()

# @app.get("/")
# async def root():
#     return {"message": "Hello World"}
#
#
# @app.get("/hello/{name}")
# async def say_hello(name: str):
#     return {"message": f"Hello {name}"}


if __name__ == '__main__':
    # uvicorn.run("main:app", port=8010, reload=True)
    uvicorn.run("main:app", port=8010, reload=conf().PROJ_RELOAD)
