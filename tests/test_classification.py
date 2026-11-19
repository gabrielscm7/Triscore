from __future__ import annotations

from app.database import transaction
from app.services import classification as classification_service
from app.services import results as result_service
from tests.conftest import create_athlete, create_category, create_event


def _athlete_ids(db, event_id):
    return {
        row["name"]: row["id"]
        for row in db.execute(
            "SELECT id, name FROM athletes WHERE event_id = ?", (event_id,)
        ).fetchall()
    }


def test_classification_groups_by_category_and_sex_across_heats(
    client, db, app
):
    event_id = create_event(client)
    create_category(client, event_id, "Adulto", 30, 39)
    create_category(client, event_id, "Master", 40, 49)
    categories = {
        row["name"]: row["id"]
        for row in db.execute(
            "SELECT id, name FROM categories WHERE event_id = ?", (event_id,)
        ).fetchall()
    }
    for name, bib, sex, category in (
        ("M1", 101, "M", "Adulto"),
        ("M2", 102, "M", "Adulto"),
        ("M3", 103, "M", "Adulto"),
        ("M4", 104, "M", "Adulto"),
        ("F1", 105, "F", "Adulto"),
        ("F2", 106, "F", "Adulto"),
        ("Outro", 201, "M", "Master"),
    ):
        create_athlete(
            client,
            event_id,
            name=name,
            age=34,
            category_id=categories[category],
            sex=sex,
            bib=bib,
            team="",
        )
    athletes = _athlete_ids(db, event_id)

    with transaction(app.state.db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO heats (event_id, category_id, sex_mode, label, sequence)
            VALUES (?, ?, 'M', 'A', 1)
            """,
            (event_id, categories["Adulto"]),
        )
        heat_a = int(cursor.lastrowid)
        cursor = connection.execute(
            """
            INSERT INTO heats (event_id, category_id, sex_mode, label, sequence)
            VALUES (?, ?, 'M', 'B', 2)
            """,
            (event_id, categories["Adulto"]),
        )
        heat_b = int(cursor.lastrowid)
        connection.execute(
            "INSERT INTO heat_entries (heat_id, athlete_id, position) VALUES (?, ?, 1)",
            (heat_a, athletes["M1"]),
        )
        connection.execute(
            "INSERT INTO heat_entries (heat_id, athlete_id, position) VALUES (?, ?, 1)",
            (heat_b, athletes["M2"]),
        )
        for name, status, final_time in (
            ("M1", "OK", 180000),
            ("M2", "OK", 150000),
            ("M4", "DNF", None),
            ("F1", "OK", 240000),
            ("F2", "DNS", None),
            ("Outro", "OK", 200000),
        ):
            result_service.save_result(
                connection,
                event_id=event_id,
                athlete_id=athletes[name],
                status=status,
                final_time_cs=final_time,
            )

    groups = classification_service.build_classification(db, event_id)
    assert [(group["category_name"], group["sex_label"]) for group in groups] == [
        ("Adulto", "Masculino"),
        ("Adulto", "Feminino"),
        ("Master", "Masculino"),
    ]

    adult_male = groups[0]
    assert [athlete["name"] for athlete in adult_male["athletes"]] == [
        "M2",
        "M1",
        "M4",
        "M3",
    ]
    assert [athlete["position"] for athlete in adult_male["athletes"]] == [
        1,
        2,
        None,
        None,
    ]
    assert [athlete["result_status"] for athlete in adult_male["athletes"]] == [
        "OK",
        "OK",
        "DNF",
        None,
    ]
    assert adult_male["athletes"][0]["heat_label"] == "B"
    assert adult_male["athletes"][1]["heat_label"] == "A"
    assert adult_male["finished_count"] == 2
    assert adult_male["special_count"] == 1
    assert adult_male["pending_count"] == 1

    adult_female = groups[1]
    assert [athlete["name"] for athlete in adult_female["athletes"]] == [
        "F1",
        "F2",
    ]
    assert [athlete["position"] for athlete in adult_female["athletes"]] == [1, None]

    stats = classification_service.classification_stats(groups)
    assert stats == {
        "groups": 3,
        "athletes": 7,
        "finished": 4,
        "special": 2,
        "pending": 1,
    }


def test_configurable_tiebreak_changes_only_equal_times(client, db, app):
    event_id = create_event(client)
    create_category(client, event_id, "Adulto", 30, 39)
    for name, bib in (("Zulu", 30), ("Ana", 20), ("Mia", 10)):
        create_athlete(
            client,
            event_id,
            name=name,
            age=34,
            category_id=1,
            sex="M",
            bib=bib,
            team="",
        )
    athletes = _athlete_ids(db, event_id)
    with transaction(app.state.db_path) as connection:
        for athlete_id in athletes.values():
            result_service.save_result(
                connection,
                event_id=event_id,
                athlete_id=athlete_id,
                status="OK",
                final_time_cs=180000,
            )

    def names(tiebreak):
        groups = classification_service.build_classification(
            db, event_id, tiebreak=tiebreak
        )
        return [athlete["name"] for athlete in groups[0]["athletes"]]

    assert names("bib") == ["Mia", "Ana", "Zulu"]
    assert names("name") == ["Ana", "Mia", "Zulu"]
    assert names("registration") == ["Zulu", "Ana", "Mia"]
    real_group = classification_service.build_classification(
        db, event_id, tiebreak="real"
    )[0]
    assert [athlete["position"] for athlete in real_group["athletes"]] == [1, 1, 1]

    page = client.get(f"/eventos/{event_id}/classificacao")
    assert page.status_code == 200
    assert 'value="bib" selected' in page.text

    changed = client.post(
        f"/eventos/{event_id}/classificacao/desempate",
        data={"tiebreak": "name"},
        follow_redirects=True,
    )
    assert "Critério de desempate atualizado" in changed.text
    assert classification_service.get_tiebreak(db, event_id) == "name"
    assert [athlete["name"] for athlete in classification_service.list_group_athletes(
        db, event_id
    )] == ["Zulu", "Ana", "Mia"]

    groups = classification_service.build_classification(db, event_id)
    assert [athlete["name"] for athlete in groups[0]["athletes"]] == [
        "Ana",
        "Mia",
        "Zulu",
    ]

    invalid = client.post(
        f"/eventos/{event_id}/classificacao/desempate",
        data={"tiebreak": "invalid"},
        follow_redirects=True,
    )
    assert "Critério de desempate inválido" in invalid.text
    assert classification_service.get_tiebreak(db, event_id) == "name"


def test_classification_page_renders_positions_specials_and_pending(client, db, app):
    event_id = create_event(client)
    empty = client.get(f"/eventos/{event_id}/classificacao")
    assert empty.status_code == 200
    assert "Nenhum atleta para classificar" in empty.text

    create_category(client, event_id, "Adulto", 30, 39)
    create_athlete(
        client, event_id, name="Ana", age=34, category_id=1, sex="F", bib=10
    )
    create_athlete(
        client, event_id, name="Bia", age=35, category_id=1, sex="F", bib=11
    )
    create_athlete(
        client, event_id, name="Carla", age=36, category_id=1, sex="F", bib=12
    )
    athletes = _athlete_ids(db, event_id)
    with transaction(app.state.db_path) as connection:
        result_service.save_result(
            connection,
            event_id=event_id,
            athlete_id=athletes["Ana"],
            status="OK",
            final_time_cs=253050,
        )
        result_service.save_result(
            connection,
            event_id=event_id,
            athlete_id=athletes["Bia"],
            status="DSQ",
            final_time_cs=None,
        )

    page = client.get(f"/eventos/{event_id}/classificacao")
    assert page.status_code == 200
    assert "Adulto" in page.text
    assert "Feminino" in page.text
    assert "42:10.50" in page.text
    assert "1º" in page.text
    assert "DSQ" in page.text
    assert "Sem resultado" in page.text
    assert "Carla" in page.text
    assert 'action="/eventos/1/classificacao/desempate"' in page.text


def test_mixed_category_has_single_podium(client, db, app):
    event_id = create_event(client)
    create_category(
        client,
        event_id,
        "Open",
        18,
        59,
        classification_mode="mixed",
    )
    for name, bib, sex, final_time in (
        ("Ana", 10, "F", 360000),
        ("Bruno", 11, "M", 330000),
        ("Carla", 12, "F", 340000),
        ("Diego", 13, "M", 350000),
    ):
        create_athlete(
            client,
            event_id,
            name=name,
            age=30,
            category_id=1,
            sex=sex,
            bib=bib,
            team="",
        )
    athletes = _athlete_ids(db, event_id)
    with transaction(app.state.db_path) as connection:
        for name, final_time in (
            ("Ana", 360000),
            ("Bruno", 330000),
            ("Carla", 340000),
            ("Diego", 350000),
        ):
            result_service.save_result(
                connection,
                event_id=event_id,
                athlete_id=athletes[name],
                status="OK",
                final_time_cs=final_time,
            )

    groups = classification_service.build_classification(db, event_id)
    assert len(groups) == 1
    group = groups[0]
    assert group["sex"] == "X"
    assert group["sex_label"] == "Misto"
    assert [athlete["name"] for athlete in group["athletes"]] == [
        "Bruno",
        "Carla",
        "Diego",
        "Ana",
    ]
    assert [athlete["position"] for athlete in group["athletes"]] == [1, 2, 3, 4]

    page = client.get(f"/eventos/{event_id}/classificacao")
    assert page.status_code == 200
    assert "Misto" in page.text
    assert "Open" in page.text


def test_real_tiebreak_shares_positions_and_warns_on_top_three(client, db, app):
    event_id = create_event(client)
    create_category(client, event_id, "Adulto", 30, 39)
    for name, bib, final_time in (
        ("Ana", 10, 60000),
        ("Bia", 20, 66000),
        ("Caio", 30, 66000),
        ("Duda", 40, 72000),
    ):
        create_athlete(
            client,
            event_id,
            name=name,
            age=34,
            category_id=1,
            sex="F",
            bib=bib,
            team="",
        )
    athletes = _athlete_ids(db, event_id)
    with transaction(app.state.db_path) as connection:
        for name, final_time in (
            ("Ana", 60000),
            ("Bia", 66000),
            ("Caio", 66000),
            ("Duda", 72000),
        ):
            result_service.save_result(
                connection,
                event_id=event_id,
                athlete_id=athletes[name],
                status="OK",
                final_time_cs=final_time,
            )
    with transaction(app.state.db_path) as connection:
        classification_service.update_tiebreak(connection, event_id, "real")

    groups = classification_service.build_classification(db, event_id)
    assert [athlete["position"] for athlete in groups[0]["athletes"]] == [
        1,
        2,
        2,
        4,
    ]
    warnings = classification_service.top_three_tie_warnings(groups)
    assert len(warnings) == 1
    assert warnings[0]["count"] == 2
    assert warnings[0]["time"] == "11:00.00"

    page = client.get(f"/eventos/{event_id}/classificacao")
    assert page.status_code == 200
    assert "empate dentro das três primeiras posições" in page.text
    assert "2 atletas com o tempo 11:00.00" in page.text
    assert 'value="real" selected' in page.text
