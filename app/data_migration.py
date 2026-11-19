from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class MigrationResult:
    copied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _copy_database(source: Path, target: Path, result: MigrationResult) -> None:
    if not source.is_file():
        return
    if target.exists():
        result.skipped.append(str(target))
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(source)
    destination = sqlite3.connect(target)
    try:
        source_connection.backup(destination)
    finally:
        destination.close()
        source_connection.close()
    result.copied.append(f"{source} -> {target}")


def _copy_tree(source: Path, target: Path, result: MigrationResult) -> None:
    if not source.is_dir():
        return
    for item in sorted(source.rglob("*")):
        if not item.is_file():
            continue
        destination = target / item.relative_to(source)
        if destination.exists():
            result.skipped.append(str(destination))
            continue
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)
        except OSError as error:
            result.errors.append(f"{item}: {error}")
            continue
        result.copied.append(f"{item} -> {destination}")


def migrate_legacy_data(
    app_dir: str | Path,
    data_dir: str | Path,
    *,
    write_manifest: bool = True,
) -> MigrationResult:
    """Copia o layout antigo para ./dados sem remover os arquivos originais."""

    source_root = Path(app_dir).expanduser().resolve()
    target_root = Path(data_dir).expanduser().resolve()
    result = MigrationResult()

    if source_root == target_root:
        return result

    legacy_data = source_root / "data"
    legacy_backups = source_root / "backups"
    legacy_exports = source_root / "exports"

    _copy_database(legacy_data / "triscore.db", target_root / "banco" / "triscore.db", result)
    _copy_tree(legacy_backups, target_root / "backups", result)
    _copy_tree(legacy_exports, target_root / "exports", result)
    _copy_tree(legacy_data / "premiacao", target_root / "uploads" / "premiacao", result)

    legacy_test = legacy_data / "teste"
    _copy_database(
        legacy_test / "triscore-teste.db",
        target_root / "teste" / "banco" / "triscore-teste.db",
        result,
    )
    _copy_tree(legacy_test / "backups", target_root / "teste" / "backups", result)
    _copy_tree(legacy_test / "exports", target_root / "teste" / "exports", result)
    _copy_tree(
        legacy_test / "premiacao",
        target_root / "teste" / "uploads" / "premiacao",
        result,
    )

    for directory in (
        "banco",
        "backups",
        "exports",
        "uploads",
        "logs",
        "teste/banco",
        "teste/backups",
        "teste/exports",
        "teste/uploads",
        "teste/logs",
    ):
        (target_root / directory).mkdir(parents=True, exist_ok=True)

    if write_manifest and (result.copied or result.errors):
        manifest = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source": str(source_root),
            "target": str(target_root),
            "copied_count": len(result.copied),
            "skipped_count": len(result.skipped),
            "error_count": len(result.errors),
            "copied": result.copied,
            "skipped": result.skipped,
            "errors": result.errors,
        }
        target_root.mkdir(parents=True, exist_ok=True)
        (target_root / ".migracao-legado.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return result
