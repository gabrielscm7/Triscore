from __future__ import annotations

from tests.conftest import create_athlete, create_category, create_event, create_team


def test_team_crud_uniqueness_and_scope(client, db):
    event_id = create_event(client, "Prova Um")
    other_event_id = create_event(client, "Prova Dois")

    page = client.get(f"/eventos/{event_id}/equipes")
    assert page.status_code == 200
    assert 'action="/eventos/1/equipes"' in page.text

    created = client.post(
        f"/eventos/{event_id}/equipes",
        data={"name": "Cardume"},
        follow_redirects=True,
    )
    assert "Equipe criada" in created.text
    duplicate = client.post(
        f"/eventos/{event_id}/equipes",
        data={"name": "cardume"},
        follow_redirects=True,
    )
    assert "Já existe uma equipe" in duplicate.text
    other = client.post(
        f"/eventos/{other_event_id}/equipes",
        data={"name": "CARDUME"},
        follow_redirects=True,
    )
    assert "Equipe criada" in other.text
    assert db.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 2

    too_long = client.post(
        f"/eventos/{event_id}/equipes",
        data={"name": "x" * 121},
        follow_redirects=True,
    )
    assert "no máximo 120" in too_long.text
    assert db.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 2

    team_id = db.execute(
        "SELECT id FROM teams WHERE event_id = ?", (event_id,)
    ).fetchone()["id"]
    renamed = client.post(
        f"/eventos/{event_id}/equipes/{team_id}/editar",
        data={"name": "Cardume Azul"},
        follow_redirects=True,
    )
    assert "Equipe atualizada" in renamed.text
    assert db.execute(
        "SELECT name FROM teams WHERE id = ?", (team_id,)
    ).fetchone()["name"] == "Cardume Azul"

    deleted = client.post(
        f"/eventos/{event_id}/equipes/{team_id}/excluir", follow_redirects=True
    )
    assert "Equipe excluída" in deleted.text
    assert db.execute("SELECT COUNT(*) FROM teams WHERE id = ?", (team_id,)).fetchone()[0] == 0
    assert db.execute(
        "SELECT COUNT(*) FROM teams WHERE event_id = ?", (other_event_id,)
    ).fetchone()[0] == 1


def test_team_rename_updates_athletes_and_delete_in_use_is_blocked(client, db):
    event_id = create_event(client)
    create_category(client, event_id, "Adulto", 30, 39)
    team_id = create_team(client, event_id, "Original")
    create_athlete(
        client,
        event_id,
        name="Ana",
        age=34,
        category_id=1,
        sex="F",
        bib=1,
        team_id=team_id,
    )

    renamed = client.post(
        f"/eventos/{event_id}/equipes/{team_id}/editar",
        data={"name": "Renomeada"},
        follow_redirects=True,
    )
    assert "Renomeada" in renamed.text
    athlete = db.execute(
        "SELECT t.name FROM athletes a JOIN teams t ON t.id = a.team_id WHERE a.name = 'Ana'"
    ).fetchone()
    assert athlete["name"] == "Renomeada"

    blocked = client.post(
        f"/eventos/{event_id}/equipes/{team_id}/excluir", follow_redirects=True
    )
    assert "possui atletas" in blocked.text
    assert db.execute("SELECT COUNT(*) FROM teams WHERE id = ?", (team_id,)).fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM athletes").fetchone()[0] == 1

    unused_id = create_team(client, event_id, "Sem atletas")
    removed = client.post(
        f"/eventos/{event_id}/equipes/{unused_id}/excluir", follow_redirects=True
    )
    assert "Equipe excluída" in removed.text
    assert db.execute("SELECT COUNT(*) FROM teams WHERE id = ?", (unused_id,)).fetchone()[0] == 0


def test_categories_page_and_configuration_summary(client, db):
    event_id = create_event(client)
    page = client.get(f"/eventos/{event_id}/categorias")
    assert page.status_code == 200
    assert "Adicionar categoria" in page.text
    assert 'action="/eventos/1/categorias"' in page.text

    create_category(client, event_id, "Adulto", 30, 39)
    page = client.get(f"/eventos/{event_id}/categorias")
    assert "Adulto" in page.text
    assert "0 M" in page.text
    assert 'action="/eventos/1/categorias/1/editar"' in page.text

    config = client.get(f"/eventos/{event_id}/configuracao")
    assert config.status_code == 200
    assert "Gerenciar categorias" in config.text
    assert 'action="/eventos/1/categorias"' not in config.text


def test_athlete_optional_team_team_filter_and_cross_event_validation(client, db):
    event_id = create_event(client, "Prova Um")
    other_event_id = create_event(client, "Prova Dois")
    create_category(client, event_id, "Adulto", 30, 39)
    create_category(client, other_event_id, "Adulto", 30, 39)
    team_a = create_team(client, event_id, "Equipe A")
    team_b = create_team(client, event_id, "Equipe B")
    other_team = create_team(client, other_event_id, "Equipe Externa")

    create_athlete(
        client,
        event_id,
        name="Ana",
        age=34,
        category_id=1,
        sex="F",
        bib=1,
        team_id=team_a,
    )
    create_athlete(
        client,
        event_id,
        name="Bia",
        age=35,
        category_id=1,
        sex="F",
        bib=2,
        team="",
    )
    create_athlete(
        client,
        event_id,
        name="Carla",
        age=36,
        category_id=1,
        sex="F",
        bib=3,
        team_id=team_b,
    )
    assert db.execute(
        "SELECT COUNT(*) FROM athletes WHERE event_id = ? AND team_id IS NULL",
        (event_id,),
    ).fetchone()[0] == 1

    filtered = client.get(f"/eventos/{event_id}/atletas?team_id={team_a}")
    assert "Ana" in filtered.text
    assert ">Bia<" not in filtered.text
    assert ">Carla<" not in filtered.text

    searched = client.get(f"/eventos/{event_id}/atletas?q=Equipe B")
    assert "Carla" in searched.text
    assert ">Ana<" not in searched.text

    invalid = client.post(
        f"/eventos/{event_id}/atletas/novo",
        data={
            "name": "Diego",
            "age": "31",
            "category_id": "1",
            "team_id": str(other_team),
            "sex": "M",
            "bib": "4",
        },
    )
    assert invalid.status_code == 422
    assert "Equipe inválida" in invalid.text
    assert db.execute("SELECT COUNT(*) FROM athletes WHERE name = 'Diego'").fetchone()[0] == 0
