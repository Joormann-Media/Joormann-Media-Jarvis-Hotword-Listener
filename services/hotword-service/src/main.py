from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .api_routes import router as api_router
from .api_routes import build_error_response
from .runtime import initialize_runtime, shutdown_runtime
from .storage import ensure_storage
from .ui_routes import router as ui_router


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Jarvis V2 Hotword Service",
    version="0.1.0",
    description="Lokales Hotword Lab und Runtime Placeholder fuer Jarvis V2",
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(api_router)
app.include_router(ui_router)


@app.on_event("startup")
def startup() -> None:
    ensure_storage()
    initialize_runtime()


@app.on_event("shutdown")
def shutdown() -> None:
    shutdown_runtime()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return build_error_response(str(exc), "validation_error", status.HTTP_422_UNPROCESSABLE_ENTITY)


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(_: Request, exc: ValidationError) -> JSONResponse:
    return build_error_response(str(exc), "validation_error", status.HTTP_422_UNPROCESSABLE_ENTITY)
