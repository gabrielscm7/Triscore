from __future__ import annotations

import random
import sqlite3
from typing import Any

from app.utils import build_schedule, excel_label, sort_name


class HeatError(Exception):
    pass


def _category(
    connection: sqlite3.Connection, event_id: int, category_id: int
) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM categories WHERE id = ? AND event_id = ?",
        (category_id, event_id),
    ).fetchone()
    if row is None:
        raise HeatError("Categoria não encontrada nesta prova.")
    return dict(row)


def group_overview(
    connection: sqlite3.Connection, event_id: int
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT c.id AS category_id, c.name AS category_name, c.sort_order,
               c.min_age, c.max_age, rg.id AS race_group_id, rg.sex,
               COUNT(a.id) AS total,
               COALESCE(SUM(CASE WHEN he.id IS NULL THEN 1 ELSE 0 END), 0) AS available
        FROM categories c
        JOIN race_groups rg ON rg.category_id = c.id
        LEFT JOIN athletes a ON a.race_group_id = rg.id
        LEFT JOIN heat_entries he ON he.athlete_id = a.id
        WHERE c.event_id = ?
        GROUP BY c.id, rg.id
        ORDER BY c.sort_order, c.name COLLATE NOCASE, rg.sex
        """,
        (event_id,),
    ).fetchall()

    categories: list[dict[str, Any]] = []
    by_id: dict[int, dict[str, Any]] = {}
    for row in rows:
        category = by_id.get(row["category_id"])
        if category is None:
            category = {
                "id": row["category_id"],
                "name": row["category_name"],
                "min_age": row["min_age"],
                "max_age": row["max_age"],
                "male_total": 0,
                "female_total": 0,
                "male_available": 0,
                "female_available": 0,
            }
            by_id[row["category_id"]] = category
            categories.append(category)
        if row["sex"] == "M":
            category["male_total"] = int(row["total"])
            category["male_available"] = int(row["available"])
        else:
            category["female_total"] = int(row["total"])
            category["female_available"] = int(row["available"])

    for category in categories:
        category["total"] = category["male_total"] + category["female_total"]
        category["mixed_total"] = category["total"]
        category["mixed_available"] = (
            category["male_available"] + category["female_available"]
        )
    return categories


def _heat_rows(connection: sqlite3.Connection, event_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT h.*, c.name AS category_name
        FROM heats h
        JOIN categories c ON c.id = h.category_id
        WHERE h.event_id = ?
        ORDER BY h.sequence, h.id
        """,
        (event_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _entries_by_heat(
    connection: sqlite3.Connection, event_id: int
) -> dict[int, list[dict[str, Any]]]:
    rows = connection.execute(
        """
        SELECT he.id AS entry_id, he.heat_id, he.position,
               a.id AS athlete_id, a.bib, a.name, t.name AS team, a.age,
               rg.sex, rg.category_id, c.name AS category_name
        FROM heat_entries he
        JOIN heats h ON h.id = he.heat_id
        JOIN athletes a ON a.id = he.athlete_id
        JOIN race_groups rg ON rg.id = a.race_group_id
        JOIN categories c ON c.id = rg.category_id
        LEFT JOIN teams t ON t.id = a.team_id AND t.event_id = a.event_id
        WHERE h.event_id = ?
        ORDER BY h.sequence, he.position
        """,
        (event_id,),
    ).fetchall()
    entries: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        entries.setdefault(row["heat_id"], []).append(dict(row))
    return entries


def unassigned_athletes(
    connection: sqlite3.Connection, event_id: int
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT a.id, a.bib, a.name, t.name AS team, a.age,
               rg.sex, rg.category_id, c.name AS category_name
        FROM athletes a
        JOIN race_groups rg ON rg.id = a.race_group_id
        JOIN categories c ON c.id = rg.category_id
        LEFT JOIN teams t ON t.id = a.team_id AND t.event_id = a.event_id
        LEFT JOIN heat_entries he ON he.athlete_id = a.id
        WHERE a.event_id = ? AND he.id IS NULL
        ORDER BY a.bib
        """,
        (event_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def load_builder(
    connection: sqlite3.Connection, event: dict[str, Any]
) -> dict[str, Any]:
    heats = _heat_rows(connection, event["id"])
    entries = _entries_by_heat(connection, event["id"])
    for heat in heats:
        heat["entries"] = entries.get(heat["id"], [])
    build_schedule(heats, event)
    return {
        "event": event,
        "overview": group_overview(connection, event["id"]),
        "unassigned": unassigned_athletes(connection, event["id"]),
        "heats": heats,
    }


def _eligible_athletes(
    connection: sqlite3.Connection,
    event_id: int,
    category_id: int,
    sex_mode: str,
) -> list[dict[str, Any]]:
    sex_clause = "" if sex_mode == "X" else "AND rg.sex = ?"
    params: list[Any] = [event_id, category_id]
    if sex_mode != "X":
        params.append(sex_mode)
    rows = connection.execute(
        f"""
        SELECT a.id, a.bib, a.name
        FROM athletes a
        JOIN race_groups rg ON rg.id = a.race_group_id
        LEFT JOIN heat_entries he ON he.athlete_id = a.id
        WHERE a.event_id = ? AND rg.category_id = ? {sex_clause} AND he.id IS NULL
        ORDER BY a.bib
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def _sort_athletes(
    athletes: list[dict[str, Any]], criterion: str
) -> list[dict[str, Any]]:
    if criterion == "alpha":
        return sorted(athletes, key=lambda athlete: (sort_name(athlete["name"]), athlete["bib"]))
    if criterion == "random":
        shuffled = list(athletes)
        random.SystemRandom().shuffle(shuffled)
        return shuffled
    return sorted(athletes, key=lambda athlete: athlete["bib"])


def generate_heats(
    connection: sqlite3.Connection,
    event: dict[str, Any],
    *,
    category_id: int,
    sex_mode: str,
    criterion: str,
) -> tuple[int, int]:
    category = _category(connection, event["id"], category_id)
    if sex_mode not in ("M", "F", "X"):
        raise HeatError("Modalidade da bateria inválida.")
    existing = connection.execute(
        """
        SELECT COUNT(*) AS total FROM heats
        WHERE event_id = ? AND category_id = ? AND sex_mode = ?
        """,
        (event["id"], category_id, sex_mode),
    ).fetchone()["total"]
    if existing:
        raise HeatError(
            "Já existem baterias para esta categoria e modalidade. "
            "Exclua-as para gerar novamente ou use “Nova bateria vazia”."
        )

    eligible = _sort_athletes(
        _eligible_athletes(connection, event["id"], category_id, sex_mode), criterion
    )
    if not eligible:
        raise HeatError(
            "Não há atletas disponíveis nessa categoria e modalidade. "
            "Atletas já alocados em outra bateria não entram na geração."
        )

    limit = int(event["heat_limit"])
    chunks = [eligible[index : index + limit] for index in range(0, len(eligible), limit)]
    next_sequence = (
        connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 AS next FROM heats WHERE event_id = ?",
            (event["id"],),
        ).fetchone()["next"]
    )
    for heat_index, chunk in enumerate(chunks):
        cursor = connection.execute(
            """
            INSERT INTO heats (event_id, category_id, sex_mode, label, sequence)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event["id"],
                category["id"],
                sex_mode,
                excel_label(heat_index),
                next_sequence + heat_index,
            ),
        )
        heat_id = int(cursor.lastrowid)
        for position, athlete in enumerate(chunk, start=1):
            connection.execute(
                "INSERT INTO heat_entries (heat_id, athlete_id, position) VALUES (?, ?, ?)",
                (heat_id, athlete["id"], position),
            )
    return len(chunks), len(eligible)


def add_empty_heat(
    connection: sqlite3.Connection,
    event: dict[str, Any],
    *,
    category_id: int,
    sex_mode: str,
) -> int:
    _category(connection, event["id"], category_id)
    if sex_mode not in ("M", "F", "X"):
        raise HeatError("Modalidade da bateria inválida.")
    series_count = connection.execute(
        """
        SELECT COUNT(*) AS total FROM heats
        WHERE event_id = ? AND category_id = ? AND sex_mode = ?
        """,
        (event["id"], category_id, sex_mode),
    ).fetchone()["total"]
    next_sequence = connection.execute(
        "SELECT COALESCE(MAX(sequence), 0) + 1 AS next FROM heats WHERE event_id = ?",
        (event["id"],),
    ).fetchone()["next"]
    cursor = connection.execute(
        """
        INSERT INTO heats (event_id, category_id, sex_mode, label, sequence)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            event["id"],
            category_id,
            sex_mode,
            excel_label(series_count),
            next_sequence,
        ),
    )
    return int(cursor.lastrowid)


def compact_sequence(connection: sqlite3.Connection, event_id: int) -> None:
    rows = connection.execute(
        "SELECT id FROM heats WHERE event_id = ? ORDER BY sequence, id", (event_id,)
    ).fetchall()
    for index, row in enumerate(rows, start=1):
        connection.execute(
            "UPDATE heats SET sequence = ? WHERE id = ?", (index, row["id"])
        )


def relabel_series(
    connection: sqlite3.Connection,
    event_id: int,
    category_id: int,
    sex_mode: str,
) -> None:
    rows = connection.execute(
        """
        SELECT id FROM heats
        WHERE event_id = ? AND category_id = ? AND sex_mode = ?
        ORDER BY sequence, id
        """,
        (event_id, category_id, sex_mode),
    ).fetchall()
    for row in rows:
        connection.execute(
            "UPDATE heats SET label = ? WHERE id = ?", (f"~{row['id']}", row["id"])
        )
    for index, row in enumerate(rows):
        connection.execute(
            "UPDATE heats SET label = ? WHERE id = ?", (excel_label(index), row["id"])
        )


def delete_heat(
    connection: sqlite3.Connection, event_id: int, heat_id: int
) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM heats WHERE id = ? AND event_id = ?", (heat_id, event_id)
    ).fetchone()
    if row is None:
        raise HeatError("Bateria não encontrada.")
    heat = dict(row)
    count = connection.execute(
        "SELECT COUNT(*) AS total FROM heat_entries WHERE heat_id = ?", (heat_id,)
    ).fetchone()["total"]
    connection.execute("DELETE FROM heats WHERE id = ?", (heat_id,))
    compact_sequence(connection, event_id)
    relabel_series(connection, event_id, heat["category_id"], heat["sex_mode"])
    return {"heat": heat, "athlete_count": count}


