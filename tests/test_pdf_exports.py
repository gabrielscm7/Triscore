from __future__ import annotations

import re
from pathlib import Path

import pytest
from pypdf import PdfReader
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import Paragraph

from app.database import connect, transaction
from app.services import athletes as athlete_service
from app.services import classification as classification_service
from app.services import events as event_service
from app.services import pdf_exports
from app.services import results as result_service
from app.services import teams as team_service
from tests.conftest import create_athlete, create_category, create_event

LONG_TEAM = (
    "Associacao Atlética Experimental de Triatlo e Corrida de Longa Distância "
    "do Vale do Rio Verde"
)
LONG_TEAM_WORD = "EquipeSuperHiperMegaBlasterUltraTriatlo2026"
SPECIAL_TEAM = "Equipe & Cia <Controle> de Testes"
LONG_ATHLETE = "Atleta com Nome Muito Longo de Teste Para Validar a Quebra de Linha"
LONG_CATEGORY = (
    "Categoria Experimental de Triatlo de Longa Distância com Nome Muito Extenso"
)
LONG_HEAT = "BateriaExtraordinariamenteLongaSemEspacos2026"
TEXT_COLUMNS = {"Nome", "Equipe", "Categoria", "Grupo", "Bateria"}


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _create_extreme_event(app, db):
    with transaction(app.state.db_path) as connection:
        event_id = event_service.create_event(
            connection,
            name="Validacao PDF Textos Extremos",
            event_date="2026-11-20",
            location="Arena de Validação Visual",
        )
        connection.execute(
            """
            UPDATE events
            SET schedule_enabled = 1, schedule_start = '08:00',
                athlete_interval_seconds = 30, heat_interval_seconds = 300
            WHERE id = ?
            """,
            (event_id,),
        )
        category_id = event_service.create_category(
            connection,
            event_id=event_id,
            name=LONG_CATEGORY,
            min_age=None,
            max_age=None,
        )
        team_a = team_service.create_team(connection, event_id, LONG_TEAM)
        team_b = team_service.create_team(connection, event_id, LONG_TEAM_WORD)
        team_c = team_service.create_team(connection, event_id, SPECIAL_TEAM)
        specs = [
            (LONG_ATHLETE, 101, team_a, "OK", 360000),
            (
                "Atleta com PalavraUnicaMuitoLongaSemEspacosParaTeste",
                102,
                team_b,
                "OK",
                361234,
            ),
            ("Nome Médio & Símbolos <OK>", 103, team_c, "OK", 362468),
            ("Atleta DNS", 104, team_a, "DNS", None),
            ("Ana", 105, None, "OK", 363702),
        ]
        athlete_ids = []
        for name, bib, team_id, status, final_time_cs in specs:
            athlete_id = athlete_service.create_athlete(
                connection,
                event_id=event_id,
                category_id=category_id,
                name=name,
                age=35,
                team_id=team_id,
                sex="F",
                bib=bib,
            )
            athlete_ids.append(athlete_id)
            result_service.save_result(
                connection,
                event_id=event_id,
                athlete_id=athlete_id,
                status=status,
                final_time_cs=final_time_cs,
            )

        cursor = connection.execute(
            """
            INSERT INTO heats (event_id, category_id, sex_mode, label, sequence)
            VALUES (?, ?, 'F', ?, 1)
            """,
            (event_id, category_id, LONG_HEAT),
        )
        heat_id = int(cursor.lastrowid)
        for position, athlete_id in enumerate(athlete_ids, start=1):
            connection.execute(
                "INSERT INTO heat_entries (heat_id, athlete_id, position) VALUES (?, ?, ?)",
                (heat_id, athlete_id, position),
            )
    return dict(db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone())


def _export_extremes(db, event, output_dir: Path) -> dict[str, Path]:
    return {
        "cronograma": pdf_exports.export_cronograma(
            db, event, exports_dir=output_dir
        ),
        "lista_largada": pdf_exports.export_start_list(
            db, event, exports_dir=output_dir
        ),
        "relatorio_final": pdf_exports.export_final_report(
            db, event, exports_dir=output_dir
        ),
        "premiacao": pdf_exports.export_awards(db, event, exports_dir=output_dir),
    }


