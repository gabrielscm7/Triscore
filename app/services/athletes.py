from __future__ import annotations

import sqlite3
from typing import Any

from app.database import ensure_race_groups
from app.utils import age_warning, clean_text, next_bib


def get_athlete(
    connection: sqlite3.Connection, event_id: int, athlete_id: int
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT a.*, t.name AS team, rg.sex, rg.category_id,
               c.name AS category_name, c.min_age, c.max_age,
               h.id AS heat_id, h.label AS heat_label,
               h.sequence AS heat_sequence, h.sex_mode AS heat_sex_mode
        FROM athletes a
        JOIN race_groups rg ON rg.id = a.race_group_id
        JOIN categories c ON c.id = rg.category_id
        LEFT JOIN teams t ON t.id = a.team_id AND t.event_id = a.event_id
        LEFT JOIN heat_entries he ON he.athlete_id = a.id
        LEFT JOIN heats h ON h.id = he.heat_id
        WHERE a.id = ? AND a.event_id = ?
        """,
        (athlete_id, event_id),
    ).fetchone()
    return dict(row) if row is not None else None


def list_athletes(
    connection: sqlite3.Connection,
    event_id: int,
    *,
    query: str = "",
    category_id: int | None = None,
    team_id: int | None = None,
    sex: str | None = None,
) -> list[dict[str, Any]]:
    conditions = ["a.event_id = ?"]
    params: list[Any] = [event_id]
    if query:
        conditions.append(
            "(a.name LIKE ? OR t.name LIKE ? OR CAST(a.bib AS TEXT) LIKE ?)"
        )
        like = f"%{query}%"
        params.extend([like, like, like])
    if category_id is not None:
        conditions.append("rg.category_id = ?")
        params.append(category_id)
    if team_id is not None:
        conditions.append("a.team_id = ?")
        params.append(team_id)
    if sex in ("M", "F"):
        conditions.append("rg.sex = ?")
        params.append(sex)

    rows = connection.execute(
        f"""
        SELECT a.*, t.name AS team, rg.sex, rg.category_id,
               c.name AS category_name, c.min_age, c.max_age,
               h.id AS heat_id, h.label AS heat_label,
               h.sequence AS heat_sequence, h.sex_mode AS heat_sex_mode
        FROM athletes a
        JOIN race_groups rg ON rg.id = a.race_group_id
        JOIN categories c ON c.id = rg.category_id
        LEFT JOIN teams t ON t.id = a.team_id AND t.event_id = a.event_id
        LEFT JOIN heat_entries he ON he.athlete_id = a.id
        LEFT JOIN heats h ON h.id = he.heat_id
        WHERE {' AND '.join(conditions)}
        ORDER BY a.bib
        """,
        params,
    ).fetchall()
    athletes = [dict(row) for row in rows]
    for athlete in athletes:
        athlete["age_warning"] = age_warning(
            athlete["age"], athlete["min_age"], athlete["max_age"]
        )
    return athletes


def group_for(
    connection: sqlite3.Connection,
    event_id: int,
    category_id: int,
    sex: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT rg.*, c.name AS category_name, c.min_age, c.max_age
        FROM race_groups rg
        JOIN categories c ON c.id = rg.category_id
        WHERE rg.event_id = ? AND rg.category_id = ? AND rg.sex = ?
        """,
        (event_id, category_id, sex),
    ).fetchone()
    if row is not None:
        return dict(row)
    ensure_race_groups(connection, event_id)
    row = connection.execute(
        """
        SELECT rg.*, c.name AS category_name, c.min_age, c.max_age
        FROM race_groups rg
        JOIN categories c ON c.id = rg.category_id
        WHERE rg.event_id = ? AND rg.category_id = ? AND rg.sex = ?
        """,
        (event_id, category_id, sex),
    ).fetchone()
    return dict(row) if row is not None else None


