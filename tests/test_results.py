from __future__ import annotations

import sqlite3

import pytest

from app.database import transaction
from app.services import results as result_service
from tests.conftest import create_athlete, create_category, create_event


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("42:10", 253000),
        ("42:10.5", 253050),
        ("01:02:03.45", 372345),
        ("1:02:03,45", 372345),
        ("90:00.00", 540000),
        ("0:00", 0),
    ],
)
def test_parse_result_time_formats(value, expected):
    assert result_service.parse_result_time(value) == expected


@pytest.mark.parametrize(
    "value",
    ["", "abc", "1", "1:2:3:4", "1:60:00", "1:2:60", "1:2.345", "1:2,3,4"],
)
def test_parse_result_time_rejects_invalid_input(value):
    with pytest.raises(ValueError):
        result_service.parse_result_time(value)


def test_result_crud_summary_and_automatic_backups(client, db, app):
    event_id = create_event(client)
    create_category(client, event_id, "Adulto", 30, 39)
    create_athlete(
        client, event_id, name="Ana", age=34, category_id=1, sex="F", bib=1
    )
    create_athlete(
        client, event_id, name="Bia", age=35, category_id=1, sex="M", bib=2
    )
    ana_id = db.execute("SELECT id FROM athletes WHERE name = 'Ana'").fetchone()["id"]
    bia_id = db.execute("SELECT id FROM athletes WHERE name = 'Bia'").fetchone()["id"]

    page = client.get(f"/eventos/{event_id}/sumula")
    assert page.status_code == 200
    assert "Súmula" in page.text
    assert "Ana" in page.text and "Bia" in page.text
    assert "<strong>0</strong> lançados" in page.text

    backup_dir = client.app.state.backup_dir
    assert list(backup_dir.glob("triscore-pre-sumula-*.db")) == []

    saved = client.post(
        f"/eventos/{event_id}/sumula/{ana_id}",
        data={"status": "OK", "final_time": "1:02:03.45"},
        follow_redirects=True,
    )
    assert "Resultado de Ana salvo" in saved.text
    assert "1:02:03.45" in saved.text
    result = db.execute(
        "SELECT status, final_time_cs FROM results WHERE athlete_id = ?", (ana_id,)
    ).fetchone()
    assert (result["status"], result["final_time_cs"]) == ("OK", 372345)
    backups = sorted(backup_dir.glob("triscore-pre-sumula-*.db"))
    assert len(backups) == 1
    backup = sqlite3.connect(backups[0])
    try:
        assert backup.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 0
        assert backup.execute("SELECT COUNT(*) FROM athletes").fetchone()[0] == 2
    finally:
        backup.close()

    edited = client.post(
        f"/eventos/{event_id}/sumula/{ana_id}",
        data={"status": "OK", "final_time": "42:10.5"},
        follow_redirects=True,
    )
    assert "42:10.50" in edited.text
    result = db.execute(
        "SELECT status, final_time_cs FROM results WHERE athlete_id = ?", (ana_id,)
    ).fetchone()
    assert (result["status"], result["final_time_cs"]) == ("OK", 253050)
    assert db.execute(
        "SELECT COUNT(*) FROM results WHERE athlete_id = ?", (ana_id,)
    ).fetchone()[0] == 1
    backups = sorted(backup_dir.glob("triscore-pre-sumula-*.db"))
    assert len(backups) == 2
    backup = sqlite3.connect(backups[-1])
    try:
        previous = backup.execute(
            "SELECT status, final_time_cs FROM results WHERE athlete_id = ?", (ana_id,)
        ).fetchone()
        assert previous == ("OK", 372345)
    finally:
        backup.close()

    special = client.post(
        f"/eventos/{event_id}/sumula/{bia_id}",
        data={"status": "DNF", "final_time": "99:99"},
        follow_redirects=True,
    )
    assert "Resultado de Bia salvo" in special.text
    result = db.execute(
        "SELECT status, final_time_cs FROM results WHERE athlete_id = ?", (bia_id,)
    ).fetchone()
    assert (result["status"], result["final_time_cs"]) == ("DNF", None)

    invalid = client.post(
        f"/eventos/{event_id}/sumula/{ana_id}",
        data={"status": "OK", "final_time": "abc"},
        follow_redirects=True,
    )
    assert "Use mm:ss" in invalid.text
    result = db.execute(
        "SELECT status, final_time_cs FROM results WHERE athlete_id = ?", (ana_id,)
    ).fetchone()
    assert (result["status"], result["final_time_cs"]) == ("OK", 253050)
    assert len(list(backup_dir.glob("triscore-pre-sumula-*.db"))) == 3

    page = client.get(f"/eventos/{event_id}/sumula")
    assert "<strong>2</strong> lançados" in page.text
    assert "<strong>0</strong> pendentes" in page.text

    deleted = client.post(
        f"/eventos/{event_id}/sumula/{bia_id}/excluir", follow_redirects=True
    )
    assert "Resultado excluído" in deleted.text
    assert db.execute(
        "SELECT COUNT(*) FROM results WHERE athlete_id = ?", (bia_id,)
    ).fetchone()[0] == 0
    assert len(list(backup_dir.glob("triscore-pre-sumula-*.db"))) == 4

    missing = client.post(
        f"/eventos/{event_id}/sumula/{bia_id}/excluir", follow_redirects=True
    )
    assert "ainda não possui resultado" in missing.text


