from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.database import transaction
from app.dependencies import get_db
from app.services import events as event_service
from app.services import teams as team_service
from app.templating import templates
from app.utils import redirect_with

router = APIRouter(prefix="/eventos/{event_id}/equipes", tags=["equipes"])


def require_event(connection: sqlite3.Connection, event_id: int) -> dict:
    event = event_service.get_event(connection, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")
    return event


@router.get("", response_class=HTMLResponse)
def teams_page(
    request: Request, event_id: int, db: sqlite3.Connection = Depends(get_db)
):
    event = require_event(db, event_id)
    teams = team_service.list_teams(db, event_id)
    return templates.TemplateResponse(
        request=request,
        name="teams/index.html",
        context={
            "event": event,
            "teams": teams,
            "active": "teams",
        },
    )


@router.post("")
def create_team(
    request: Request,
    event_id: int,
    name: str = Form(""),
):
    try:
        with transaction(request.app.state.db_path) as db:
            require_event(db, event_id)
            team_service.create_team(db, event_id, name)
    except (ValueError, sqlite3.IntegrityError) as error:
        message = (
            str(error)
            if isinstance(error, ValueError)
            else "Já existe uma equipe com esse nome nesta prova."
        )
        return redirect_with(f"/eventos/{event_id}/equipes", error=message)
    return redirect_with(f"/eventos/{event_id}/equipes", ok="Equipe criada.")


@router.post("/{team_id}/editar")
def edit_team(
    request: Request,
    event_id: int,
    team_id: int,
    name: str = Form(""),
):
    try:
        with transaction(request.app.state.db_path) as db:
            require_event(db, event_id)
            team_service.update_team(db, event_id, team_id, name)
    except (ValueError, sqlite3.IntegrityError) as error:
        message = (
            str(error)
            if isinstance(error, ValueError)
            else "Já existe uma equipe com esse nome nesta prova."
        )
        return redirect_with(f"/eventos/{event_id}/equipes", error=message)
    return redirect_with(f"/eventos/{event_id}/equipes", ok="Equipe atualizada.")


@router.post("/{team_id}/excluir")
def remove_team(request: Request, event_id: int, team_id: int):
    with transaction(request.app.state.db_path) as db:
        require_event(db, event_id)
        deleted, error = team_service.delete_team(db, event_id, team_id)
    if not deleted:
        return redirect_with(f"/eventos/{event_id}/equipes", error=error)
    return redirect_with(f"/eventos/{event_id}/equipes", ok="Equipe excluída.")
