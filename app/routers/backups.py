from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from app.services import manual_backup
from app.templating import templates
from app.utils import redirect_with

router = APIRouter(prefix="/backup", tags=["backup"])


@router.get("", response_class=HTMLResponse)
def backup_page(request: Request):
    environment = request.app.state.environment
    return templates.TemplateResponse(
        request=request,
        name="backup/index.html",
        context={
            "event": None,
            "active": "backup",
            "environment": environment,
            "automatic_backups": manual_backup.list_automatic_backups(
                request.app.state.backup_dir
            ),
        },
    )


@router.post("")
def create_backup(request: Request, destination: str = Form("")):
    destination = (destination or "").strip()[:500]
    if not destination:
        return redirect_with(
            "/backup", error="Informe a pasta de destino do backup."
        )
    try:
        result = manual_backup.create_manual_backup(
            request.app.state.db_path,
            destination,
            exports_dir=request.app.state.exports_dir,
            awards_media_dir=request.app.state.awards_media_dir,
            environment_name=request.app.state.environment.name,
        )
    except manual_backup.BackupError as error:
        return redirect_with("/backup", error=str(error))
    return redirect_with(
        "/backup",
        ok=(
            f"Backup criado em {result.target} — {result.pdf_count} PDF(s) e "
            f"{result.asset_count} arquivo(s) de premiação copiados."
        ),
    )
