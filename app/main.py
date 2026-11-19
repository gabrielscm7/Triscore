from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.database import init_db, resolve_db_path
from app.environment import create_environment
from app.paths import STATIC_DIR
from app.routers import (
    athletes,
    awards,
    backups,
    classification,
    events,
    exports,
    heats,
    results,
    system,
    teams,
)
from app.templating import templates


def create_app(db_path: str | Path | None = None) -> FastAPI:
    resolved_db = resolve_db_path(db_path)
    environment = create_environment(resolved_db)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(app.state.db_path, backup_dir=app.state.backup_dir)
        yield

    app = FastAPI(title="Triscore", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.environment = environment
    app.state.db_path = resolved_db
    app.state.data_dir = environment.data_dir
    app.state.backup_dir = environment.backup_dir
    app.state.exports_dir = environment.exports_dir
    app.state.awards_media_dir = environment.awards_media_dir
    app.state.logs_dir = environment.logs_dir
    app.state.log_file = None
    app.state.shutdown_handler = None
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(events.router)
    app.include_router(backups.router)
    app.include_router(teams.router)
    app.include_router(athletes.router)
    app.include_router(heats.router)
    app.include_router(results.router)
    app.include_router(classification.router)
    app.include_router(exports.router)
    app.include_router(awards.router)
    app.include_router(system.router)

    @app.get("/", include_in_schema=False)
    def index():
        return RedirectResponse(url="/eventos", status_code=303)

    @app.exception_handler(404)
    async def not_found(request: Request, exc):
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            context={"event": None, "message": getattr(exc, "detail", "Página não encontrada.")},
            status_code=404,
        )

    return app


app = create_app()
