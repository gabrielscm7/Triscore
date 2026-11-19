from __future__ import annotations

from tests.conftest import create_athlete, create_category, create_event


def configure_event(
    client,
    event_id,
    *,
    limit=2,
    schedule=True,
    start="07:30",
    athlete_interval=60,
    heat_interval=300,
):
    response = client.post(
        f"/eventos/{event_id}/configuracao",
        data={
            "name": "Prova Teste",
            "event_date": "2026-08-15",
            "location": "Cidade Teste",
            "heat_limit": str(limit),
            "schedule_enabled": "1" if schedule else "",
            "schedule_start": start,
            "athlete_interval_seconds": str(athlete_interval),
            "heat_interval_seconds": str(heat_interval),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def heat_rows(db, event_id):
    return db.execute(
        "SELECT * FROM heats WHERE event_id = ? ORDER BY sequence", (event_id,)
    ).fetchall()


def entry_names(db, heat_id):
    return [
        row["name"]
        for row in db.execute(
            "SELECT a.name FROM heat_entries he JOIN athletes a ON a.id = he.athlete_id "
            "WHERE he.heat_id = ? ORDER BY he.position",
            (heat_id,),
        ).fetchall()
    ]


def test_heat_generation_split_schedule_and_rejections(client, db):
    event_id = create_event(client)
    create_category(client, event_id, "Adulto", 30, 39)
    for index, name in enumerate(["Ana", "Bia", "Carla", "Duda", "Eva"], start=1):
        create_athlete(
            client,
            event_id,
            name=name,
            age=34,
            category_id=1,
            sex="F",
            bib=index,
        )
    create_athlete(
        client, event_id, name="Mario", age=35, category_id=1, sex="M", bib=6
    )
    create_athlete(
        client, event_id, name="Nilo", age=36, category_id=1, sex="M", bib=7
    )
    configure_event(client, event_id)

    response = client.post(
        f"/eventos/{event_id}/baterias/gerar",
        data={"category_id": "1", "sex_mode": "F", "criterion": "bib"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "5 atleta(s) distribuído(s) em 3 bateria(s)" in response.text

    heats = heat_rows(db, event_id)
    assert [(row["label"], row["sex_mode"], row["sequence"]) for row in heats] == [
        ("A", "F", 1),
        ("B", "F", 2),
        ("C", "F", 3),
    ]
    assert [len(entry_names(db, row["id"])) for row in heats] == [2, 2, 1]

    response = client.post(
        f"/eventos/{event_id}/baterias/gerar",
        data={"category_id": "1", "sex_mode": "F", "criterion": "bib"},
        follow_redirects=True,
    )
    assert "Já existem baterias" in response.text

    client.post(
        f"/eventos/{event_id}/baterias/gerar",
        data={"category_id": "1", "sex_mode": "M", "criterion": "alpha"},
    )
    heats = heat_rows(db, event_id)
    assert heats[-1]["label"] == "A"
    assert heats[-1]["sex_mode"] == "M"
    assert heats[-1]["sequence"] == 4
    assert entry_names(db, heats[-1]["id"]) == ["Mario", "Nilo"]

    builder = client.get(f"/eventos/{event_id}/baterias")
    assert "07:36" in builder.text
    assert "07:42" in builder.text

    full_heat = heats[0]["id"]
    last_heat = heats[2]["id"]
    move = client.post(
        f"/eventos/{event_id}/baterias/mover-atleta",
        json={"athlete_id": 5, "target_heat_id": full_heat, "before_athlete_id": None},
    )
    assert move.status_code == 400
    assert "cheia" in move.json()["detail"].lower()

    male_athlete = db.execute(
        "SELECT id FROM athletes WHERE name = 'Mario'"
    ).fetchone()["id"]
    incompatible = client.post(
        f"/eventos/{event_id}/baterias/mover-atleta",
        json={"athlete_id": male_athlete, "target_heat_id": last_heat},
    )
    assert incompatible.status_code == 400
    assert "sexo" in incompatible.json()["detail"].lower()

    fifth = db.execute("SELECT id FROM athletes WHERE name = 'Eva'").fetchone()["id"]
    unassign = client.post(
        f"/eventos/{event_id}/baterias/mover-atleta",
        json={"athlete_id": fifth, "target_heat_id": None},
    )
    assert unassign.status_code == 200
    full_from_pool = client.post(
        f"/eventos/{event_id}/baterias/mover-atleta",
        json={"athlete_id": fifth, "target_heat_id": full_heat},
    )
    assert full_from_pool.status_code == 400
    assert "cheia" in full_from_pool.json()["detail"].lower()

    client.post(
        f"/eventos/{event_id}/baterias/nova",
        data={"category_id": "1", "sex_mode": "F"},
    )
    empty_heat = heat_rows(db, event_id)[-1]
    assert empty_heat["label"] == "D"
    move = client.post(
        f"/eventos/{event_id}/baterias/mover-atleta",
        json={"athlete_id": fifth, "target_heat_id": empty_heat["id"]},
    )
    assert move.status_code == 200
    assert entry_names(db, empty_heat["id"]) == ["Eva"]


def test_mixed_heat_keeps_classification_groups(client, db):
    event_id = create_event(client)
    create_category(client, event_id, "Open", 18, 59)
    create_athlete(
        client, event_id, name="Ana", age=30, category_id=1, sex="F", bib=1
    )
    create_athlete(
        client, event_id, name="Bia", age=31, category_id=1, sex="F", bib=2
    )
    create_athlete(
        client, event_id, name="Caio", age=32, category_id=1, sex="M", bib=3
    )
    configure_event(client, event_id, limit=4)

    response = client.post(
        f"/eventos/{event_id}/baterias/gerar",
        data={"category_id": "1", "sex_mode": "X", "criterion": "bib"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    heats = heat_rows(db, event_id)
    assert len(heats) == 1
    assert heats[0]["sex_mode"] == "X"
    assert entry_names(db, heats[0]["id"]) == ["Ana", "Bia", "Caio"]

    groups = db.execute(
        "SELECT rg.sex, COUNT(a.id) AS total FROM race_groups rg "
        "LEFT JOIN athletes a ON a.race_group_id = rg.id "
        "WHERE rg.category_id = 1 GROUP BY rg.sex ORDER BY rg.sex"
    ).fetchall()
    assert [(row["sex"], row["total"]) for row in groups] == [("F", 2), ("M", 1)]


def test_heat_reorder_sort_and_delete_relabel(client, db):
    event_id = create_event(client)
    create_category(client, event_id, "Adulto", 30, 39)
    create_athlete(
        client, event_id, name="Zulu", age=34, category_id=1, sex="F", bib=1
    )
    create_athlete(
        client, event_id, name="Ana", age=34, category_id=1, sex="F", bib=2
    )
    create_athlete(
        client, event_id, name="Mia", age=34, category_id=1, sex="F", bib=3
    )
    create_athlete(
        client, event_id, name="Bia", age=34, category_id=1, sex="F", bib=4
    )
    create_athlete(
        client, event_id, name="Eva", age=34, category_id=1, sex="F", bib=5
    )
    configure_event(client, event_id, limit=2, schedule=False)

    client.post(
        f"/eventos/{event_id}/baterias/gerar",
        data={"category_id": "1", "sex_mode": "F", "criterion": "bib"},
    )
    heats = heat_rows(db, event_id)
    assert [row["label"] for row in heats] == ["A", "B", "C"]

    reversed_ids = [row["id"] for row in reversed(heats)]
    reorder = client.post(
        f"/eventos/{event_id}/baterias/ordem", json={"heat_ids": reversed_ids}
    )
    assert reorder.status_code == 200
    heats = heat_rows(db, event_id)
    assert [(row["id"], row["sequence"]) for row in heats] == [
        (reversed_ids[0], 1),
        (reversed_ids[1], 2),
        (reversed_ids[2], 3),
    ]

    selected_heat = heats[1]
    sort_response = client.post(
        f"/eventos/{event_id}/baterias/{selected_heat['id']}/ordenar",
        data={"criterion": "alpha"},
        follow_redirects=True,
    )
    assert sort_response.status_code == 200
    assert entry_names(db, selected_heat["id"]) == ["Bia", "Mia"]

    order_response = client.post(
        f"/eventos/{event_id}/baterias/{selected_heat['id']}/ordem-atletas",
        json={"athlete_ids": [
            db.execute("SELECT id FROM athletes WHERE name = 'Mia'").fetchone()["id"],
            db.execute("SELECT id FROM athletes WHERE name = 'Bia'").fetchone()["id"],
        ]},
    )
    assert order_response.status_code == 200
    assert entry_names(db, selected_heat["id"]) == ["Mia", "Bia"]

    delete_response = client.post(
        f"/eventos/{event_id}/baterias/{selected_heat['id']}/excluir",
        follow_redirects=True,
    )
    assert delete_response.status_code == 200
    remaining = heat_rows(db, event_id)
    assert [(row["label"], row["sequence"]) for row in remaining] == [
        ("A", 1),
        ("B", 2),
    ]
    assert db.execute(
        "SELECT COUNT(*) AS total FROM heat_entries WHERE heat_id = ?",
        (selected_heat["id"],),
    ).fetchone()["total"] == 0


def test_deleting_assigned_athlete_renumbers_heat(client, db):
    event_id = create_event(client)
    create_category(client, event_id, "Adulto", 30, 39)
    for index, name in enumerate(["Ana", "Bia", "Carla"], start=1):
        create_athlete(
            client,
            event_id,
            name=name,
            age=34,
            category_id=1,
            sex="F",
            bib=index,
        )
    configure_event(client, event_id, limit=10, schedule=False)
    client.post(
        f"/eventos/{event_id}/baterias/gerar",
        data={"category_id": "1", "sex_mode": "F", "criterion": "bib"},
    )
    heat = heat_rows(db, event_id)[0]
    bia = db.execute("SELECT id FROM athletes WHERE name = 'Bia'").fetchone()["id"]
    response = client.post(
        f"/eventos/{event_id}/atletas/{bia}/excluir", follow_redirects=True
    )
    assert response.status_code == 200
    assert entry_names(db, heat["id"]) == ["Ana", "Carla"]
    positions = [
        row["position"]
        for row in db.execute(
            "SELECT position FROM heat_entries WHERE heat_id = ? ORDER BY position",
            (heat["id"],),
        ).fetchall()
    ]
    assert positions == [1, 2]
