from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.data_migration import migrate_legacy_data
from app.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_health_and_shutdown_without_handler(tmp_path):
    app = create_app(tmp_path / "teste" / "sistema.db")
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["environment"] == "teste"

        response = client.post("/encerrar")
        assert response.status_code == 409


def test_shutdown_handler_is_called(tmp_path):
    app = create_app(tmp_path / "teste" / "sistema.db")
    called = []
    app.state.shutdown_handler = lambda: called.append(True)
    with TestClient(app) as client:
        response = client.post("/encerrar")
    assert response.status_code == 200
    assert called == [True]


def test_external_data_dir_layout(tmp_path):
    env = os.environ.copy()
    env["TRISCORE_DATA_DIR"] = str(tmp_path / "dados")
    code = (
        "from app.paths import DEFAULT_DB_PATH, DEFAULT_BACKUP_DIR, "
        "DEFAULT_EXPORTS_DIR, DEFAULT_LOGS_DIR; "
        "print(DEFAULT_DB_PATH); print(DEFAULT_BACKUP_DIR); "
        "print(DEFAULT_EXPORTS_DIR); print(DEFAULT_LOGS_DIR)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    paths = [Path(line) for line in result.stdout.splitlines()]
    assert paths[0] == tmp_path / "dados" / "banco" / "triscore.db"
    assert paths[1] == tmp_path / "dados" / "backups"
    assert paths[2] == tmp_path / "dados" / "exports"
    assert paths[3] == tmp_path / "dados" / "logs"


def test_legacy_data_migration_copies_without_removing(tmp_path):
    app_dir = tmp_path / "app"
    data_dir = tmp_path / "dados"
    (app_dir / "data").mkdir(parents=True)
    source = sqlite3.connect(app_dir / "data" / "triscore.db")
    source.execute("CREATE TABLE exemplo (id INTEGER)")
    source.execute("INSERT INTO exemplo (id) VALUES (7)")
    source.commit()
    source.close()
    (app_dir / "backups").mkdir()
    (app_dir / "backups" / "antigo.db").write_bytes(b"backup")
    (app_dir / "exports").mkdir()
    (app_dir / "exports" / "relatorio.pdf").write_bytes(b"%PDF")

    result = migrate_legacy_data(app_dir, data_dir)

    assert result.ok
    assert (app_dir / "data" / "triscore.db").exists()
    target = sqlite3.connect(data_dir / "banco" / "triscore.db")
    try:
        assert target.execute("SELECT id FROM exemplo").fetchone()[0] == 7
    finally:
        target.close()
    assert (data_dir / "backups" / "antigo.db").read_bytes() == b"backup"
    assert (data_dir / "exports" / "relatorio.pdf").read_bytes() == b"%PDF"
    manifest = json.loads((data_dir / ".migracao-legado.json").read_text())
    assert manifest["copied_count"] >= 3
