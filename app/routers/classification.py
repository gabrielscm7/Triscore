from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.database import transaction
from app.dependencies import get_db
from app.services import classification as classification_service
from app.services import events as event_service
from app.templating import templates
from app.utils import redirect_with

router = APIRouter(prefix="/eventos/{event_id}/classificacao", tags=["classificacao"])


def require_event(connection: sqlite3.Connection, event_id: int) -> dict:
    event = event_service.get_event(connection, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")
    return event


@router.get("", response_class=HTMLResponse)
def classification_page(
    request: Request, event_id: int, db: sqlite3.Connection = Depends(get_db)
):
    event = require_event(db, event_id)
    tiebreak = classification_service.get_tiebreak(db, event_id)
    groups = classification_service.build_classification(
        db, event_id, tiebreak=tiebreak
    )
    stats = classification_service.classification_stats(groups)
    tie_warnings = classification_service.top_three_tie_warnings(groups)
    return templates.TemplateResponse(
        request=request,
        name="classification/index.html",
        context={
            "event": event,
            "groups": groups,
            "stats": stats,
            "tie_warnings": tie_warnings,
            "tiebreak": tiebreak,
            "tiebreak_options": classification_service.TIEBREAK_OPTIONS,
            "active": "classification",
        },
    )


@router.post("/desempate")
def update_tiebreak(
    request: Request,
    event_id: int,
    tiebreak: str = Form(""),
):
    try:
        with transaction(request.app.state.db_path) as db:
            require_event(db, event_id)
            classification_service.update_tiebreak(db, event_id, tiebreak)
    except ValueError as error:
        return redirect_with(
            f"/eventos/{event_id}/classificacao", error=str(error)
        )
    return redirect_with(
        f"/eventos/{event_id}/classificacao",
        ok="Critério de desempate atualizado.",
    )
