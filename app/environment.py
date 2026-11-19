from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from app.database import resolve_db_path
from app.paths import (
    DATA_DIR,
    DEFAULT_DB_PATH,
    TEST_DATA_DIR,
    TEST_DB_PATH,
)

REAL_PORT = 8000
TEST_PORT = 8100
REAL_PORT_END = 8100
TEST_PORT_END = 8200

TEST_HINTS = ("teste", "test", "homolog")


@dataclass(frozen=True)
class Environment:
    name: str
    is_test: bool
    db_path: Path
    data_dir: Path
    backup_dir: Path
    exports_dir: Path
    awards_media_dir: Path
    logs_dir: Path
    default_port: int
    port_range: tuple[int, int]

    @property
    def label(self) -> str:
        return "Teste" if self.is_test else "Real"

    @property
    def banner_title(self) -> str:
        return "MODO TESTE" if self.is_test else "MODO REAL"

    @property
    def backup_prefix(self) -> str:
        return "triscore-teste" if self.is_test else "triscore"


def _looks_like_test_db(path: Path) -> bool:
    names = (path.stem, path.parent.name)
    return any(
        hint in name.casefold()
        for hint in TEST_HINTS
        for name in names
        if name
    )


def _test_root(path: Path) -> Path:
    resolved_test_dir = TEST_DATA_DIR.resolve()
    resolved = path.resolve()
    if resolved == TEST_DB_PATH.resolve() or resolved_test_dir in resolved.parents:
        return TEST_DATA_DIR
    if path.parent == DATA_DIR or path.parent.resolve() == DATA_DIR.resolve():
        return TEST_DATA_DIR
    return path.parent


def create_environment(db_path: str | Path | None = None) -> Environment:
    path = resolve_db_path(db_path)
    explicit = os.environ.get("TRISCORE_ENV", "").strip().casefold()

    if explicit in ("teste", "test"):
        is_test = True
    else:
        is_test = _looks_like_test_db(path)

    if is_test:
        root = _test_root(path)
        return Environment(
            name="teste",
            is_test=True,
            db_path=path,
            data_dir=root,
            backup_dir=root / "backups",
            exports_dir=root / "exports",
            awards_media_dir=root / "uploads" / "premiacao" / path.stem,
            logs_dir=root / "logs",
            default_port=TEST_PORT,
            port_range=(TEST_PORT, TEST_PORT_END),
        )

    if path == DEFAULT_DB_PATH.resolve():
        root = DATA_DIR
        return Environment(
            name="real",
            is_test=False,
            db_path=path,
            data_dir=root,
            backup_dir=root / "backups",
            exports_dir=root / "exports",
            awards_media_dir=root / "uploads" / "premiacao" / path.stem,
            logs_dir=root / "logs",
            default_port=REAL_PORT,
            port_range=(REAL_PORT, REAL_PORT_END),
        )

    return Environment(
        name="real",
        is_test=False,
        db_path=path,
        data_dir=path.parent,
        backup_dir=path.parent / "backups",
        exports_dir=path.parent / "exports",
        awards_media_dir=path.parent / "uploads" / "premiacao" / path.stem,
        logs_dir=path.parent / "logs",
        default_port=REAL_PORT,
        port_range=(REAL_PORT, REAL_PORT_END),
    )
