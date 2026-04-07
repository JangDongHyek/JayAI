from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import get_settings
from .routers.local import router as local_router


settings = get_settings()
templates = Jinja2Templates(directory=str(settings.templates_dir))


def create_local_app() -> FastAPI:
    app = FastAPI(title=f"{settings.app_name} Local", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"app_name": settings.app_name, "base_path": ""},
        )

    app.include_router(local_router)
    return app


app = create_local_app()
