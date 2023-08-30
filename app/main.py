from dataclasses import asdict

import uvicorn
from fastapi import FastAPI

from app.common.config import conf
from app.database.conn import db
from app.router import index


def create_app():
    """
    앱 함수 실행
    :return:
    """
    app = FastAPI()

    config = conf()
    config_dict = asdict(config)

    db.init_app(app, **config_dict)

    # route 등록
    app.include_router(index.router)

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
