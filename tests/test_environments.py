from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_test_environment_has_isolated_folders_and_visible_banner(tmp_path):
    root = tmp_path / "teste"
    app = create_app(root / "triscore.db")
    assert app.state.environment.is_test
    assert app.state.backup_dir == root / "backups"
    assert app.state.exports_dir == root / "exports"
    with TestClient(app) as client:
        response = client.get("/eventos")
    assert response.status_code == 200
    assert "MODO TESTE" in response.text


def test_real_environment_has_no_test_banner(tmp_path):
    root = tmp_path / "producao"
    app = create_app(root / "triscore.db")
    assert not app.state.environment.is_test
    assert app.state.backup_dir == root / "backups"
    assert app.state.exports_dir == root / "exports"
    with TestClient(app) as client:
        response = client.get("/eventos")
    assert response.status_code == 200
    assert "MODO TESTE" not in response.text
