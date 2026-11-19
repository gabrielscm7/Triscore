from __future__ import annotations

from tests.conftest import create_athlete, create_category, create_event, create_team


def test_event_and_category_crud(client, app):
    response = client.get("/eventos")
    assert response.status_code == 200
    assert "Nenhuma prova cadastrada" in response.text

    response = client.post(
        "/eventos",
        data={"name": "", "event_date": "", "location": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=" in response.headers["location"]

    event_id = create_event(client, "Triatlo Central")
    create_category(client, event_id, "Adulto", 30, 39)
    create_category(client, event_id, "Master", 40, 49)

    response = client.get(f"/eventos/{event_id}/categorias")
    assert response.status_code == 200
    assert "Adulto" in response.text
    assert "Master" in response.text

    duplicate = client.post(
        f"/eventos/{event_id}/categorias",
        data={"name": "Adulto", "min_age": "30", "max_age": "39"},
        follow_redirects=False,
    )
    assert duplicate.status_code == 303
    assert "error=" in duplicate.headers["location"]

    invalid_range = client.post(
        f"/eventos/{event_id}/categorias",
        data={"name": "Invertida", "min_age": "50", "max_age": "20"},
        follow_redirects=False,
    )
    assert "error=" in invalid_range.headers["location"]



def test_athlete_crud_auto_bib_and_age_warning(client, app):
    event_id = create_event(client)
    create_category(client, event_id, "Adulto", 30, 39)
    create_category(client, event_id, "Master", 40, 49)
    azul = create_team(client, event_id, "Azul")
    verde = create_team(client, event_id, "Verde")

    response = client.post(
        f"/eventos/{event_id}/atletas/novo",
        data={
            "name": "Ana Souza",
            "age": "34",
            "category_id": "1",
            "team_id": str(azul),
            "sex": "F",
            "bib": "",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Ana Souza" in response.text

    response = client.post(
        f"/eventos/{event_id}/atletas/novo",
        data={
            "name": "Bia Lima",
            "age": "28",
            "category_id": "1",
            "team_id": str(verde),
            "sex": "F",
            "bib": "",
        },
        follow_redirects=True,
    )
    assert "Idade 28 abaixo da faixa" in response.text

    from app.database import connect

    db = connect(app.state.db_path)
    rows = db.execute(
        "SELECT name, bib FROM athletes WHERE event_id = ? ORDER BY bib", (event_id,)
    ).fetchall()
    assert [(row["name"], row["bib"]) for row in rows] == [
        ("Ana Souza", 1),
        ("Bia Lima", 2),
    ]

    duplicate = client.post(
        f"/eventos/{event_id}/atletas/novo",
        data={
            "name": "Carla",
            "age": "31",
            "category_id": "1",
            "team_id": "",
            "sex": "F",
            "bib": "1",
        },
    )
    assert duplicate.status_code == 422
    assert "já está em uso" in duplicate.text

    ana = db.execute(
        "SELECT id FROM athletes WHERE name = 'Ana Souza'"
    ).fetchone()["id"]
    response = client.post(
        f"/eventos/{event_id}/atletas/{ana}/editar",
        data={
            "name": "Ana Souza",
            "age": "34",
            "category_id": "2",
            "team_id": str(azul),
            "sex": "F",
            "bib": "1",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    updated = db.execute(
        "SELECT c.name FROM athletes a JOIN race_groups rg ON rg.id = a.race_group_id "
        "JOIN categories c ON c.id = rg.category_id WHERE a.id = ?",
        (ana,),
    ).fetchone()
    assert updated["name"] == "Master"

    response = client.post(
        f"/eventos/{event_id}/atletas/{ana}/excluir", follow_redirects=True
    )
    assert response.status_code == 200
    assert "excluído" in response.text
    assert db.execute(
        "SELECT COUNT(*) AS total FROM athletes WHERE id = ?", (ana,)
    ).fetchone()["total"] == 0
    db.close()


def test_athlete_validation_and_filters(client):
    event_id = create_event(client)
    create_category(client, event_id, "Adulto", 30, 39)
    create_athlete(
        client,
        event_id,
        name="Carlos",
        age=35,
        category_id=1,
        sex="M",
        bib=20,
        team="Time Alfa",
    )
    create_athlete(
        client,
        event_id,
        name="Daniela",
        age=33,
        category_id=1,
        sex="F",
        bib=10,
        team="Time Beta",
    )

    invalid = client.post(
        f"/eventos/{event_id}/atletas/novo",
        data={
            "name": "",
            "age": "200",
            "category_id": "",
            "team_id": "",
            "sex": "X",
            "bib": "-1",
        },
    )
    assert invalid.status_code == 422
    assert "Informe o nome" in invalid.text
    assert "entre 1 e 120" in invalid.text

    response = client.get(f"/eventos/{event_id}/atletas?sex=F&q=Daniela")
    assert response.status_code == 200
    assert "Daniela" in response.text
    assert ">Carlos<" not in response.text

    response = client.get(f"/eventos/{event_id}/atletas?category_id=1")
    assert "Carlos" in response.text and "Daniela" in response.text


def test_category_delete_is_blocked_when_in_use(client, db):
    event_id = create_event(client)
    create_category(client, event_id, "Adulto", 30, 39)
    create_athlete(
        client, event_id, name="Ana", age=33, category_id=1, sex="F", bib=101
    )
    response = client.post(
        f"/eventos/{event_id}/categorias/1/excluir", follow_redirects=True
    )
    assert "possui atletas" in response.text
    assert db.execute("SELECT COUNT(*) AS total FROM categories").fetchone()["total"] == 1
