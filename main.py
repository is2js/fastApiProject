import os

if __name__ == "__mp_main__":
    """Option 1: Skip section for multiprocess spawning
    This section will be skipped when running in multiprocessing mode"""
    pass

elif __name__ == '__main__':
    if os.getenv('API_ENV') != 'test':
        os.environ["API_ENV"] = "local"
    os.environ["DOCKER_MODE"] = "False"

    from app import create_app
    from app.common.config import config
    import uvicorn

    app = create_app(config)

    # uvicorn.run("app.main:app", port=config.PORT, reload=config.PROJ_RELOAD)
    uvicorn.run("main:app", port=config.PORT, reload=config.PROJ_RELOAD)

else:
    from app import create_app
    from app.common.config import config

    app = create_app(config)
