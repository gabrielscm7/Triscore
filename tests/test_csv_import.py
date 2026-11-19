from __future__ import annotations

import pytest

from app.database import transaction
from app.services import athletes as athlete_service
from app.services import csv_import
from tests.conftest import create_category, create_event, create_team


def _upload(client, event_id, content: bytes, filename: str = "atletas.csv"):
    response = client.post(
        f"/eventos/{event_id}/atletas/importar/previa",
        files={"file": (filename, content, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    location = response.headers["location"]
    assert "error=" not in location
    batch_id = location.split("/importar/")[1].split("?")[0]
    return batch_id


def test_csv_preview_report_and_confirm(client, db):
    event_id = create_event(client)
    create_category(client, event_id, "Adulto", 30, 39)
    content = (
        "nome;idade;categoria;equipe;sexo;peito\n"
        "Ana;32;Adulto;Equipe A;F;10\n"
        "Bia;28;Adulto;Equipe B;F;11\n"
        "Caio;40;Master;Equipe C;M;12\n"
        "Duda;15;Adulto;Equipe D;M;13\n"
        "Eva;abc;Adulto;;F;14\n"
        "Ivo;30;Adulto;;X;15\n"
        "Jo;31;Adulto;;M;10\n"
        "Nina;30;Adulto;;F;\n"
    ).encode("utf-8")

    batch_id = _upload(client, event_id, content)
    assert db.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 0
    assert db.execute(
        "SELECT COUNT(*) FROM categories WHERE name = 'Master'"
    ).fetchone()[0] == 0
    preview = client.get(f"/eventos/{event_id}/atletas/importar/{batch_id}")
    assert preview.status_code == 200
    assert "Caio" in preview.text
    assert "Categoria “Master” não existe" in preview.text
    assert "Equipe “Equipe B” não existe" in preview.text
    assert "Serão criados" in preview.text
    assert "duplicado dentro do arquivo" in preview.text
    assert "Idade 15 abaixo" in preview.text
    assert "Sexo inválido" in preview.text
    assert db.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 0
    assert db.execute(
        "SELECT COUNT(*) FROM categories WHERE name = 'Master'"
    ).fetchone()[0] == 0

    report = client.get(
        f"/eventos/{event_id}/atletas/importar/{batch_id}/erros.csv"
    )
    assert report.status_code == 200
    assert "relatorio_importacao.csv" in report.headers["content-disposition"]
    report_text = report.content.decode("utf-8-sig")
    assert "Eva" in report_text and "Idade inválida" in report_text
    assert "equipe" in report_text.splitlines()[0]

    confirmed = client.post(
        f"/eventos/{event_id}/atletas/importar/{batch_id}/confirmar",
        follow_redirects=True,
    )
    assert confirmed.status_code == 200
    assert "4 atleta(s) importado(s)" in confirmed.text
    assert "1 categoria(s) criada(s)" in confirmed.text
    assert "3 equipe(s) criada(s)" in confirmed.text

    athletes = db.execute(
        "SELECT a.name, a.bib, c.name AS category, t.name AS team FROM athletes a "
        "JOIN race_groups rg ON rg.id = a.race_group_id "
        "JOIN categories c ON c.id = rg.category_id "
        "LEFT JOIN teams t ON t.id = a.team_id "
        "WHERE a.event_id = ? ORDER BY a.bib",
        (event_id,),
    ).fetchall()
    assert [row["name"] for row in athletes] == ["Bia", "Caio", "Duda", "Nina"]
    assert [row["bib"] for row in athletes] == [11, 12, 13, 14]
    assert athletes[1]["category"] == "Master"
    assert [row["team"] for row in athletes] == [
        "Equipe B",
        "Equipe C",
        "Equipe D",
        None,
    ]
    master = db.execute(
        "SELECT min_age, max_age FROM categories WHERE event_id = ? AND name = 'Master'",
        (event_id,),
    ).fetchone()
    assert master["min_age"] is None and master["max_age"] is None

    missing = db.execute(
        "SELECT COUNT(*) AS total FROM import_batches WHERE id = ?", (batch_id,)
    ).fetchone()["total"]
    assert missing == 0


def test_csv_accepts_comma_encoding_and_missing_optional_columns(client, db):
    event_id = create_event(client)
    create_category(client, event_id, "Geral", None, None)
    content = (
        "Nome,Idade,Categoria,Sexo\n"
        "João da Silva,36,Geral,Masculino\n"
        "Márcia Ávila,42,Geral,Feminino\n"
    ).encode("cp1252")

    batch_id = _upload(client, event_id, content, "lista.csv")
    preview = client.get(f"/eventos/{event_id}/atletas/importar/{batch_id}")
    assert preview.status_code == 200
    assert "João da Silva" in preview.text
    response = client.post(
        f"/eventos/{event_id}/atletas/importar/{batch_id}/confirmar",
        follow_redirects=True,
    )
    assert "2 atleta(s) importado(s)" in response.text
    rows = db.execute(
        "SELECT name, bib FROM athletes WHERE event_id = ? ORDER BY bib", (event_id,)
    ).fetchall()
    assert [(row["name"], row["bib"]) for row in rows] == [
        ("João da Silva", 1),
        ("Márcia Ávila", 2),
    ]


def test_csv_missing_headers_returns_friendly_error(client):
    event_id = create_event(client)
    response = client.post(
        f"/eventos/{event_id}/atletas/importar/previa",
        files={"file": ("atletas.csv", b"nome;equipe\nAna;Time\n", "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=" in response.headers["location"]
    assert "obrigat" in response.headers["location"].lower()


def test_csv_reuses_team_and_category_case_insensitively(client, db):
    event_id = create_event(client)
    create_category(client, event_id, "Adulto", 30, 39)
    team_id = create_team(client, event_id, "Cardume")
    content = (
        "nome;idade;categoria;equipe;sexo;peito\n"
        "Ana;32;adulto;  cArDuMe  ;F;10\n"
    ).encode("utf-8")

    batch_id = _upload(client, event_id, content)
    preview = client.get(f"/eventos/{event_id}/atletas/importar/{batch_id}")
    assert preview.status_code == 200
    assert "Serão criados" not in preview.text

    response = client.post(
        f"/eventos/{event_id}/atletas/importar/{batch_id}/confirmar",
        follow_redirects=True,
    )
    assert "1 atleta(s) importado(s)" in response.text
    assert "categoria(s) criada(s)" not in response.text
    assert "equipe(s) criada(s)" not in response.text

    assert db.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 1
    athlete = db.execute(
        "SELECT team_id FROM athletes WHERE event_id = ?", (event_id,)
    ).fetchone()
    assert athlete["team_id"] == team_id


def test_csv_empty_team_and_invalid_entities_are_reported_without_creation(client, db):
    event_id = create_event(client)
    create_category(client, event_id, "Adulto", 30, 39)
    long_team = "E" * 121
    content = (
        "nome;idade;categoria;equipe;sexo;peito\n"
        "Sem Equipe;32;Adulto;;F;10\n"
        f"Equipe Longa;33;Adulto;{long_team};M;11\n"
        "Categoria Ausente;34;;Equipe Nova;F;12\n"
    ).encode("utf-8")

    batch_id = _upload(client, event_id, content)
    preview = client.get(f"/eventos/{event_id}/atletas/importar/{batch_id}")
    assert preview.status_code == 200
    assert "no máximo 120 caracteres" in preview.text
    assert "Categoria obrigatória" in preview.text
    assert db.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 0

    report = client.get(f"/eventos/{event_id}/atletas/importar/{batch_id}/erros.csv")
    report_text = report.content.decode("utf-8-sig")
    assert "Equipe Longa" in report_text
    assert "no máximo 120 caracteres" in report_text

    response = client.post(
        f"/eventos/{event_id}/atletas/importar/{batch_id}/confirmar",
        follow_redirects=True,
    )
    assert "1 atleta(s) importado(s)" in response.text
    assert db.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 0
    athlete = db.execute(
        "SELECT team_id FROM athletes WHERE event_id = ?", (event_id,)
    ).fetchone()
    assert athlete is not None and athlete["team_id"] is None


def test_csv_confirmation_is_transactional_and_returns_creation_counts(
    client, db, app, monkeypatch
):
    event_id = create_event(client)
    content = (
        "nome;idade;categoria;equipe;sexo;peito\n"
        "Ana;32;Nova Categoria;Nova Equipe;F;10\n"
    ).encode("utf-8")
    batch_id = _upload(client, event_id, content)

    original_create_athlete = athlete_service.create_athlete

    def fail_create_athlete(*args, **kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(athlete_service, "create_athlete", fail_create_athlete)
    with pytest.raises(RuntimeError, match="falha simulada"):
        with transaction(app.state.db_path) as connection:
            csv_import.confirm_batch(connection, event_id, batch_id)

    assert db.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM athletes").fetchone()[0] == 0
    assert db.execute(
        "SELECT COUNT(*) FROM import_batches WHERE id = ?", (batch_id,)
    ).fetchone()[0] == 1

    monkeypatch.setattr(athlete_service, "create_athlete", original_create_athlete)
    with transaction(app.state.db_path) as connection:
        summary = csv_import.confirm_batch(connection, event_id, batch_id)
    assert summary["imported"] == 1
    assert summary["skipped"] == []
    assert summary["categories_created"] == 1
    assert summary["teams_created"] == 1
    assert db.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM athletes").fetchone()[0] == 1
    assert db.execute(
        "SELECT COUNT(*) FROM import_batches WHERE id = ?", (batch_id,)
    ).fetchone()[0] == 0
