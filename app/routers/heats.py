from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.database import transaction
from app.dependencies import get_db
from app.services import events as event_service
from app.services import heats as heat_service
from app.templating import templates
from app.utils import redirect_with

router = APIRouter(prefix="/eventos/{event_id}/baterias", tags=["baterias"])


def require_event(connection: sqlite3.Connection, event_id: int) -> dict:
    event = event_service.get_event(connection, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")
    return event


class HeatOrderPayload(BaseModel):
    heat_ids: list[int]


class MoveAthletePayload(BaseModel):
    athlete_id: int
    target_heat_id: int | None = None
    before_athlete_id: int | None = None


class AthleteOrderPayload(BaseModel):
    athlete_ids: list[int]


@router.get("", response_class=HTMLResponse)
def heats_builder(
    request: Request, event_id: int, db: sqlite3.Connection = Depends(get_db)
):
    event = require_event(db, event_id)
    builder = heat_service.load_builder(db, event)
    return templates.TemplateResponse(
        request=request,
        name="heats/builder.html",
        context={**builder, "active": "heats"},
    )


@router.post("/gerar")
def generate_heats(
    request: Request,
    event_id: int,
    category_id: int = Form(...),
    sex_mode: str = Form("M"),
    criterion: str = Form("bib"),
):
    with transaction(request.app.state.db_path) as db:
        event = require_event(db, event_id)
        try:
            heat_count, athlete_count = heat_service.generate_heats(
                db,
                event,
                category_id=category_id,
                sex_mode=sex_mode,
                criterion=criterion,
            )
        except heat_service.HeatError as error:
            return redirect_with(
                f"/eventos/{event_id}/baterias", error=str(error)
            )
    return redirect_with(
        f"/eventos/{event_id}/baterias",
        ok=f"{athlete_count} atleta(s) distribuído(s) em {heat_count} bateria(s).",
    )


@router.post("/nova")
def create_empty_heat(
    request: Request,
    event_id: int,
    category_id: int = Form(...),
    sex_mode: str = Form("M"),
):
    with transaction(request.app.state.db_path) as db:
        event = require_event(db, event_id)
        try:
            heat_service.add_empty_heat(
                db, event, category_id=category_id, sex_mode=sex_mode
            )
        except heat_service.HeatError as error:
            return redirect_with(
                f"/eventos/{event_id}/baterias", error=str(error)
            )
    return redirect_with(
        f"/eventos/{event_id}/baterias", ok="Bateria vazia criada."
    )


@router.post("/{heat_id}/excluir")
def delete_heat(request: Request, event_id: int, heat_id: int):
    with transaction(request.app.state.db_path) as db:
        require_event(db, event_id)
        try:
            result = heat_service.delete_heat(db, event_id, heat_id)
        except heat_service.HeatError as error:
            return redirect_with(
                f"/eventos/{event_id}/baterias", error=str(error)
            )
    heat = result["heat"]
    message = f"Bateria {heat['label']} excluída."
    if result["athlete_count"]:
        message += f" {result['athlete_count']} atleta(s) voltaram para a lista de não alocados."
    return redirect_with(f"/eventos/{event_id}/baterias", ok=message)


@router.post("/{heat_id}/ordenar")
def sort_heat(
    request: Request,
    event_id: int,
    heat_id: int,
    criterion: str = Form("bib"),
):
    with transaction(request.app.state.db_path) as db:
        require_event(db, event_id)
        try:
            heat_service.sort_heat(db, event_id, heat_id, criterion)
        except heat_service.HeatError as error:
            return redirect_with(
                f"/eventos/{event_id}/baterias", error=str(error)
            )
    return redirect_with(
        f"/eventos/{event_id}/baterias", ok="Ordem de largada atualizada."
    )


@router.post("/{heat_id}/ordem-atletas")
def reorder_athletes(
    request: Request,
    event_id: int,
    heat_id: int,
    payload: AthleteOrderPayload,
):
    with transaction(request.app.state.db_path) as db:
        require_event(db, event_id)
        try:
            heat_service.reorder_heat_athletes(
                db, event_id, heat_id, payload.athlete_ids
            )
        except heat_service.HeatError as error:
            raise HTTPException(status_code=400, detail=str(error))
    return {"ok": True}


@router.post("/ordem")
def reorder_heats(
    request: Request,
    event_id: int,
    payload: HeatOrderPayload,
):
    with transaction(request.app.state.db_path) as db:
        require_event(db, event_id)
        try:
            heat_service.reorder_heats(db, event_id, payload.heat_ids)
        except heat_service.HeatError as error:
            raise HTTPException(status_code=400, detail=str(error))
    return {"ok": True}


@router.post("/mover-atleta")
def move_athlete(
    request: Request,
    event_id: int,
    payload: MoveAthletePayload,
):
    with transaction(request.app.state.db_path) as db:
        event = require_event(db, event_id)
        try:
            heat_service.move_athlete(
                db,
                event,
                athlete_id=payload.athlete_id,
                target_heat_id=payload.target_heat_id,
                before_athlete_id=payload.before_athlete_id,
            )
        except heat_service.HeatError as error:
            raise HTTPException(status_code=400, detail=str(error))
    return {"ok": True}
