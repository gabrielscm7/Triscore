from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from app.database import connect, transaction
from app.services import athletes as athlete_service
from app.services import classification as classification_service
from app.services import pdf_exports
from app.services import results as result_service
from tests.conftest import create_athlete, create_category, create_event


def _create_heat(connection, event_id, category_id, label, sequence, athlete_ids):
    cursor = connection.execute(
        """
        INSERT INTO heats (event_id, category_id, sex_mode, label, sequence)
        VALUES (?, ?, 'F', ?, ?)
        """,
        (event_id, category_id, label, sequence),
    )
    heat_id = int(cursor.lastrowid)
    for position, athlete_id in enumerate(athlete_ids, start=1):
        connection.execute(
            "INSERT INTO heat_entries (heat_id, athlete_id, position) VALUES (?, ?, ?)",
            (heat_id, athlete_id, position),
        )
    return heat_id


def test_pdf_exports_files_endpoints_tables_and_content(client, db, app):
    event_id = create_event(client, "Prova PDF")
    create_category(client, event_id, "Adulto", 30, 39)
    for name, bib, sex in (("Ana", 101, "F"), ("Bia", 102, "F"), ("Carla", 103, "F")):
        create_athlete(
            client,
            event_id,
            name=name,
            age=34,
            category_id=1,
            sex=sex,
            bib=bib,
            team="",
        )
    athletes = {
        row["name"]: row["id"]
        for row in db.execute("SELECT id, name FROM athletes").fetchall()
    }
    with transaction(app.state.db_path) as connection:
        _create_heat(
            connection, event_id, 1, "A", 1, [athletes["Ana"], athletes["Bia"]]
        )
        _create_heat(connection, event_id, 1, "B", 2, [athletes["Carla"]])
        result_service.save_result(
            connection,
            event_id=event_id,
            athlete_id=athletes["Ana"],
            status="OK",
            final_time_cs=300000,
        )
        result_service.save_result(
            connection,
            event_id=event_id,
            athlete_id=athletes["Bia"],
            status="OK",
            final_time_cs=300000,
        )
        result_service.save_result(
            connection,
            event_id=event_id,
            athlete_id=athletes["Carla"],
            status="DNF",
            final_time_cs=None,
        )
        classification_service.update_tiebreak(connection, event_id, "real")

    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    event = dict(event)
    cron_rows = pdf_exports.cronograma_table_data(db, event)
    assert len(cron_rows) == 3
    sections = pdf_exports.start_list_sections(db, event)
    assert [len(section["entries"]) + 1 for section in sections] == [3, 2]
    groups, stats = pdf_exports.final_report_groups(db, event)
    assert sum(len(group["athletes"]) for group in groups) == 3
    assert stats["finished"] == 2 and stats["special"] == 1
    assert [athlete["position"] for athlete in groups[0]["athletes"]] == [
        1,
        1,
        None,
    ]

    expected = {
        "cronograma": "prova_pdf_cronograma_",
        "lista-largada": "prova_pdf_lista_largada_",
        "relatorio-final": "prova_pdf_relatorio_final_",
    }
    for route, prefix in expected.items():
        response = client.get(f"/eventos/{event_id}/pdfs/{route}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert prefix in response.headers["content-disposition"]
        assert response.content.startswith(b"%PDF")

    exports = sorted(client.app.state.exports_dir.glob("prova_pdf_*.pdf"))
    assert len(exports) == 3
    assert all(path.stat().st_size > 1000 for path in exports)
    for path in exports:
        reader = PdfReader(str(path))
        assert len(reader.pages) >= 1
        assert tuple(round(value) for value in reader.pages[0].mediabox[2:]) == (595, 842)

    start_pdf = next(
        client.app.state.exports_dir.glob("prova_pdf_lista_largada_*.pdf")
    )
    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(start_pdf)).pages)
    for name in ("Ana", "Bia", "Carla"):
        assert name in text
    assert "Tempo" in text

    final_pdf = next(
        client.app.state.exports_dir.glob("prova_pdf_relatorio_final_*.pdf")
    )
    final_reader = PdfReader(str(final_pdf))
    final_text = "\n".join(
        page.extract_text() or "" for page in final_reader.pages
    )
    assert "Resumo geral" in final_text
    assert "Observações" in final_text
    assert "DNF" in final_text
    assert "1" in final_text and "2" in final_text
    assert len(final_reader.pages[0].images) >= 1


def test_pdf_tables_repeat_headers_across_pages(client, db, app, tmp_path):
    event_id = create_event(client, "Prova Longa")
    create_category(client, event_id, "Geral", None, None)
    athlete_ids = []
    with transaction(app.state.db_path) as connection:
        for index in range(60):
            athlete_id = athlete_service.create_athlete(
                connection,
                event_id=event_id,
                category_id=1,
                name=f"Atleta {index + 1:02d}",
                age=30,
                team_id=None,
                sex="F",
                bib=index + 1,
            )
            athlete_ids.append(athlete_id)
            result_service.save_result(
                connection,
                event_id=event_id,
                athlete_id=athlete_id,
                status="OK",
                final_time_cs=360000 + index * 100,
            )
        _create_heat(connection, event_id, 1, "A", 1, athlete_ids)

    event = dict(db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone())
    sections = pdf_exports.start_list_sections(db, event)
    assert len(sections) == 1
    assert len(sections[0]["entries"]) == 60

    start_pdf = pdf_exports.export_start_list(
        db, event, exports_dir=tmp_path / "exports"
    )
    start_reader = PdfReader(str(start_pdf))
    start_text = "\n".join(page.extract_text() or "" for page in start_reader.pages)
    assert len(start_reader.pages) >= 2
    assert start_text.count("Peito") >= 2
    assert all(f"Atleta {index:02d}" in start_text for index in range(1, 61))

    final_pdf = pdf_exports.export_final_report(
        db, event, exports_dir=tmp_path / "exports"
    )
    final_reader = PdfReader(str(final_pdf))
    final_text = "\n".join(page.extract_text() or "" for page in final_reader.pages)
    assert len(final_reader.pages) >= 3
    assert final_text.count("Peito") >= 2
    assert "Geral · Feminino" in final_text


def test_pdf_export_buttons_are_visible(client):
    event_id = create_event(client)
    create_category(client, event_id, "Adulto", 30, 39)
    builder = client.get(f"/eventos/{event_id}/baterias")
    assert f"/eventos/{event_id}/pdfs/cronograma" in builder.text
    assert f"/eventos/{event_id}/pdfs/lista-largada" in builder.text
    classification = client.get(f"/eventos/{event_id}/classificacao")
    assert f"/eventos/{event_id}/pdfs/relatorio-final" in classification.text


def test_disposable_test_results_seed(tmp_path):
    from scripts.seed_test_results import seed

    database = tmp_path / "teste.db"
    seed(database)
    connection = connect(database)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 6
        assert connection.execute(
            "SELECT classification_tiebreak FROM events"
        ).fetchone()[0] == "real"
        modes = {
            row[0]
            for row in connection.execute(
                "SELECT classification_mode FROM categories"
            ).fetchall()
        }
        assert modes == {"separate", "mixed"}
        statuses = {
            row[0]
            for row in connection.execute("SELECT status FROM results").fetchall()
        }
        assert statuses == {"OK", "DNF", "DSQ", "DNS"}
        total_athletes = connection.execute(
            "SELECT COUNT(*) FROM athletes"
        ).fetchone()[0]
        with_result = connection.execute(
            "SELECT COUNT(*) FROM results"
        ).fetchone()[0]
        assert total_athletes > with_result
    finally:
        connection.close()
    assert Path(database).exists()