def reorder_heats(
    connection: sqlite3.Connection, event_id: int, heat_ids: list[int]
) -> None:
    current = [
        row["id"]
        for row in connection.execute(
            "SELECT id FROM heats WHERE event_id = ? ORDER BY sequence, id", (event_id,)
        ).fetchall()
    ]
    if len(set(heat_ids)) != len(heat_ids) or set(heat_ids) != set(current):
        raise HeatError("A nova ordem de baterias está incompleta. Atualize a página.")
    for index, heat_id in enumerate(heat_ids, start=1):
        connection.execute(
            "UPDATE heats SET sequence = ? WHERE id = ? AND event_id = ?",
            (index, heat_id, event_id),
        )


def _heat_entries(connection: sqlite3.Connection, heat_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT he.athlete_id, a.bib, a.name
        FROM heat_entries he
        JOIN athletes a ON a.id = he.athlete_id
        WHERE he.heat_id = ?
        ORDER BY he.position, he.id
        """,
        (heat_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _replace_entries(
    connection: sqlite3.Connection,
    heat_id: int,
    athlete_ids: list[int],
) -> None:
    connection.execute("DELETE FROM heat_entries WHERE heat_id = ?", (heat_id,))
    for position, athlete_id in enumerate(athlete_ids, start=1):
        connection.execute(
            "INSERT INTO heat_entries (heat_id, athlete_id, position) VALUES (?, ?, ?)",
            (heat_id, athlete_id, position),
        )


def sort_heat(
    connection: sqlite3.Connection,
    event_id: int,
    heat_id: int,
    criterion: str,
) -> None:
    heat = connection.execute(
        "SELECT * FROM heats WHERE id = ? AND event_id = ?", (heat_id, event_id)
    ).fetchone()
    if heat is None:
        raise HeatError("Bateria não encontrada.")
    if criterion not in ("bib", "alpha", "random"):
        raise HeatError("Critério de ordenação inválido.")
    athletes = _heat_entries(connection, heat_id)
    if criterion == "alpha":
        athletes.sort(key=lambda row: (sort_name(row["name"]), row["bib"]))
    elif criterion == "random":
        random.SystemRandom().shuffle(athletes)
    else:
        athletes.sort(key=lambda row: row["bib"])
    _replace_entries(connection, heat_id, [row["athlete_id"] for row in athletes])


def move_athlete(
    connection: sqlite3.Connection,
    event: dict[str, Any],
    *,
    athlete_id: int,
    target_heat_id: int | None,
    before_athlete_id: int | None = None,
) -> None:
    athlete_row = connection.execute(
        """
        SELECT a.*, rg.sex, rg.category_id,
               he.heat_id AS source_heat_id
        FROM athletes a
        JOIN race_groups rg ON rg.id = a.race_group_id
        LEFT JOIN heat_entries he ON he.athlete_id = a.id
        WHERE a.id = ? AND a.event_id = ?
        """,
        (athlete_id, event["id"]),
    ).fetchone()
    if athlete_row is None:
        raise HeatError("Atleta não encontrado nesta prova.")
    athlete = dict(athlete_row)
    source_heat_id = athlete["source_heat_id"]

    if target_heat_id is None:
        if source_heat_id is not None:
            connection.execute(
                "DELETE FROM heat_entries WHERE athlete_id = ?", (athlete_id,)
            )
            rows = connection.execute(
                "SELECT id FROM heat_entries WHERE heat_id = ? ORDER BY position, id",
                (source_heat_id,),
            ).fetchall()
            for index, row in enumerate(rows, start=1):
                connection.execute(
                    "UPDATE heat_entries SET position = ? WHERE id = ?",
                    (index, row["id"]),
                )
        return

    target = connection.execute(
        "SELECT * FROM heats WHERE id = ? AND event_id = ?",
        (target_heat_id, event["id"]),
    ).fetchone()
    if target is None:
        raise HeatError("Bateria de destino não encontrada.")
    target = dict(target)
    if target["category_id"] != athlete["category_id"]:
        raise HeatError("A bateria de destino pertence a outra categoria.")
    if target["sex_mode"] != "X" and target["sex_mode"] != athlete["sex"]:
        raise HeatError("A bateria de destino não aceita atletas deste sexo.")

    target_list = [
        row["athlete_id"] for row in _heat_entries(connection, target_heat_id)
    ]
    source_list: list[int] | None = None
    if source_heat_id != target_heat_id and len(target_list) + 1 > int(
        event["heat_limit"]
    ):
        raise HeatError(
            f"A bateria de destino está cheia (limite de {event['heat_limit']} atletas)."
        )
    if source_heat_id is not None and source_heat_id != target_heat_id:
        source_list = [
            row["athlete_id"] for row in _heat_entries(connection, source_heat_id)
        ]

    target_without = [item for item in target_list if item != athlete_id]
    if before_athlete_id is not None and before_athlete_id != athlete_id:
        try:
            insertion = target_without.index(before_athlete_id)
        except ValueError:
            raise HeatError("A posição de destino não está mais disponível.")
    elif before_athlete_id == athlete_id:
        return
    else:
        insertion = len(target_without)
    target_without.insert(insertion, athlete_id)

    if source_list is not None:
        source_without = [item for item in source_list if item != athlete_id]
        connection.execute(
            "DELETE FROM heat_entries WHERE heat_id IN (?, ?)",
            (source_heat_id, target_heat_id),
        )
        _replace_entries(connection, target_heat_id, target_without)
        _replace_entries(connection, source_heat_id, source_without)
    else:
        _replace_entries(connection, target_heat_id, target_without)


def reorder_heat_athletes(
    connection: sqlite3.Connection,
    event_id: int,
    heat_id: int,
    athlete_ids: list[int],
) -> None:
    heat = connection.execute(
        "SELECT id FROM heats WHERE id = ? AND event_id = ?", (heat_id, event_id)
    ).fetchone()
    if heat is None:
        raise HeatError("Bateria não encontrada.")
    current = [row["athlete_id"] for row in _heat_entries(connection, heat_id)]
    if len(set(athlete_ids)) != len(athlete_ids) or set(athlete_ids) != set(current):
        raise HeatError("A ordem dos atletas está incompleta. Atualize a página.")
    _replace_entries(connection, heat_id, athlete_ids)