def test_result_summary_counts_and_all_special_statuses(client, db, app):
    event_id = create_event(client)
    create_category(client, event_id, "Adulto", 30, 39)
    for index, name in enumerate(("Ana", "Bia", "Caio", "Duda", "Eva"), start=1):
        create_athlete(
            client,
            event_id,
            name=name,
            age=30 + index,
            category_id=1,
            sex="F" if index % 2 else "M",
            bib=index,
        )
    athlete_ids = {
        row["name"]: row["id"]
        for row in db.execute("SELECT id, name FROM athletes").fetchall()
    }
    with transaction(app.state.db_path) as connection:
        result_service.save_result(
            connection,
            event_id=event_id,
            athlete_id=athlete_ids["Ana"],
            status="OK",
            final_time_cs=123456,
        )
        for name, status in (("Bia", "DNF"), ("Caio", "DSQ"), ("Duda", "DNS")):
            result_service.save_result(
                connection,
                event_id=event_id,
                athlete_id=athlete_ids[name],
                status=status,
                final_time_cs=None,
            )

    stats = result_service.result_stats(db, event_id)
    assert stats == {
        "total": 5,
        "entered": 4,
        "ok": 1,
        "dnf": 1,
        "dsq": 1,
        "dns": 1,
        "pending": 1,
        "special": 3,
    }
    listing = result_service.list_results(db, event_id)
    assert [row["name"] for row in listing] == ["Ana", "Bia", "Caio", "Duda", "Eva"]
    assert listing[0]["formatted_time"] == "20:34.56"
    assert listing[1]["result_status"] == "DNF"
    assert listing[4]["result_status"] is None


def test_result_rejects_athlete_from_other_event(client, db, app):
    event_id = create_event(client, "Prova Um")
    other_event_id = create_event(client, "Prova Dois")
    create_category(client, event_id, "Adulto", 30, 39)
    create_category(client, other_event_id, "Adulto", 30, 39)
    other_category_id = db.execute(
        "SELECT id FROM categories WHERE event_id = ?", (other_event_id,)
    ).fetchone()["id"]
    create_athlete(
        client,
        other_event_id,
        name="Externo",
        age=32,
        category_id=other_category_id,
        sex="M",
        bib=1,
    )
    external_id = db.execute(
        "SELECT id FROM athletes WHERE event_id = ?", (other_event_id,)
    ).fetchone()["id"]

    response = client.post(
        f"/eventos/{event_id}/sumula/{external_id}",
        data={"status": "OK", "final_time": "30:00"},
        follow_redirects=True,
    )
    assert "Atleta não encontrado nesta prova" in response.text
    assert db.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 0
