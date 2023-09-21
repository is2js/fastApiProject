import asyncio
import os

# if __name__ == "__mp_main__":
#     """Option 1: Skip section for multiprocess spawning
#     This section will be skipped when running in multiprocessing mode"""
#     pass
#
# elif __name__ == '__main__':
if __name__ == "__mp_main__":
    if os.getenv('API_ENV') != 'test':
        os.environ["API_ENV"] = "local"

    os.environ["DOCKER_MODE"] = "False"

    from app.common.config import config
    from app import create_app
    import uvicorn

    app = create_app(config)

    # uvicorn.run("app.main:app", port=config.PORT, reload=config.PROJ_RELOAD)
    event_loop = asyncio.get_event_loop()
    event_loop.run_until_complete(
        uvicorn.run("main:app", port=config.PORT, reload=config.PROJ_RELOAD)
    )

else:
    # docker 용
    from app.common.config import config
    from app import create_app

    app = create_app(config)
