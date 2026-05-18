from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import settings


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


@router.get("/ui", response_class=HTMLResponse)
def ui(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="ui.html",
        context={
            "service_name": settings.service_name,
            "trainer_url": settings.hotword_trainer_url,
            "runtime_engine": settings.hotword_engine,
        },
    )


@router.get("/assistant", response_class=HTMLResponse)
def assistant(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="assistant.html",
        context={
            "service_name": settings.service_name,
            "trainer_url": settings.hotword_trainer_url,
            "runtime_engine": settings.hotword_engine,
        },
    )
