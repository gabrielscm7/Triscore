from __future__ import annotations

import sqlite3
from typing import Any

from app.services.results import format_result_time
from app.utils import clean_text, sort_name

TIEBREAK_OPTIONS = {
    "bib": "Menor número de peito",
    "name": "Nome do atleta",
    "registration": "Ordem de cadastro",
    "real": "Empate real (mesma posição)",
}
DEFAULT_TIEBREAK = "bib"
STATUS_ORDER = {"OK": 0, "DNF": 1, "DSQ": 2, "DNS": 3, None: 4}
SEX_LABELS = {"M": "Masculino", "F": "Feminino", "X": "Misto"}


def validate_tiebreak(value: str | None) -> str:
    tiebreak = clean_text(value)
    if tiebreak not in TIEBREAK_OPTIONS:
        raise ValueError("Critério de desempate inválido.")
    return tiebreak


def get_tiebreak(connection: sqlite3.Connection, event_id: int) -> str:
    row = connection.execute(
        "SELECT classification_tiebreak FROM events WHERE id = ?", (event_id,)
    ).fetchone()
    if row is None:
        raise ValueError("Prova não encontrada.")
    return row["classification_tiebreak"] or DEFAULT_TIEBREAK


def update_tiebreak(
    connection: sqlite3.Connection, event_id: int, tiebreak: str
) -> None:
    value = validate_tiebreak(tiebreak)
    cursor = connection.execute(
        """
        UPDATE events
        SET classification_tiebreak = ?,
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
        """,
        (value, event_id),
    )
    if cursor.rowcount == 0:
        raise ValueError("Prova não encontrada.")


def _tiebreak_key(athlete: dict[str, Any], tiebreak: str) -> tuple[Any, ...]:
    if tiebreak == "name":
        return (
            sort_name(athlete["name"]),
            athlete["bib"],
            athlete["athlete_id"],
        )
    if tiebreak == "registration":
        return (athlete["athlete_id"],)
    return (athlete["bib"], athlete["athlete_id"])


def _sort_key(athlete: dict[str, Any], tiebreak: str) -> tuple[Any, ...]:
    status_rank = STATUS_ORDER[athlete["result_status"]]
    effective_tiebreak = "bib" if tiebreak == "real" else tiebreak
    if athlete["result_status"] == "OK":
        return (
            status_rank,
            athlete["final_time_cs"],
            _tiebreak_key(athlete, effective_tiebreak),
        )
    return (status_rank, _tiebreak_key(athlete, effective_tiebreak))


def list_group_athletes(
    connection: sqlite3.Connection, event_id: int
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT c.id AS category_id, c.name AS category_name,
               c.sort_order, c.min_age, c.max_age, c.classification_mode,
               rg.id AS race_group_id, rg.sex,
               a.id AS athlete_id, a.bib, a.name, a.age,
               t.name AS team,
               h.id AS heat_id, h.label AS heat_label,
               h.sequence AS heat_sequence, he.position AS heat_position,
               r.status AS result_status, r.final_time_cs
        FROM categories c
        JOIN race_groups rg
          ON rg.category_id = c.id AND rg.event_id = c.event_id
        JOIN athletes a ON a.race_group_id = rg.id
        LEFT JOIN teams t
          ON t.id = a.team_id AND t.event_id = a.event_id
        LEFT JOIN heat_entries he ON he.athlete_id = a.id
        LEFT JOIN heats h ON h.id = he.heat_id
        LEFT JOIN results r ON r.athlete_id = a.id
        WHERE c.event_id = ?
        ORDER BY c.sort_order, c.name COLLATE NOCASE,
                 CASE WHEN rg.sex = 'M' THEN 0 ELSE 1 END,
                 a.id
        """,
        (event_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def build_classification(
    connection: sqlite3.Connection,
    event_id: int,
    *,
    tiebreak: str | None = None,
) -> list[dict[str, Any]]:
    criterion = validate_tiebreak(tiebreak) if tiebreak else get_tiebreak(
        connection, event_id
    )
    grouped: dict[tuple[int, str], dict[str, Any]] = {}
    ordered_groups: list[dict[str, Any]] = []
    for row in list_group_athletes(connection, event_id):
        group_sex = "X" if row["classification_mode"] == "mixed" else row["sex"]
        key = (row["category_id"], group_sex)
        group = grouped.get(key)
        if group is None:
            group = {
                "category_id": row["category_id"],
                "category_name": row["category_name"],
                "sex": group_sex,
                "sex_label": SEX_LABELS[group_sex],
                "classification_mode": row["classification_mode"],
                "min_age": row["min_age"],
                "max_age": row["max_age"],
                "athletes": [],
            }
            grouped[key] = group
            ordered_groups.append(group)

        athlete = dict(row)
        athlete["formatted_time"] = format_result_time(athlete["final_time_cs"])
        group["athletes"].append(athlete)

    for group in ordered_groups:
        group["athletes"].sort(key=lambda row: _sort_key(row, criterion))
        position = 0
        last_time = None
        last_position = None
        for athlete in group["athletes"]:
            if athlete["result_status"] != "OK":
                athlete["position"] = None
                continue
            position += 1
            if criterion == "real":
                if last_time is not None and athlete["final_time_cs"] == last_time:
                    athlete["position"] = last_position
                else:
                    athlete["position"] = position
                    last_position = position
                last_time = athlete["final_time_cs"]
            else:
                athlete["position"] = position
        group["finished_count"] = sum(
            1 for athlete in group["athletes"] if athlete["result_status"] == "OK"
        )
        group["special_count"] = sum(
            1
            for athlete in group["athletes"]
            if athlete["result_status"] in ("DNF", "DSQ", "DNS")
        )
        group["pending_count"] = sum(
            1 for athlete in group["athletes"] if athlete["result_status"] is None
        )
    return ordered_groups


def classification_stats(groups: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "groups": len(groups),
        "athletes": sum(len(group["athletes"]) for group in groups),
        "finished": sum(group["finished_count"] for group in groups),
        "special": sum(group["special_count"] for group in groups),
        "pending": sum(group["pending_count"] for group in groups),
    }


def top_three_tie_warnings(
    groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    warnings = []
    for group in groups:
        by_time: dict[int, list[dict[str, Any]]] = {}
        for athlete in group["athletes"]:
            if athlete["position"] is None or athlete["position"] > 3:
                continue
            by_time.setdefault(athlete["final_time_cs"], []).append(athlete)
        for final_time_cs, tied in by_time.items():
            if len(tied) < 2:
                continue
            warnings.append(
                {
                    "category_name": group["category_name"],
                    "sex_label": group["sex_label"],
                    "time": format_result_time(final_time_cs),
                    "count": len(tied),
                    "names": [athlete["name"] for athlete in tied],
                }
            )
    return warnings
