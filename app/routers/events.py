from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.database import transaction
from app.dependencies import get_db
from app.services import events as event_service
from app.templating import templates
from app.utils import (
    clean_text,
    parse_clock_minutes,
    parse_date_input,
    parse_optional_int,
    redirect_with,
)

router = APIRouter(prefix="/eventos", tags=["eventos"])


def require_event(connection: sqlite3.Connection, event_id: int) -> dict:
    event = event_service.get_event(connection, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")
    return event


@router.get("", response_class=HTMLResponse)
def events_index(request: Request, db: sqlite3.Connection = Depends(get_db)):
    events = event_service.list_events(db)
    return templates.TemplateResponse(
        request=request,
        name="events/list.html",
        context={"event": None, "events": events, "active": "events"},
    )


@router.post("")
def create_event(
    request: Request,
    name: str = Form(""),
    event_date: str = Form(""),
    location: str = Form(""),
):
    name = clean_text(name, 160)
    location = clean_text(location, 160)
    if not name:
        return redirect_with("/eventos", error="Informe o nome da prova.")
    try:
        parsed_date = parse_date_input(event_date)
    except ValueError:
        return redirect_with("/eventos", error="Data da prova inválida.")

    with transaction(request.app.state.db_path) as db:
        event_id = event_service.create_event(
            db, name=name, event_date=parsed_date, location=location
        )
    return redirect_with(
        f"/eventos/{event_id}/configuracao",
        ok="Prova criada. Configure as categorias e o cronograma.",
    )


@router.get("/{event_id}", response_class=RedirectResponse)
def event_home(event_id: int):
    return RedirectResponse(url=f"/eventos/{event_id}/configuracao", status_code=303)


@router.get("/{event_id}/configuracao", response_class=HTMLResponse)
def event_settings(
    request: Request,
    event_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    event = require_event(db, event_id)
    stats = event_service.event_stats(db, event_id)
    return templates.TemplateResponse(
        request=request,
        name="events/config.html",
        context={
            "event": event,
            "stats": stats,
            "active": "settings",
        },
    )


@router.get("/{event_id}/categorias", response_class=HTMLResponse)
def categories_page(
    request: Request,
    event_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    event = require_event(db, event_id)
    categories = event_service.list_categories(db, event_id)
    return templates.TemplateResponse(
        request=request,
        name="events/categories.html",
        context={
            "event": event,
            "categories": categories,
            "classification_modes": event_service.CATEGORY_CLASSIFICATION_MODES,
            "active": "categories",
        },
    )


@router.post("/{event_id}/configuracao")
def update_event_settings(
    request: Request,
    event_id: int,
    name: str = Form(""),
    event_date: str = Form(""),
    location: str = Form(""),
    heat_limit: str = Form("10"),
    schedule_enabled: str | None = Form(None),
    schedule_start: str = Form("08:00"),
    athlete_interval_seconds: str = Form("60"),
    heat_interval_seconds: str = Form("300"),
):
    with transaction(request.app.state.db_path) as db:
        require_event(db, event_id)
        name = clean_text(name, 160)
        location = clean_text(location, 160)
        if not name:
            return redirect_with(
                f"/eventos/{event_id}/configuracao", error="Informe o nome da prova."
            )
        try:
            parsed_date = parse_date_input(event_date)
            limit = int(heat_limit)
            athlete_interval = int(athlete_interval_seconds)
            heat_interval = int(heat_interval_seconds)
            hour, minute = parse_clock_minutes(schedule_start)
        except (ValueError, TypeError):
            return redirect_with(
                f"/eventos/{event_id}/configuracao",
                error="Confira a data, os limites e os intervalos informados.",
            )
        if limit < 1 or limit > 1000:
            return redirect_with(
                f"/eventos/{event_id}/configuracao",
                error="O limite por bateria deve estar entre 1 e 1000.",
            )
        if not (0 <= athlete_interval <= 86400 and 0 <= heat_interval <= 86400):
            return redirect_with(
                f"/eventos/{event_id}/configuracao",
                error="Os intervalos devem estar entre 0 e 86400 segundos.",
            )

        event_service.update_event(
            db,
            event_id,
            name=name,
            event_date=parsed_date,
            location=location,
            heat_limit=limit,
            schedule_enabled=schedule_enabled is not None,
            schedule_start=f"{hour:02d}:{minute:02d}",
            athlete_interval_seconds=athlete_interval,
            heat_interval_seconds=heat_interval,
        )
        overfull = db.execute(
            """
            SELECT COUNT(*) AS total FROM (
                SELECT heat_id, COUNT(*) AS entries
                FROM heat_entries
                GROUP BY heat_id
                HAVING COUNT(*) > ?
            )
            """,
            (limit,),
        ).fetchone()["total"]
    warning = (
        "Atenção: existem baterias acima do novo limite configurado."
        if overfull
        else None
    )
    return redirect_with(
        f"/eventos/{event_id}/configuracao",
        ok="Configuração da prova atualizada.",
        warning=warning,
    )


@router.post("/{event_id}/categorias")
def add_category(
    request: Request,
    event_id: int,
    name: str = Form(""),
    min_age: str = Form(""),
    max_age: str = Form(""),
    classification_mode: str = Form("separate"),
):
    page_url = f"/eventos/{event_id}/categorias"
    name = clean_text(name, 80)
    if not name:
        return redirect_with(page_url, error="Informe o nome da categoria.")
    try:
        min_value = parse_optional_int(min_age)
        max_value = parse_optional_int(max_age)
    except ValueError:
        return redirect_with(
            page_url, error="As idades da categoria devem ser numéricas."
        )
    if min_value is not None and not (0 <= min_value <= 120):
        return redirect_with(page_url, error="Idade mínima inválida.")
    if max_value is not None and not (0 <= max_value <= 120):
        return redirect_with(page_url, error="Idade máxima inválida.")
    if min_value is not None and max_value is not None and min_value > max_value:
        return redirect_with(
            page_url, error="A idade mínima não pode ser maior que a máxima."
        )
    try:
        with transaction(request.app.state.db_path) as db:
            require_event(db, event_id)
            event_service.create_category(
                db,
                event_id=event_id,
                name=name,
                min_age=min_value,
                max_age=max_value,
                classification_mode=classification_mode,
            )
    except ValueError as error:
        return redirect_with(page_url, error=str(error))
    except sqlite3.IntegrityError:
        return redirect_with(
            page_url, error="Já existe uma categoria com esse nome nesta prova."
        )
    return redirect_with(page_url, ok="Categoria criada.")


@router.post("/{event_id}/categorias/{category_id}/editar")
def edit_category(
    request: Request,
    event_id: int,
    category_id: int,
    name: str = Form(""),
    min_age: str = Form(""),
    max_age: str = Form(""),
    classification_mode: str = Form("separate"),
):
    page_url = f"/eventos/{event_id}/categorias"
    name = clean_text(name, 80)
    if not name:
        return redirect_with(page_url, error="Informe o nome da categoria.")
    try:
        min_value = parse_optional_int(min_age)
        max_value = parse_optional_int(max_age)
    except ValueError:
        return redirect_with(
            page_url, error="As idades da categoria devem ser numéricas."
        )
    if min_value is not None and not (0 <= min_value <= 120):
        return redirect_with(page_url, error="Idade mínima inválida.")
    if max_value is not None and not (0 <= max_value <= 120):
        return redirect_with(page_url, error="Idade máxima inválida.")
    if min_value is not None and max_value is not None and min_value > max_value:
        return redirect_with(
            page_url, error="A idade mínima não pode ser maior que a máxima."
        )
    try:
        with transaction(request.app.state.db_path) as db:
            require_event(db, event_id)
            event_service.update_category(
                db,
                event_id=event_id,
                category_id=category_id,
                name=name,
                min_age=min_value,
                max_age=max_value,
                classification_mode=classification_mode,
            )
    except ValueError as error:
        return redirect_with(page_url, error=str(error))
    except sqlite3.IntegrityError:
        return redirect_with(
            page_url, error="Já existe uma categoria com esse nome nesta prova."
        )
    return redirect_with(page_url, ok="Categoria atualizada.")


@router.post("/{event_id}/categorias/{category_id}/excluir")
def remove_category(request: Request, event_id: int, category_id: int):
    page_url = f"/eventos/{event_id}/categorias"
    with transaction(request.app.state.db_path) as db:
        require_event(db, event_id)
        deleted, error = event_service.delete_category(db, event_id, category_id)
    if not deleted:
        return redirect_with(page_url, error=error)
    return redirect_with(page_url, ok="Categoria excluída.")
