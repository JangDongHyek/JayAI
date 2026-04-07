from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import get_settings
from .db import init_db
from .routers import devices_router, projects_router, runner_router


settings = get_settings()
templates = Jinja2Templates(directory=str(settings.templates_dir))


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0")

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"app_name": settings.app_name},
        )

    app.include_router(projects_router)
    app.include_router(devices_router)
    app.include_router(runner_router)
    return app


app = create_app()

