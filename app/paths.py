from __future__ import annotations

import os
import sys
from pathlib import Path

IS_FROZEN = bool(getattr(sys, "frozen", False))

if IS_FROZEN:
    APP_DIR = Path(sys.executable).resolve().parent
    RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", APP_DIR)).resolve()
else:
    APP_DIR = Path(__file__).resolve().parent.parent
    RESOURCE_ROOT = APP_DIR

RESOURCE_APP_DIR = RESOURCE_ROOT / "app"


def _resolve_data_dir() -> Path:
    configured = os.environ.get("TRISCORE_DATA_DIR")
    if configured:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = APP_DIR / path
        return path.resolve()
    return (APP_DIR / "dados").resolve()


DATA_DIR = _resolve_data_dir()
DEFAULT_DB_PATH = DATA_DIR / "banco" / "triscore.db"
DEFAULT_BACKUP_DIR = DATA_DIR / "backups"
DEFAULT_EXPORTS_DIR = DATA_DIR / "exports"
DEFAULT_UPLOADS_DIR = DATA_DIR / "uploads"
DEFAULT_LOGS_DIR = DATA_DIR / "logs"

TEST_DATA_DIR = DATA_DIR / "teste"
TEST_DB_PATH = TEST_DATA_DIR / "banco" / "triscore-teste.db"

TEMPLATES_DIR = RESOURCE_APP_DIR / "templates"
STATIC_DIR = RESOURCE_APP_DIR / "static"
SCHEMA_PATH = RESOURCE_APP_DIR / "schema.sql"
FONT_DIR = STATIC_DIR / "fonts"
LOGO_PATH = STATIC_DIR / "img" / "logo.png"

# Compatibilidade com módulos que ainda importam PROJECT_ROOT.
PROJECT_ROOT = APP_DIR
