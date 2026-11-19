from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from app.database import transaction
from app.dependencies import get_db
from app.services import award_assets
from app.services import awards as award_service
from app.services import events as event_service
from app.services import pdf_exports
from app.templating import templates
from app.utils import redirect_with

router = APIRouter(prefix="/premiacao", tags=["premiacao"])


def require_event(connection: sqlite3.Connection, event_id: int) -> dict:
    event = event_service.get_event(connection, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Prova não encontrada.")
    return event


@router.get("", response_class=HTMLResponse)
def awards_selector(request: Request, db: sqlite3.Connection = Depends(get_db)):
    events = event_service.list_events(db)
    return templates.TemplateResponse(
        request=request,
        name="awards/select.html",
        context={
            "event": None,
            "events": events,
            "active": "awards",
        },
    )


@router.get("/{event_id}", response_class=HTMLResponse)
def awards_page(
    request: Request, event_id: int, db: sqlite3.Connection = Depends(get_db)
):
    event = require_event(db, event_id)
    settings = award_service.get_settings(db, event_id)
    theme = award_service.resolve_theme(settings)
    data = award_service.build_awards(db, event_id)
    for kind in ("banner", "background", "font"):
        filename = settings.get(f"{kind}_filename")
        theme[f"{kind}_url"] = (
            f"/premiacao/{event_id}/asset/{kind}?v={filename}" if filename else None
        )
    return templates.TemplateResponse(
        request=request,
        name="awards/show.html",
        context={
            "event": event,
            "groups": data["groups"],
            "stats": data["stats"],
            "settings": settings,
            "theme": theme,
            "presets": award_service.PRESETS,
            "layouts": award_service.LAYOUTS,
            "active": "awards",
        },
    )


@router.post("/{event_id}/tema")
def update_awards_theme(
    request: Request,
    event_id: int,
    preset: str = Form("classic"),
    accent_color: str = Form(""),
    background_color: str = Form(""),
    text_color: str = Form(""),
    show_logo: str | None = Form(None),
    animations_enabled: str | None = Form(None),
    layout: str = Form("classic"),
    background_opacity: str = Form("35"),
    background_dim: str = Form("55"),
    opening_title: str = Form("Premiação"),
    opening_text: str = Form(""),
    closing_title: str = Form("Obrigado!"),
    closing_text: str = Form(""),
):
    try:
        with transaction(request.app.state.db_path) as db:
            require_event(db, event_id)
            award_service.update_settings(
                db,
                event_id,
                preset=preset,
                accent_color=accent_color,
                background_color=background_color,
                text_color=text_color,
                show_logo=show_logo is not None,
                animations_enabled=animations_enabled is not None,
                layout=layout,
                background_opacity=background_opacity,
                background_dim=background_dim,
                opening_title=opening_title,
                opening_text=opening_text,
                closing_title=closing_title,
                closing_text=closing_text,
            )
    except ValueError as error:
        return redirect_with(f"/premiacao/{event_id}", error=str(error))
    return redirect_with(
        f"/premiacao/{event_id}", ok="Tema da premiação atualizado."
    )


@router.post("/{event_id}/tema/assets")
async def update_awards_assets(
    request: Request,
    event_id: int,
    banner: UploadFile | None = File(None),
    background: UploadFile | None = File(None),
    custom_font: UploadFile | None = File(None),
    remove_banner: str | None = Form(None),
    remove_background: str | None = Form(None),
    remove_font: str | None = Form(None),
):
    media_root = request.app.state.awards_media_dir
    uploads = {}
    for kind, upload in (
        ("banner", banner),
        ("background", background),
        ("font", custom_font),
    ):
        if upload is not None and upload.filename:
            uploads[kind] = (upload.filename, await upload.read())

    new_files: dict[str, str] = {}
    try:
        for kind, (filename, content) in uploads.items():
            new_files[kind] = award_assets.save_asset(
                media_root, event_id, kind, filename, content
            )
        with transaction(request.app.state.db_path) as db:
            require_event(db, event_id)
            old = award_service.get_settings(db, event_id)
            final = {}
            for kind, remove in (
                ("banner", remove_banner),
                ("background", remove_background),
                ("font", remove_font),
            ):
                if kind in new_files:
                    final[kind] = new_files[kind]
                elif remove:
                    final[kind] = None
                else:
                    final[kind] = old.get(f"{kind}_filename")
            award_service.update_assets(
                db,
                event_id,
                banner_filename=final["banner"],
                background_filename=final["background"],
                font_filename=final["font"],
                font_format=award_assets.font_format(final["font"]),
            )
    except ValueError as error:
        for kind, filename in new_files.items():
            award_assets.delete_asset(media_root, event_id, filename)
        return redirect_with(f"/premiacao/{event_id}", error=str(error))
    except Exception:
        for kind, filename in new_files.items():
            award_assets.delete_asset(media_root, event_id, filename)
        raise

    for kind in ("banner", "background", "font"):
        old_filename = old.get(f"{kind}_filename")
        if old_filename and old_filename != final[kind]:
            award_assets.delete_asset(media_root, event_id, old_filename)
    return redirect_with(
        f"/premiacao/{event_id}", ok="Arquivos da premiação atualizados."
    )


@router.get("/{event_id}/asset/{kind}")
def award_asset(
    request: Request,
    event_id: int,
    kind: str,
    db: sqlite3.Connection = Depends(get_db),
):
    if kind not in ("banner", "background", "font"):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    require_event(db, event_id)
    settings = award_service.get_settings(db, event_id)
    filename = settings.get(f"{kind}_filename")
    path = award_assets.asset_path(
        request.app.state.awards_media_dir, event_id, filename
    )
    if path is None:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    return FileResponse(
        path=path,
        media_type=award_assets.media_type(filename),
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.post("/{event_id}/slides/{category_id}/{group_sex}")
def update_award_slide_text(
    request: Request,
    event_id: int,
    category_id: int,
    group_sex: str,
    title: str = Form(""),
    call_text: str = Form(""),
):
    try:
        with transaction(request.app.state.db_path) as db:
            require_event(db, event_id)
            award_service.update_slide_text(
                db,
                event_id,
                category_id,
                group_sex,
                title=title,
                call_text=call_text,
            )
    except ValueError as error:
        return redirect_with(f"/premiacao/{event_id}", error=str(error))
    return redirect_with(
        f"/premiacao/{event_id}", ok="Texto do slide atualizado."
    )


@router.get("/{event_id}/pdf")
def export_awards_pdf(
    request: Request, event_id: int, db: sqlite3.Connection = Depends(get_db)
):
    event = require_event(db, event_id)
    settings = award_service.get_settings(db, event_id)
    theme = award_service.resolve_theme(settings)
    path = pdf_exports.export_awards(
        db,
        event,
        theme=theme,
        settings=settings,
        media_dir=request.app.state.awards_media_dir,
        exports_dir=request.app.state.exports_dir,
    )
    if not path.exists():
        raise HTTPException(status_code=500, detail="Não foi possível gerar o PDF.")
    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=path.name,
    )
