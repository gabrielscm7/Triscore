from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.dependencies import get_db

router = APIRouter(tags=["sistema"])


@router.get("/health")
def health(request: Request, db: sqlite3.Connection = Depends(get_db)):
    db.execute("SELECT 1").fetchone()
    environment = request.app.state.environment
    return {
        "status": "ok",
        "app": "Triscore",
        "environment": environment.name,
        "database": str(request.app.state.db_path),
        "version": 1,
    }


@router.post("/encerrar", response_class=HTMLResponse)
def shutdown(request: Request):
    handler = getattr(request.app.state, "shutdown_handler", None)
    if handler is None:
        return HTMLResponse(
            "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
            "<title>Triscore</title><body><h1>Encerramento indisponível</h1>"
            "<p>O servidor não foi iniciado pelo launcher do Triscore.</p>"
            "</body></html>",
            status_code=409,
        )
    handler()
    return HTMLResponse(
        "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
        "<title>Triscore</title><body><h1>Triscore encerrado</h1>"
        "<p>O backup de encerramento foi criado. Você já pode fechar esta aba.</p>"
        "</body></html>"
    )
