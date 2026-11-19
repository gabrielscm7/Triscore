from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.database import connect
from app.main import create_app


@pytest.fixture
def app(tmp_path):
    application = create_app(tmp_path / "triscore-test.db")
    application.state.exports_dir = tmp_path / "exports"
    return application


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db(app, client):
    connection = connect(app.state.db_path)
    try:
        yield connection
    finally:
        connection.close()


def create_event(client: TestClient, name: str = "Prova Teste") -> int:
    response = client.post(
        "/eventos",
        data={"name": name, "event_date": "2026-08-15", "location": "Cidade Teste"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return int(response.headers["location"].split("/")[2])


def create_category(
    client: TestClient,
    event_id: int,
    name: str,
    min_age: int | None = None,
    max_age: int | None = None,
    classification_mode: str = "separate",
) -> None:
    response = client.post(
        f"/eventos/{event_id}/categorias",
        data={
            "name": name,
            "min_age": "" if min_age is None else str(min_age),
            "max_age": "" if max_age is None else str(max_age),
            "classification_mode": classification_mode,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def create_team(client: TestClient, event_id: int, name: str) -> int:
    client.post(
        f"/eventos/{event_id}/equipes",
        data={"name": name},
        follow_redirects=False,
    )
    connection = connect(client.app.state.db_path)
    try:
        row = connection.execute(
            "SELECT id FROM teams WHERE event_id = ? AND name = ? COLLATE NOCASE",
            (event_id, name),
        ).fetchone()
    finally:
        connection.close()
    assert row is not None
    return int(row["id"])


def create_athlete(
    client: TestClient,
    event_id: int,
    *,
    name: str,
    age: int,
    category_id: int,
    sex: str,
    bib: int | None = None,
    team: str = "Equipe",
    team_id: int | None = None,
) -> None:
    if team_id is None and team:
        team_id = create_team(client, event_id, team)
    response = client.post(
        f"/eventos/{event_id}/atletas/novo",
        data={
            "name": name,
            "age": str(age),
            "category_id": str(category_id),
            "team_id": "" if team_id is None else str(team_id),
            "sex": sex,
            "bib": "" if bib is None else str(bib),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
