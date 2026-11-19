from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.database import connect


class BackupError(Exception):
    pass


@dataclass(frozen=True)
class ManualBackupResult:
    target: Path
    database: Path
    pdf_count: int
    asset_count: int
    created_at: str


def _copy_files(source: Path | None, target: Path) -> int:
    if source is None or not source.exists():
        return 0
    count = 0
    for item in sorted(source.rglob("*")):
        if not item.is_file() or item.name.endswith(".tmp.pdf"):
            continue
        destination = target / item.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, destination)
        count += 1
    return count


def _validate_destination(
    destination: Path, exports_dir: Path | None, media_dir: Path | None
) -> Path:
    target = destination.expanduser().resolve()
    if not target.exists():
        raise BackupError("A pasta escolhida não existe. Conecte o pendrive e confira o caminho.")
    if not target.is_dir():
        raise BackupError("O caminho escolhido não é uma pasta.")
    for source in (exports_dir, media_dir):
        if source is None:
            continue
        resolved_source = source.expanduser().resolve()
        if target == resolved_source or resolved_source in target.parents:
            raise BackupError(
                "Escolha uma pasta fora dos diretórios da aplicação para evitar cópias recursivas."
            )
    return target


def create_manual_backup(
    db_path: str | Path,
    destination: str | Path,
    *,
    exports_dir: str | Path | None,
    awards_media_dir: str | Path | None = None,
    environment_name: str = "real",
) -> ManualBackupResult:
    exports = Path(exports_dir) if exports_dir is not None else None
    media = Path(awards_media_dir) if awards_media_dir is not None else None
    root = _validate_destination(Path(destination), exports, media)

    now = datetime.now()
    stamp = now.strftime("%Y%m%d-%H%M%S-%f")
    label = "teste" if environment_name == "teste" else "real"
    target = root / f"triscore-backup-{label}-{stamp}"
    database_target = target / Path(db_path).name

    try:
        target.mkdir(parents=False, exist_ok=False)
        connection = connect(db_path)
        try:
            snapshot = sqlite3.connect(database_target)
            try:
                connection.backup(snapshot)
            finally:
                snapshot.close()
        finally:
            connection.close()

        pdf_count = _copy_files(exports, target / "exports")
        asset_count = _copy_files(media, target / "premiacao")

        manifest = {
            "created_at": now.isoformat(timespec="seconds"),
            "environment": label,
            "database": str(database_target.name),
            "source_db": str(Path(db_path).name),
            "pdf_count": pdf_count,
            "award_asset_count": asset_count,
        }
        (target / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except BackupError:
        shutil.rmtree(target, ignore_errors=True)
        raise
    except Exception as error:
        shutil.rmtree(target, ignore_errors=True)
        raise BackupError(f"Falha ao criar o backup: {error}") from error

    return ManualBackupResult(
        target=target,
        database=database_target,
        pdf_count=pdf_count,
        asset_count=asset_count,
        created_at=manifest["created_at"],
    )


def list_automatic_backups(backup_dir: str | Path, limit: int = 8) -> list[dict]:
    root = Path(backup_dir)
    if not root.exists():
        return []
    items = []
    for path in root.glob("*.db"):
        if not path.is_file():
            continue
        stat = path.stat()
        items.append(
            {
                "name": path.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime),
            }
        )
    items.sort(key=lambda item: item["modified"], reverse=True)
    return items[:limit]