def create_athlete(
    connection: sqlite3.Connection,
    *,
    event_id: int,
    category_id: int,
    name: str,
    age: int,
    team_id: int | None,
    sex: str,
    bib: int | None = None,
    race_group_id: int | None = None,
) -> int:
    group = None
    if race_group_id is not None:
        row = connection.execute(
            "SELECT * FROM race_groups WHERE id = ? AND event_id = ?",
            (race_group_id, event_id),
        ).fetchone()
        group = dict(row) if row is not None else None
    if group is None:
        group = group_for(connection, event_id, category_id, sex)
    if group is None:
        raise ValueError("Grupo de prova inválido.")

    resolved_bib = bib if bib is not None else next_bib(connection, event_id)
    cursor = connection.execute(
        """
        INSERT INTO athletes (event_id, race_group_id, name, age, team_id, bib)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (event_id, group["id"], name, age, team_id, resolved_bib),
    )
    return int(cursor.lastrowid)


def renumber_heat(connection: sqlite3.Connection, heat_id: int) -> None:
    rows = connection.execute(
        "SELECT id FROM heat_entries WHERE heat_id = ? ORDER BY position, id", (heat_id,)
    ).fetchall()
    for index, row in enumerate(rows, start=1):
        connection.execute(
            "UPDATE heat_entries SET position = ? WHERE id = ?", (index, row["id"])
        )


def update_athlete(
    connection: sqlite3.Connection,
    *,
    event_id: int,
    athlete_id: int,
    category_id: int,
    name: str,
    age: int,
    team_id: int | None,
    sex: str,
    bib: int | None,
) -> dict[str, Any]:
    current = get_athlete(connection, event_id, athlete_id)
    if current is None:
        raise ValueError("Atleta não encontrado.")
    group = group_for(connection, event_id, category_id, sex)
    if group is None:
        raise ValueError("Grupo de prova inválido.")

    resolved_bib = bib if bib is not None else next_bib(connection, event_id)
    removed_heat = None
    if current["race_group_id"] != group["id"] and current["heat_id"] is not None:
        removed_heat = {
            "id": current["heat_id"],
            "label": current["heat_label"],
            "sequence": current["heat_sequence"],
        }
        connection.execute(
            "DELETE FROM heat_entries WHERE athlete_id = ?", (athlete_id,)
        )
        renumber_heat(connection, current["heat_id"])

    connection.execute(
        """
        UPDATE athletes
        SET race_group_id = ?, name = ?, age = ?, team_id = ?, bib = ?,
            updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        WHERE id = ? AND event_id = ?
        """,
        (group["id"], name, age, team_id, resolved_bib, athlete_id, event_id),
    )
    return {
        "removed_heat": removed_heat,
        "age_warning": age_warning(age, group["min_age"], group["max_age"]),
    }


def delete_athlete(
    connection: sqlite3.Connection, event_id: int, athlete_id: int
) -> dict[str, Any] | None:
    current = get_athlete(connection, event_id, athlete_id)
    if current is None:
        return None
    connection.execute(
        "DELETE FROM athletes WHERE id = ? AND event_id = ?", (athlete_id, event_id)
    )
    if current["heat_id"] is not None:
        renumber_heat(connection, current["heat_id"])
    return current


def validate_fields(
    connection: sqlite3.Connection,
    event_id: int,
    *,
    name: str,
    age: str,
    category_id: str | int | None,
    team_id: str | int | None,
    sex: str,
    bib: str | int | None,
    exclude_athlete_id: int | None = None,
) -> tuple[dict[str, Any] | None, list[str], str | None]:
    errors: list[str] = []
    name = clean_text(name, 120)
    if not name:
        errors.append("Informe o nome do atleta.")

    try:
        age_value = int(str(age).strip())
    except (ValueError, TypeError):
        age_value = None
        errors.append("Informe uma idade válida.")
    else:
        if not 1 <= age_value <= 120:
            errors.append("A idade deve estar entre 1 e 120 anos.")

    sex = clean_text(sex).upper()
    if sex not in ("M", "F"):
        errors.append("Selecione o sexo do atleta.")

    try:
        category_value = int(str(category_id).strip()) if category_id not in (None, "") else None
    except (ValueError, TypeError):
        category_value = None
    if category_value is None:
        errors.append("Selecione a categoria.")
    else:
        category = connection.execute(
            "SELECT * FROM categories WHERE id = ? AND event_id = ?",
            (category_value, event_id),
        ).fetchone()
        if category is None:
            errors.append("Categoria inválida.")

    team_value: int | None = None
    if team_id is not None and str(team_id).strip() != "":
        try:
            team_value = int(str(team_id).strip())
        except (ValueError, TypeError):
            errors.append("Equipe inválida.")
        else:
            team = connection.execute(
                "SELECT id FROM teams WHERE id = ? AND event_id = ?",
                (team_value, event_id),
            ).fetchone()
            if team is None:
                errors.append("Equipe inválida.")

    bib_value: int | None = None
    if bib is None or str(bib).strip() == "":
        bib_value = None
    else:
        try:
            bib_value = int(str(bib).strip())
        except (ValueError, TypeError):
            errors.append("O número de peito deve ser numérico.")
        else:
            if bib_value <= 0:
                errors.append("O número de peito deve ser maior que zero.")
            else:
                duplicate = connection.execute(
                    """
                    SELECT id FROM athletes
                    WHERE event_id = ? AND bib = ? AND id <> ?
                    """,
                    (event_id, bib_value, exclude_athlete_id or -1),
                ).fetchone()
                if duplicate is not None:
                    errors.append(f"O peito {bib_value} já está em uso nesta prova.")

    if errors:
        return None, errors, None
    category = connection.execute(
        "SELECT * FROM categories WHERE id = ? AND event_id = ?",
        (category_value, event_id),
    ).fetchone()
    warning = age_warning(age_value, category["min_age"], category["max_age"])
    return (
        {
            "name": name,
            "age": age_value,
            "category_id": category_value,
            "team_id": team_value,
            "sex": sex,
            "bib": bib_value,
        },
        [],
        warning,
    )
