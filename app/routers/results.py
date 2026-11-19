from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.database import backup_database, transaction
from app.dependencies import get_db
from app.services import events as event_service
from app.services import results as result_service
from app.templating import templates
from app.utils import redirect_with

router = APIRouter(prefix="/eventos/{event_id}/sumula", tags=["sumula"])


def require_event(connection: sqlite3.Connection, event_id: int) -> dict:
    event = event_service.get_event(connection, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")
    return event


def _create_backup(request: Request) -> None:
    backup_database(
        request.app.state.db_path,
        prefix="triscore-pre-sumula",
        backup_dir=request.app.state.backup_dir,
    )


@router.get("", response_class=HTMLResponse)
def results_page(
    request: Request, event_id: int, db: sqlite3.Connection = Depends(get_db)
):
    event = require_event(db, event_id)
    results = result_service.list_results(db, event_id)
    stats = result_service.result_stats(db, event_id)
    return templates.TemplateResponse(
        request=request,
        name="results/summary.html",
        context={
            "event": event,
            "results": results,
            "stats": stats,
            "status_labels": result_service.STATUS_LABELS,
            "active": "results",
        },
    )


@router.post("/{athlete_id}")
def save_result(
    request: Request,
    event_id: int,
    athlete_id: int,
    status: str = Form(""),
    final_time: str = Form(""),
):
    try:
        parsed_status, final_time_cs = result_service.parse_result_fields(
            status, final_time
        )
    except ValueError as error:
        return redirect_with(
            f"/eventos/{event_id}/sumula", error=str(error)
        )

    _create_backup(request)
    try:
        with transaction(request.app.state.db_path) as db:
            require_event(db, event_id)
            athlete = db.execute(
                "SELECT name FROM athletes WHERE id = ? AND event_id = ?",
                (athlete_id, event_id),
            ).fetchone()
            if athlete is None:
                raise ValueError("Atleta não encontrado nesta prova.")
            result_service.save_result(
                db,
                event_id=event_id,
                athlete_id=athlete_id,
                status=parsed_status,
                final_time_cs=final_time_cs,
            )
            athlete_name = athlete["name"]
    except ValueError as error:
        return redirect_with(f"/eventos/{event_id}/sumula", error=str(error))

    return redirect_with(
        f"/eventos/{event_id}/sumula",
        ok=f"Resultado de {athlete_name} salvo.",
    )


@router.post("/{athlete_id}/excluir")
def remove_result(request: Request, event_id: int, athlete_id: int):
    _create_backup(request)
    with transaction(request.app.state.db_path) as db:
        require_event(db, event_id)
        deleted = result_service.delete_result(db, event_id, athlete_id)
    if not deleted:
        return redirect_with(
            f"/eventos/{event_id}/sumula",
            error="Este atleta ainda não possui resultado lançado.",
        )
    return redirect_with(
        f"/eventos/{event_id}/sumula", ok="Resultado excluído."
    )
