from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response

from app.database import transaction
from app.dependencies import get_db
from app.services import athletes as athlete_service
from app.services import csv_import
from app.services import events as event_service
from app.services import teams as team_service
from app.templating import templates
from app.utils import clean_text, next_bib, redirect_with

router = APIRouter(prefix="/eventos/{event_id}/atletas", tags=["atletas"])


def require_event(connection: sqlite3.Connection, event_id: int) -> dict:
    event = event_service.get_event(connection, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")
    return event


def _form_context(
    request: Request,
    *,
    event: dict,
    categories: list[dict],
    teams: list[dict],
    athlete: dict,
    next_bib_value: int,
    is_edit: bool,
    form_error: str | None = None,
):
    return templates.TemplateResponse(
        request=request,
        name="athletes/form.html",
        context={
            "event": event,
            "categories": categories,
            "teams": teams,
            "athlete": athlete,
            "next_bib": next_bib_value,
            "is_edit": is_edit,
            "form_error": form_error,
            "active": "athletes",
        },
        status_code=422 if form_error else 200,
    )


@router.get("", response_class=HTMLResponse)
def athletes_list(
    request: Request,
    event_id: int,
    q: str = "",
    category_id: int | None = None,
    team_id: int | None = None,
    sex: str = "",
    db: sqlite3.Connection = Depends(get_db),
):
    event = require_event(db, event_id)
    categories = event_service.list_categories(db, event_id)
    teams = team_service.list_teams(db, event_id)
    athletes = athlete_service.list_athletes(
        db,
        event_id,
        query=clean_text(q),
        category_id=category_id,
        team_id=team_id,
        sex=sex if sex in ("M", "F") else None,
    )
    return templates.TemplateResponse(
        request=request,
        name="athletes/list.html",
        context={
            "event": event,
            "athletes": athletes,
            "categories": categories,
            "teams": teams,
            "filters": {
                "q": q,
                "category_id": category_id,
                "team_id": team_id,
                "sex": sex,
            },
            "active": "athletes",
        },
    )


@router.get("/novo", response_class=HTMLResponse)
def athlete_new(
    request: Request, event_id: int, db: sqlite3.Connection = Depends(get_db)
):
    event = require_event(db, event_id)
    categories = event_service.list_categories(db, event_id)
    teams = team_service.list_teams(db, event_id)
    return _form_context(
        request,
        event=event,
        categories=categories,
        teams=teams,
        athlete={
            "name": "",
            "age": "",
            "category_id": None,
            "team_id": None,
            "sex": "",
            "bib": "",
        },
        next_bib_value=next_bib(db, event_id),
        is_edit=False,
    )


@router.post("/novo")
def athlete_create(
    request: Request,
    event_id: int,
    name: str = Form(""),
    age: str = Form(""),
    category_id: str = Form(""),
    team_id: str = Form(""),
    sex: str = Form(""),
    bib: str = Form(""),
):
    with transaction(request.app.state.db_path) as db:
        event = require_event(db, event_id)
        categories = event_service.list_categories(db, event_id)
        teams = team_service.list_teams(db, event_id)
        values, errors, warning = athlete_service.validate_fields(
            db,
            event_id,
            name=name,
            age=age,
            category_id=category_id,
            team_id=team_id,
            sex=sex,
            bib=bib,
        )
        if errors:
            return _form_context(
                request,
                event=event,
                categories=categories,
                teams=teams,
                athlete={
                    "name": name,
                    "age": age,
                    "category_id": category_id,
                    "team_id": team_id,
                    "sex": sex.upper(),
                    "bib": bib,
                },
                next_bib_value=next_bib(db, event_id),
                is_edit=False,
                form_error=" ".join(errors),
            )
        try:
            athlete_service.create_athlete(
                db,
                event_id=event_id,
                category_id=values["category_id"],
                name=values["name"],
                age=values["age"],
                team_id=values["team_id"],
                sex=values["sex"],
                bib=values["bib"],
            )
        except sqlite3.IntegrityError:
            return _form_context(
                request,
                event=event,
                categories=categories,
                teams=teams,
                athlete={
                    "name": name,
                    "age": age,
                    "category_id": category_id,
                    "team_id": team_id,
                    "sex": sex.upper(),
                    "bib": bib,
                },
                next_bib_value=next_bib(db, event_id),
                is_edit=False,
                form_error="O número de peito informado já está em uso nesta prova.",
            )
    return redirect_with(
        f"/eventos/{event_id}/atletas",
        ok=f"Atleta {values['name']} cadastrado.",
        warning=warning,
    )


@router.get("/importar", response_class=HTMLResponse)
def import_page(
    request: Request, event_id: int, db: sqlite3.Connection = Depends(get_db)
):
    event = require_event(db, event_id)
    return templates.TemplateResponse(
        request=request,
        name="athletes/import.html",
        context={"event": event, "active": "athletes"},
    )


@router.post("/importar/previa")
async def import_preview(
    request: Request,
    event_id: int,
    file: UploadFile = File(...),
):
    content = await file.read()
    try:
        with transaction(request.app.state.db_path) as connection:
            require_event(connection, event_id)
            batch_id = csv_import.prepare_batch(
                connection,
                event_id=event_id,
                filename=file.filename or "atletas.csv",
                content=content,
            )
    except csv_import.CSVImportError as error:
        return redirect_with(
            f"/eventos/{event_id}/atletas/importar", error=str(error)
        )
    return redirect_with(
        f"/eventos/{event_id}/atletas/importar/{batch_id}", ok="Prévia gerada."
    )


@router.get("/importar/{batch_id}", response_class=HTMLResponse)
def import_preview_page(
    request: Request,
    event_id: int,
    batch_id: str,
    db: sqlite3.Connection = Depends(get_db),
):
    event = require_event(db, event_id)
    batch, rows, counts = csv_import.preview_batch(db, event_id, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Prévia de importação não encontrada.")
    return templates.TemplateResponse(
        request=request,
        name="athletes/import_preview.html",
        context={
            "event": event,
            "batch": batch,
            "rows": rows,
            "counts": counts,
            "active": "athletes",
        },
    )


@router.post("/importar/{batch_id}/confirmar")
def import_confirm(request: Request, event_id: int, batch_id: str):
    with transaction(request.app.state.db_path) as db:
        require_event(db, event_id)
        try:
            summary = csv_import.confirm_batch(db, event_id, batch_id)
        except csv_import.CSVImportError as error:
            return redirect_with(
                f"/eventos/{event_id}/atletas/importar", error=str(error)
            )
    warning = None
    if summary["skipped"]:
        details = " ".join(summary["skipped"][:3])
        if len(summary["skipped"]) > 3:
            details += f" Mais {len(summary['skipped']) - 3} linha(s) ignorada(s)."
        warning = f"{len(summary['skipped'])} linha(s) ignorada(s). {details}"
    if summary["imported"] == 0:
        return redirect_with(
            f"/eventos/{event_id}/atletas/importar",
            error="Nenhum atleta foi importado. " + (warning or ""),
        )
    created_parts = []
    if summary["categories_created"]:
        created_parts.append(f"{summary['categories_created']} categoria(s) criada(s)")
    if summary["teams_created"]:
        created_parts.append(f"{summary['teams_created']} equipe(s) criada(s)")
    created_message = (
        " " + ", ".join(created_parts) + "." if created_parts else ""
    )
    return redirect_with(
        f"/eventos/{event_id}/atletas",
        ok=f"{summary['imported']} atleta(s) importado(s).{created_message}",
        warning=warning,
    )


@router.post("/importar/{batch_id}/cancelar")
def import_cancel(request: Request, event_id: int, batch_id: str):
    with transaction(request.app.state.db_path) as db:
        require_event(db, event_id)
        csv_import.cancel_batch(db, event_id, batch_id)
    return redirect_with(
        f"/eventos/{event_id}/atletas/importar", ok="Importação cancelada."
    )


@router.get("/importar/{batch_id}/erros.csv")
def import_errors_csv(
    event_id: int, batch_id: str, db: sqlite3.Connection = Depends(get_db)
):
    require_event(db, event_id)
    try:
        payload = csv_import.errors_csv(db, event_id, batch_id)
    except csv_import.CSVImportError as error:
        raise HTTPException(status_code=404, detail=str(error))
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=relatorio_importacao.csv"
        },
    )


