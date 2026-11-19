from __future__ import annotations

import sqlite3
from typing import Any

from app.utils import clean_text

RESULT_STATUSES = ("OK", "DNF", "DSQ", "DNS")
STATUS_LABELS = {
    "OK": "Tempo válido",
    "DNF": "DNF — não finalizou",
    "DSQ": "DSQ — desclassificado",
    "DNS": "DNS — não largou",
}


def parse_result_time(value: str | None) -> int:
    text = clean_text(value).replace(",", ".")
    if not text:
        raise ValueError("Informe o tempo do atleta.")

    parts = text.split(":")
    if len(parts) not in (2, 3):
        raise ValueError("Use mm:ss, hh:mm:ss ou o mesmo formato com centésimos.")

    fraction = 0
    last = parts[-1]
    if "." in last:
        last, fraction_text = last.split(".", 1)
        if not fraction_text.isdigit() or len(fraction_text) > 2:
            raise ValueError("Os centésimos devem ter uma ou duas casas decimais.")
        fraction = int(fraction_text.ljust(2, "0"))
        parts[-1] = last

    if not all(part.isdigit() for part in parts):
        raise ValueError("O tempo deve conter apenas números, dois-pontos e centésimos.")

    numbers = [int(part) for part in parts]
    if len(numbers) == 2:
        minutes, seconds = numbers
        hours = 0
    else:
        hours, minutes, seconds = numbers
        if minutes > 59:
            raise ValueError("Os minutos devem estar entre 0 e 59.")

    if seconds > 59:
        raise ValueError("Os segundos devem estar entre 0 e 59.")

    total_seconds = hours * 3600 + minutes * 60 + seconds
    return total_seconds * 100 + fraction


def format_result_time(final_time_cs: int | None) -> str:
    if final_time_cs is None:
        return ""
    value = max(0, int(final_time_cs))
    hours, remainder = divmod(value, 360000)
    minutes, remainder = divmod(remainder, 6000)
    seconds, centiseconds = divmod(remainder, 100)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"
    return f"{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def parse_result_fields(
    status: str | None, final_time: str | None
) -> tuple[str, int | None]:
    value = clean_text(status).upper()
    if value not in RESULT_STATUSES:
        raise ValueError("Selecione um resultado válido.")
    if value != "OK":
        return value, None
    return value, parse_result_time(final_time)


def _result_row(
    connection: sqlite3.Connection, event_id: int, athlete_id: int
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT r.*
        FROM results r
        JOIN athletes a ON a.id = r.athlete_id
        WHERE r.athlete_id = ? AND a.event_id = ?
        """,
        (athlete_id, event_id),
    ).fetchone()


def get_result(
    connection: sqlite3.Connection, event_id: int, athlete_id: int
) -> dict[str, Any] | None:
    row = _result_row(connection, event_id, athlete_id)
    if row is None:
        return None
    result = dict(row)
    result["formatted_time"] = format_result_time(result["final_time_cs"])
    return result


def list_results(
    connection: sqlite3.Connection, event_id: int
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT a.id AS athlete_id, a.bib, a.name, a.age,
               t.name AS team, rg.sex, rg.category_id,
               c.name AS category_name,
               h.id AS heat_id, h.label AS heat_label,
               h.sequence AS heat_sequence, he.position AS heat_position,
               r.status AS result_status, r.final_time_cs,
               r.updated_at AS result_updated_at
        FROM athletes a
        JOIN race_groups rg ON rg.id = a.race_group_id
        JOIN categories c ON c.id = rg.category_id
        LEFT JOIN teams t ON t.id = a.team_id AND t.event_id = a.event_id
        LEFT JOIN heat_entries he ON he.athlete_id = a.id
        LEFT JOIN heats h ON h.id = he.heat_id
        LEFT JOIN results r ON r.athlete_id = a.id
        WHERE a.event_id = ?
        ORDER BY
            CASE WHEN h.id IS NULL THEN 1 ELSE 0 END,
            h.sequence,
            he.position,
            a.bib
        """,
        (event_id,),
    ).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        item["formatted_time"] = format_result_time(item["final_time_cs"])
        results.append(item)
    return results


def result_stats(
    connection: sqlite3.Connection, event_id: int
) -> dict[str, int]:
    row = connection.execute(
        """
        SELECT COUNT(a.id) AS total,
               COUNT(r.athlete_id) AS entered,
               COALESCE(SUM(CASE WHEN r.status = 'OK' THEN 1 ELSE 0 END), 0) AS ok,
               COALESCE(SUM(CASE WHEN r.status = 'DNF' THEN 1 ELSE 0 END), 0) AS dnf,
               COALESCE(SUM(CASE WHEN r.status = 'DSQ' THEN 1 ELSE 0 END), 0) AS dsq,
               COALESCE(SUM(CASE WHEN r.status = 'DNS' THEN 1 ELSE 0 END), 0) AS dns
        FROM athletes a
        LEFT JOIN results r ON r.athlete_id = a.id
        WHERE a.event_id = ?
        """,
        (event_id,),
    ).fetchone()
    stats = dict(row)
    stats["pending"] = stats["total"] - stats["entered"]
    stats["special"] = stats["dnf"] + stats["dsq"] + stats["dns"]
    return stats


def save_result(
    connection: sqlite3.Connection,
    *,
    event_id: int,
    athlete_id: int,
    status: str,
    final_time_cs: int | None,
) -> None:
    athlete = connection.execute(
        "SELECT id FROM athletes WHERE id = ? AND event_id = ?",
        (athlete_id, event_id),
    ).fetchone()
    if athlete is None:
        raise ValueError("Atleta não encontrado nesta prova.")
    status = clean_text(status).upper()
    if status not in RESULT_STATUSES:
        raise ValueError("Status de resultado inválido.")
    if status == "OK":
        if final_time_cs is None or int(final_time_cs) < 0:
            raise ValueError("Informe um tempo válido para o resultado.")
        final_time_cs = int(final_time_cs)
    else:
        final_time_cs = None

    connection.execute(
        """
        INSERT INTO results (athlete_id, status, final_time_cs)
        VALUES (?, ?, ?)
        ON CONFLICT(athlete_id) DO UPDATE SET
            status = excluded.status,
            final_time_cs = excluded.final_time_cs,
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        """,
        (athlete_id, status, final_time_cs),
    )


def delete_result(
    connection: sqlite3.Connection, event_id: int, athlete_id: int
) -> bool:
    result = _result_row(connection, event_id, athlete_id)
    if result is None:
        return False
    connection.execute("DELETE FROM results WHERE athlete_id = ?", (athlete_id,))
    return True