def _pdf_text(path: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


@pytest.fixture
def extreme_event(db, app):
    return _create_extreme_event(app, db)


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


def test_extreme_text_tables_use_growing_paragraphs_and_do_not_truncate(
    extreme_event, db, tmp_path, monkeypatch
):
    captured = []
    original_table = pdf_exports._table

    def capture_table(data, widths, **kwargs):
        table = original_table(data, widths, **kwargs)
        captured.append((data, table))
        return table

    monkeypatch.setattr(pdf_exports, "_table", capture_table)
    paths = _export_extremes(db, extreme_event, tmp_path / "exports")

    assert len(captured) == 4
    start_data, start_table = captured[1]
    for data, table in captured:
        assert table.repeatRows == 1
        assert table.splitByRow == 1
        assert table.splitInRow == 0
        headers = data[0]
        for index, header in enumerate(headers):
            if header in TEXT_COLUMNS:
                expected_alignment = TA_CENTER if header == "Bateria" else TA_LEFT
                for row in data[1:]:
                    cell = row[index]
                    assert isinstance(cell, Paragraph)
                    assert cell.style.splitLongWords is True
                    assert cell.style.alignment == expected_alignment
                    assert cell.style.fontSize >= 8
            elif header in {"Pos.", "Peito", "Tempo", "Status"}:
                for row in data[1:]:
                    assert not isinstance(row[index], Paragraph)

    assert start_table._colWidths[4] == pytest.approx(32 * mm)
    assert all(row[4] == "" for row in start_data[1:])
    assert start_table._minRowHeights[1] == pytest.approx(9 * mm)
    assert min(start_table._rowHeights[1:]) == pytest.approx(9 * mm, abs=0.1)
    assert max(start_table._rowHeights[1:]) > 9 * mm

    texts = {name: _pdf_text(path) for name, path in paths.items()}
    for name in ("lista_largada", "relatorio_final", "premiacao"):
        text = texts[name]
        normalized = _normalized(text)
        compact = _compact(text)
        assert LONG_TEAM in normalized
        assert SPECIAL_TEAM in normalized
        assert LONG_ATHLETE in normalized
        assert LONG_TEAM_WORD in compact

    assert LONG_CATEGORY in _normalized(texts["relatorio_final"])
    assert LONG_HEAT in _compact(texts["cronograma"])
    assert LONG_CATEGORY in _normalized(texts["cronograma"])


def test_start_list_team_text_stays_inside_its_column(
    extreme_event, db, tmp_path, monkeypatch
):
    captured = []
    original_table = pdf_exports._table

    def capture_table(data, widths, **kwargs):
        table = original_table(data, widths, **kwargs)
        captured.append((data, table))
        return table

    monkeypatch.setattr(pdf_exports, "_table", capture_table)
    start_path = pdf_exports.export_start_list(
        db, extreme_event, exports_dir=tmp_path / "exports"
    )
    _start_data, start_table = captured[0]
    page = PdfReader(str(start_path)).pages[0]
    needles = [_compact(value) for value in (LONG_TEAM, LONG_TEAM_WORD, SPECIAL_TEAM)]
    fragments = []

    def collect(text, cm, tm, _font_dict, font_size):
        raw = text.rstrip("\r\n")
        stripped = raw.strip()
        if not stripped or stripped == "Equipe":
            return
        compact = _compact(stripped)
        if len(compact) < 4 or not any(compact in needle for needle in needles):
            return
        x = float(cm[4]) + float(tm[4])
        width = pdfmetrics.stringWidth(
            raw, pdf_exports.FONT_REGULAR, float(font_size or 8)
        )
        fragments.append((raw, x, width))

    page.extract_text(visitor_text=collect)
    assert len(fragments) >= 5

    table_left = (
        min(x for _text, x, _width in fragments)
        - sum(start_table._colWidths[:3])
        - 4
    )
    team_left = table_left + sum(start_table._colWidths[:3]) + 4
    tempo_left = table_left + sum(start_table._colWidths[:4])
    team_content_right = tempo_left - 4
    for raw, x, width in fragments:
        assert x >= team_left - 0.5, raw
        assert x + width <= team_content_right + 0.75, raw


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