@router.get("/{athlete_id}/editar", response_class=HTMLResponse)
def athlete_edit(
    request: Request,
    event_id: int,
    athlete_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    event = require_event(db, event_id)
    athlete = athlete_service.get_athlete(db, event_id, athlete_id)
    if athlete is None:
        raise HTTPException(status_code=404, detail="Atleta não encontrado.")
    categories = event_service.list_categories(db, event_id)
    teams = team_service.list_teams(db, event_id)
    return _form_context(
        request,
        event=event,
        categories=categories,
        teams=teams,
        athlete=athlete,
        next_bib_value=next_bib(db, event_id),
        is_edit=True,
    )


@router.post("/{athlete_id}/editar")
def athlete_update(
    request: Request,
    event_id: int,
    athlete_id: int,
    name: str = Form(""),
    age: str = Form(""),
    category_id: str = Form(""),
    team_id: str = Form(""),
    sex: str = Form(""),
    bib: str = Form(""),
):
    with transaction(request.app.state.db_path) as db:
        event = require_event(db, event_id)
        current = athlete_service.get_athlete(db, event_id, athlete_id)
        if current is None:
            raise HTTPException(status_code=404, detail="Atleta não encontrado.")
        categories = event_service.list_categories(db, event_id)
        teams = team_service.list_teams(db, event_id)
        values, errors, warning = athlete_service.validate_fields(
            db,
            event_id,
            name=name,
            age=age,
            category_id=category_id,
            team_id=team_id,
            sex=sex,
            bib=bib,
            exclude_athlete_id=athlete_id,
        )
        if errors:
            current.update(
                {
                    "name": name,
                    "age": age,
                    "category_id": category_id,
                    "team_id": team_id,
                    "sex": sex.upper(),
                    "bib": bib,
                }
            )
            return _form_context(
                request,
                event=event,
                categories=categories,
                teams=teams,
                athlete=current,
                next_bib_value=next_bib(db, event_id),
                is_edit=True,
                form_error=" ".join(errors),
            )
        try:
            result = athlete_service.update_athlete(
                db,
                event_id=event_id,
                athlete_id=athlete_id,
                category_id=values["category_id"],
                name=values["name"],
                age=values["age"],
                team_id=values["team_id"],
                sex=values["sex"],
                bib=values["bib"],
            )
        except sqlite3.IntegrityError:
            current.update(
                {
                    "name": name,
                    "age": age,
                    "category_id": category_id,
                    "team_id": team_id,
                    "sex": sex.upper(),
                    "bib": bib,
                }
            )
            return _form_context(
                request,
                event=event,
                categories=categories,
                teams=teams,
                athlete=current,
                next_bib_value=next_bib(db, event_id),
                is_edit=True,
                form_error="O número de peito informado já está em uso nesta prova.",
            )
    warning_parts = [part for part in (warning, result["age_warning"]) if part]
    if result["removed_heat"]:
        warning_parts.append(
            "O atleta foi removido da bateria "
            f"{result['removed_heat']['label']} porque a categoria ou o sexo mudou."
        )
    return redirect_with(
        f"/eventos/{event_id}/atletas",
        ok=f"Atleta {values['name']} atualizado.",
        warning=" ".join(warning_parts) or None,
    )


@router.post("/{athlete_id}/excluir")
def athlete_delete(request: Request, event_id: int, athlete_id: int):
    with transaction(request.app.state.db_path) as db:
        require_event(db, event_id)
        removed = athlete_service.delete_athlete(db, event_id, athlete_id)
    if removed is None:
        return redirect_with(
            f"/eventos/{event_id}/atletas", error="Atleta não encontrado."
        )
    warning = None
    if removed["heat_id"] is not None:
        warning = f"O atleta também foi removido da bateria {removed['heat_label']}."
    return redirect_with(
        f"/eventos/{event_id}/atletas",
        ok=f"Atleta {removed['name']} excluído.",
        warning=warning,
    )
