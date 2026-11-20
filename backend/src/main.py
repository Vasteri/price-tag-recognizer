from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from .api.router import api_router
from .core.exceptions import AppException


def create_app() -> FastAPI:
    app = FastAPI(root_path="/api", title="Recognizer API")
    Instrumentator().instrument(app).expose(app)

    @app.exception_handler(AppException)
    async def handle_app_exception(_: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    app.include_router(api_router)
    return app


app = create_app()