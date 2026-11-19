from __future__ import annotations

import sqlite3
from typing import Any

from app.utils import clean_text

MAX_TEAM_NAME_LENGTH = 120


def normalize_team_name(name: str | None) -> str:
    return clean_text(name)


def validate_team_name(name: str | None) -> str:
    value = normalize_team_name(name)
    if not value:
        raise ValueError("Informe o nome da equipe.")
    if len(value) > MAX_TEAM_NAME_LENGTH:
        raise ValueError("O nome da equipe deve ter no máximo 120 caracteres.")
    return value


def _name_key(name: str) -> str:
    return normalize_team_name(name).casefold()


def list_teams(
    connection: sqlite3.Connection, event_id: int
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT t.*, COUNT(a.id) AS athlete_count
        FROM teams t
        LEFT JOIN athletes a ON a.team_id = t.id AND a.event_id = t.event_id
        WHERE t.event_id = ?
        GROUP BY t.id
        ORDER BY t.name COLLATE NOCASE
        """,
        (event_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_team(
    connection: sqlite3.Connection, event_id: int, team_id: int
) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM teams WHERE id = ? AND event_id = ?", (team_id, event_id)
    ).fetchone()
    return dict(row) if row is not None else None


def find_team_by_name(
    connection: sqlite3.Connection, event_id: int, name: str
) -> dict[str, Any] | None:
    key = _name_key(name)
    if not key:
        return None
    for team in list_teams(connection, event_id):
        if _name_key(team["name"]) == key:
            return team
    return None


def _ensure_unique_name(
    connection: sqlite3.Connection,
    event_id: int,
    name: str,
    *,
    exclude_team_id: int | None = None,
) -> None:
    key = _name_key(name)
    for team in list_teams(connection, event_id):
        if team["id"] == exclude_team_id:
            continue
        if _name_key(team["name"]) == key:
            raise ValueError("Já existe uma equipe com esse nome nesta prova.")


def create_team(
    connection: sqlite3.Connection, event_id: int, name: str
) -> int:
    value = validate_team_name(name)
    _ensure_unique_name(connection, event_id, value)
    cursor = connection.execute(
        "INSERT INTO teams (event_id, name) VALUES (?, ?)", (event_id, value)
    )
    return int(cursor.lastrowid)


def update_team(
    connection: sqlite3.Connection, event_id: int, team_id: int, name: str
) -> None:
    team = get_team(connection, event_id, team_id)
    if team is None:
        raise ValueError("Equipe não encontrada.")
    value = validate_team_name(name)
    _ensure_unique_name(connection, event_id, value, exclude_team_id=team_id)
    connection.execute(
        """
        UPDATE teams
        SET name = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ? AND event_id = ?
        """,
        (value, team_id, event_id),
    )


def delete_team(
    connection: sqlite3.Connection, event_id: int, team_id: int
) -> tuple[bool, str | None]:
    team = get_team(connection, event_id, team_id)
    if team is None:
        return False, "Equipe não encontrada."
    athlete_count = connection.execute(
        "SELECT COUNT(*) AS total FROM athletes WHERE team_id = ? AND event_id = ?",
        (team_id, event_id),
    ).fetchone()["total"]
    if athlete_count:
        return False, "A equipe possui atletas e não pode ser excluída."
    connection.execute(
        "DELETE FROM teams WHERE id = ? AND event_id = ?", (team_id, event_id)
    )
    return True, None


def get_or_create_team(
    connection: sqlite3.Connection, event_id: int, name: str
) -> dict[str, Any]:
    value = validate_team_name(name)
    team = find_team_by_name(connection, event_id, value)
    if team is None:
        team_id = create_team(connection, event_id, value)
        team = get_team(connection, event_id, team_id)
    if team is None:
        raise ValueError("Não foi possível criar a equipe.")
    return team
