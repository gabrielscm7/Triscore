from __future__ import annotations

import sqlite3
from typing import Any

from app.database import ensure_race_groups

CATEGORY_CLASSIFICATION_MODES = {
    "separate": "Pódios separados (Masculino e Feminino)",
    "mixed": "Pódio único misto",
}


def validate_classification_mode(value: str | None) -> str:
    mode = (value or "separate").strip()
    if mode not in CATEGORY_CLASSIFICATION_MODES:
        raise ValueError("Modo de classificação da categoria inválido.")
    return mode


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def get_event(connection: sqlite3.Connection, event_id: int) -> dict[str, Any] | None:
    row = connection.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    return row_to_dict(row)


def list_events(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT e.*,
               (SELECT COUNT(*) FROM athletes a WHERE a.event_id = e.id) AS athlete_count,
               (SELECT COUNT(*) FROM categories c WHERE c.event_id = e.id) AS category_count,
               (SELECT COUNT(*) FROM heats h WHERE h.event_id = e.id) AS heat_count
        FROM events e
        ORDER BY COALESCE(e.event_date, '9999-12-31') DESC, e.id DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def create_event(
    connection: sqlite3.Connection,
    *,
    name: str,
    event_date: str | None,
    location: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO events (name, event_date, location)
        VALUES (?, ?, ?)
        """,
        (name, event_date, location),
    )
    return int(cursor.lastrowid)


def update_event(
    connection: sqlite3.Connection,
    event_id: int,
    *,
    name: str,
    event_date: str | None,
    location: str,
    heat_limit: int,
    schedule_enabled: bool,
    schedule_start: str,
    athlete_interval_seconds: int,
    heat_interval_seconds: int,
) -> None:
    connection.execute(
        """
        UPDATE events
        SET name = ?,
            event_date = ?,
            location = ?,
            heat_limit = ?,
            schedule_enabled = ?,
            schedule_start = ?,
            athlete_interval_seconds = ?,
            heat_interval_seconds = ?,
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ?
        """,
        (
            name,
            event_date,
            location,
            heat_limit,
            1 if schedule_enabled else 0,
            schedule_start,
            athlete_interval_seconds,
            heat_interval_seconds,
            event_id,
        ),
    )


def list_categories(connection: sqlite3.Connection, event_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT c.*,
               COUNT(a.id) AS athlete_count,
               COUNT(CASE WHEN rg.sex = 'M' THEN a.id END) AS male_count,
               COUNT(CASE WHEN rg.sex = 'F' THEN a.id END) AS female_count
        FROM categories c
        LEFT JOIN race_groups rg ON rg.category_id = c.id
        LEFT JOIN athletes a ON a.race_group_id = rg.id
        WHERE c.event_id = ?
        GROUP BY c.id
        ORDER BY c.sort_order, c.name COLLATE NOCASE
        """,
        (event_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_category(
    connection: sqlite3.Connection, event_id: int, category_id: int
) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM categories WHERE id = ? AND event_id = ?",
        (category_id, event_id),
    ).fetchone()
    return row_to_dict(row)


def create_category(
    connection: sqlite3.Connection,
    *,
    event_id: int,
    name: str,
    min_age: int | None,
    max_age: int | None,
    classification_mode: str = "separate",
) -> int:
    mode = validate_classification_mode(classification_mode)
    row = connection.execute(
        "SELECT COALESCE(MAX(sort_order), 0) + 10 AS next_order FROM categories WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    cursor = connection.execute(
        """
        INSERT INTO categories
            (event_id, name, min_age, max_age, classification_mode, sort_order)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (event_id, name, min_age, max_age, mode, row["next_order"]),
    )
    ensure_race_groups(connection, event_id)
    return int(cursor.lastrowid)


def update_category(
    connection: sqlite3.Connection,
    *,
    event_id: int,
    category_id: int,
    name: str,
    min_age: int | None,
    max_age: int | None,
    classification_mode: str = "separate",
) -> None:
    mode = validate_classification_mode(classification_mode)
    connection.execute(
        """
        UPDATE categories
        SET name = ?, min_age = ?, max_age = ?, classification_mode = ?
        WHERE id = ? AND event_id = ?
        """,
        (name, min_age, max_age, mode, category_id, event_id),
    )


def delete_category(
    connection: sqlite3.Connection, event_id: int, category_id: int
) -> tuple[bool, str | None]:
    category = get_category(connection, event_id, category_id)
    if category is None:
        return False, "Categoria não encontrada."
    athlete_count = connection.execute(
        "SELECT COUNT(*) AS total FROM athletes WHERE race_group_id IN "
        "(SELECT id FROM race_groups WHERE category_id = ?)",
        (category_id,),
    ).fetchone()["total"]
    if athlete_count:
        return False, "A categoria possui atletas e não pode ser excluída."
    heat_count = connection.execute(
        "SELECT COUNT(*) AS total FROM heats WHERE category_id = ?", (category_id,)
    ).fetchone()["total"]
    if heat_count:
        return False, "A categoria possui baterias. Exclua as baterias primeiro."
    connection.execute(
        "DELETE FROM categories WHERE id = ? AND event_id = ?", (category_id, event_id)
    )
    return True, None


def event_stats(connection: sqlite3.Connection, event_id: int) -> dict[str, int]:
    row = connection.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM athletes WHERE event_id = ?) AS athletes,
            (SELECT COUNT(*) FROM categories WHERE event_id = ?) AS categories,
            (SELECT COUNT(*) FROM heats WHERE event_id = ?) AS heats
        """,
        (event_id, event_id, event_id),
    ).fetchone()
    return dict(row)
