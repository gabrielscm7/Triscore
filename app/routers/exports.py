from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from app.dependencies import get_db
from app.services import events as event_service
from app.services import pdf_exports

router = APIRouter(prefix="/eventos/{event_id}/pdfs", tags=["pdfs"])


def require_event(connection: sqlite3.Connection, event_id: int) -> dict:
    event = event_service.get_event(connection, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")
    return event


def _response(path) -> FileResponse:
    if not path.exists():
        raise HTTPException(status_code=500, detail="Não foi possível gerar o PDF.")
    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=path.name,
    )


@router.get("/cronograma")
def export_cronograma(
    request: Request,
    event_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    event = require_event(db, event_id)
    path = pdf_exports.export_cronograma(
        db, event, exports_dir=request.app.state.exports_dir
    )
    return _response(path)


@router.get("/lista-largada")
def export_start_list(
    request: Request,
    event_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    event = require_event(db, event_id)
    path = pdf_exports.export_start_list(
        db, event, exports_dir=request.app.state.exports_dir
    )
    return _response(path)


@router.get("/relatorio-final")
def export_final_report(
    request: Request,
    event_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    event = require_event(db, event_id)
    path = pdf_exports.export_final_report(
        db, event, exports_dir=request.app.state.exports_dir
    )
    return _response(path)
