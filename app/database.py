from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from collections.abc import Iterator
import re

from app.paths import (
    DEFAULT_BACKUP_DIR,
    DEFAULT_DB_PATH,
    PROJECT_ROOT,
    SCHEMA_PATH,
)

BACKUP_DIR = DEFAULT_BACKUP_DIR
SCHEMA_VERSION = 6
V2_SCHEMA_VERSION = 2
V3_SCHEMA_VERSION = 3
V4_SCHEMA_VERSION = 4
V5_SCHEMA_VERSION = 5

AWARD_SLIDE_TEXTS_TABLE_SQL = """
CREATE TABLE award_slide_texts (
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL,
    group_sex TEXT NOT NULL CHECK (group_sex IN ('M', 'F', 'X')),
    title TEXT NOT NULL DEFAULT '',
    call_text TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (event_id, category_id, group_sex),
    FOREIGN KEY (category_id, event_id) REFERENCES categories(id, event_id) ON DELETE CASCADE
)
"""

AWARD_SETTINGS_TABLE_SQL = """
CREATE TABLE award_settings (
    event_id INTEGER PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
    preset TEXT NOT NULL DEFAULT 'classic'
        CHECK (preset IN ('classic', 'light', 'dark', 'custom')),
    accent_color TEXT,
    background_color TEXT,
    text_color TEXT,
    show_logo INTEGER NOT NULL DEFAULT 1 CHECK (show_logo IN (0, 1)),
    animations_enabled INTEGER NOT NULL DEFAULT 1
        CHECK (animations_enabled IN (0, 1)),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
)
"""

EVENTS_V4_TABLE_SQL = """
CREATE TABLE events_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    event_date TEXT,
    location TEXT NOT NULL DEFAULT '',
    heat_limit INTEGER NOT NULL DEFAULT 10 CHECK (heat_limit BETWEEN 1 AND 1000),
    schedule_enabled INTEGER NOT NULL DEFAULT 0 CHECK (schedule_enabled IN (0, 1)),
    schedule_start TEXT NOT NULL DEFAULT '08:00',
    athlete_interval_seconds INTEGER NOT NULL DEFAULT 60
        CHECK (athlete_interval_seconds BETWEEN 0 AND 86400),
    heat_interval_seconds INTEGER NOT NULL DEFAULT 300
        CHECK (heat_interval_seconds BETWEEN 0 AND 86400),
    classification_tiebreak TEXT NOT NULL DEFAULT 'bib'
        CHECK (classification_tiebreak IN ('bib', 'name', 'registration', 'real')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
)
"""

TEAMS_TABLE_SQL = """
CREATE TABLE teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (event_id, name COLLATE NOCASE),
    UNIQUE (id, event_id)
)
"""

ATHLETES_V2_TABLE_SQL = """
CREATE TABLE athletes_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    race_group_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    age INTEGER NOT NULL CHECK (age BETWEEN 1 AND 120),
    team_id INTEGER,
    bib INTEGER NOT NULL CHECK (bib > 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (race_group_id, event_id) REFERENCES race_groups(id, event_id) ON DELETE RESTRICT,
    FOREIGN KEY (team_id, event_id) REFERENCES teams(id, event_id) ON DELETE RESTRICT,
    UNIQUE (event_id, bib)
)
"""


def resolve_db_path(value: str | Path | None = None) -> Path:
    if value is not None:
        return Path(value).expanduser().resolve()
    configured = os.environ.get("TRISCORE_DB")
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_DB_PATH


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = resolve_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        path, timeout=30, isolation_level=None, check_same_thread=False
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


@contextmanager
def transaction(db_path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    connection = connect(db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()


def ensure_race_groups(connection: sqlite3.Connection, event_id: int | None = None) -> None:
    if event_id is None:
        categories = connection.execute("SELECT id, event_id FROM categories").fetchall()
    else:
        categories = connection.execute(
            "SELECT id, event_id FROM categories WHERE event_id = ?", (event_id,)
        ).fetchall()

    for category in categories:
        for sex in ("M", "F"):
            exists = connection.execute(
                "SELECT 1 FROM race_groups WHERE category_id = ? AND sex = ?",
                (category["id"], sex),
            ).fetchone()
            if exists is None:
                connection.execute(
                    """
                    INSERT INTO race_groups (event_id, category_id, sex)
                    VALUES (?, ?, ?)
                    """,
                    (category["event_id"], category["id"], sex),
                )


def _user_version(connection: sqlite3.Connection) -> int:
    return int(connection.execute("PRAGMA user_version").fetchone()[0])


def _user_tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row["name"] for row in rows}


def _normalize_team_name(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _sequence_value(connection: sqlite3.Connection, table: str) -> int | None:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'"
    ).fetchone()
    if exists is None:
        return None
    row = connection.execute(
        "SELECT seq FROM sqlite_sequence WHERE name = ?", (table,)
    ).fetchone()
    return int(row["seq"]) if row is not None else None


def _set_sequence(connection: sqlite3.Connection, table: str, value: int) -> None:
    row = connection.execute(
        "SELECT seq FROM sqlite_sequence WHERE name = ?", (table,)
    ).fetchone()
    if row is None:
        connection.execute(
            "INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)", (table, value)
        )
    else:
        connection.execute(
            "UPDATE sqlite_sequence SET seq = ? WHERE name = ?", (value, table)
        )


def create_snapshot_backup(
    connection: sqlite3.Connection,
    *,
    prefix: str,
    backup_dir: str | Path | None = None,
) -> Path:
    target_dir = Path(backup_dir) if backup_dir is not None else BACKUP_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = target_dir / f"{prefix}-{timestamp}.db"
    destination = sqlite3.connect(target)
    try:
        connection.backup(destination)
    finally:
        destination.close()
    return target


def create_migration_backup(
    connection: sqlite3.Connection, backup_dir: str | Path | None = None
) -> Path:
    return create_snapshot_backup(
        connection, prefix="triscore-pre-v2", backup_dir=backup_dir
    )


def backup_database(
    db_path: str | Path | None,
    *,
    prefix: str,
    backup_dir: str | Path | None = None,
) -> Path:
    connection = connect(db_path)
    try:
        return create_snapshot_backup(
            connection, prefix=prefix, backup_dir=backup_dir
        )
    finally:
        connection.close()


def migrate_v1_to_v2(
    connection: sqlite3.Connection, backup_dir: str | Path | None = None
) -> Path | None:
    backup_path = create_migration_backup(connection, backup_dir)
    connection.execute("PRAGMA foreign_keys = OFF")
    if int(connection.execute("PRAGMA foreign_keys").fetchone()[0]) != 0:
        raise RuntimeError("Não foi possível desativar as chaves estrangeiras para a migração.")

    try:
        connection.execute("BEGIN IMMEDIATE")
        if _user_version(connection) != 1:
            connection.execute("ROLLBACK")
            return backup_path

        old_sequence = _sequence_value(connection, "athletes")
        athletes = connection.execute(
            """
            SELECT id, event_id, race_group_id, name, age, team, bib,
                   created_at, updated_at
            FROM athletes
            ORDER BY id
            """
        ).fetchall()

        connection.execute(TEAMS_TABLE_SQL)
        team_ids: dict[tuple[int, str], int] = {}
        athlete_team_ids: dict[int, int | None] = {}
        for athlete in athletes:
            name = _normalize_team_name(athlete["team"])
            if not name:
                athlete_team_ids[athlete["id"]] = None
                continue
            key = (int(athlete["event_id"]), name.casefold())
            team_id = team_ids.get(key)
            if team_id is None:
                cursor = connection.execute(
                    "INSERT INTO teams (event_id, name) VALUES (?, ?)",
                    (athlete["event_id"], name),
                )
                team_id = int(cursor.lastrowid)
                team_ids[key] = team_id
            athlete_team_ids[athlete["id"]] = team_id

        connection.execute(ATHLETES_V2_TABLE_SQL)
        for athlete in athletes:
            connection.execute(
                """
                INSERT INTO athletes_new
                    (id, event_id, race_group_id, name, age, team_id, bib,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    athlete["id"],
                    athlete["event_id"],
                    athlete["race_group_id"],
                    athlete["name"],
                    athlete["age"],
                    athlete_team_ids[athlete["id"]],
                    athlete["bib"],
                    athlete["created_at"],
                    athlete["updated_at"],
                ),
            )
        connection.execute("DROP TABLE athletes")
        connection.execute("ALTER TABLE athletes_new RENAME TO athletes")
        connection.execute(
            "CREATE INDEX idx_athletes_event ON athletes(event_id, bib)"
        )
        connection.execute(
            "CREATE INDEX idx_athletes_group ON athletes(race_group_id)"
        )
        connection.execute(
            "CREATE INDEX idx_athletes_team ON athletes(event_id, team_id)"
        )
        connection.execute(
            "CREATE INDEX idx_teams_event ON teams(event_id, name)"
        )

        max_athlete_id = max((int(row["id"]) for row in athletes), default=0)
        _set_sequence(
            connection,
            "athletes",
            max(old_sequence or 0, max_athlete_id),
        )

        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(
                "A migração v1 → v2 encontrou violações de chave estrangeira."
            )
        connection.execute(f"PRAGMA user_version = {V2_SCHEMA_VERSION}")
        connection.execute("COMMIT")
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")
    return backup_path


def migrate_v2_to_v3(
    connection: sqlite3.Connection, backup_dir: str | Path | None = None
) -> Path | None:
    backup_path = create_snapshot_backup(
        connection, prefix="triscore-pre-v3", backup_dir=backup_dir
    )
    try:
        connection.execute("BEGIN IMMEDIATE")
        if _user_version(connection) != V2_SCHEMA_VERSION:
            connection.execute("ROLLBACK")
            return backup_path

        connection.execute(
            """
            ALTER TABLE events
            ADD COLUMN classification_tiebreak TEXT NOT NULL DEFAULT 'bib'
                CHECK (classification_tiebreak IN ('bib', 'name', 'registration'))
            """
        )
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(
                "A migração v2 → v3 encontrou violações de chave estrangeira."
            )
        connection.execute(f"PRAGMA user_version = {V3_SCHEMA_VERSION}")
        connection.execute("COMMIT")
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    return backup_path


def migrate_v3_to_v4(
    connection: sqlite3.Connection, backup_dir: str | Path | None = None
) -> Path | None:
    backup_path = create_snapshot_backup(
        connection, prefix="triscore-pre-v4", backup_dir=backup_dir
    )
    connection.execute("PRAGMA foreign_keys = OFF")
    if int(connection.execute("PRAGMA foreign_keys").fetchone()[0]) != 0:
        raise RuntimeError("Não foi possível desativar as chaves estrangeiras para a migração.")

    try:
        connection.execute("BEGIN IMMEDIATE")
        if _user_version(connection) != V3_SCHEMA_VERSION:
            connection.execute("ROLLBACK")
            return backup_path

        old_sequence = _sequence_value(connection, "events")
        events = connection.execute("SELECT * FROM events ORDER BY id").fetchall()
        connection.execute(EVENTS_V4_TABLE_SQL)
        for event in events:
            connection.execute(
                """
                INSERT INTO events_new
                    (id, name, event_date, location, heat_limit, schedule_enabled,
                     schedule_start, athlete_interval_seconds,
                     heat_interval_seconds, classification_tiebreak,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["id"],
                    event["name"],
                    event["event_date"],
                    event["location"],
                    event["heat_limit"],
                    event["schedule_enabled"],
                    event["schedule_start"],
                    event["athlete_interval_seconds"],
                    event["heat_interval_seconds"],
                    event["classification_tiebreak"],
                    event["created_at"],
                    event["updated_at"],
                ),
            )
        connection.execute("DROP TABLE events")
        connection.execute("ALTER TABLE events_new RENAME TO events")
        max_event_id = max((int(row["id"]) for row in events), default=0)
        _set_sequence(connection, "events", max(old_sequence or 0, max_event_id))

        connection.execute(
            """
            ALTER TABLE categories
            ADD COLUMN classification_mode TEXT NOT NULL DEFAULT 'separate'
                CHECK (classification_mode IN ('separate', 'mixed'))
            """
        )

        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(
                "A migração v3 → v4 encontrou violações de chave estrangeira."
            )
        connection.execute(f"PRAGMA user_version = {V4_SCHEMA_VERSION}")
        connection.execute("COMMIT")
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")
    return backup_path


def migrate_v4_to_v5(
    connection: sqlite3.Connection, backup_dir: str | Path | None = None
) -> Path | None:
    backup_path = create_snapshot_backup(
        connection, prefix="triscore-pre-v5", backup_dir=backup_dir
    )
    try:
        connection.execute("BEGIN IMMEDIATE")
        if _user_version(connection) != V4_SCHEMA_VERSION:
            connection.execute("ROLLBACK")
            return backup_path

        connection.execute(AWARD_SETTINGS_TABLE_SQL)
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(
                "A migração v4 → v5 encontrou violações de chave estrangeira."
            )
        connection.execute(f"PRAGMA user_version = {V5_SCHEMA_VERSION}")
        connection.execute("COMMIT")
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    return backup_path


def migrate_v5_to_v6(
    connection: sqlite3.Connection, backup_dir: str | Path | None = None
) -> Path | None:
    backup_path = create_snapshot_backup(
        connection, prefix="triscore-pre-v6", backup_dir=backup_dir
    )
    try:
        connection.execute("BEGIN IMMEDIATE")
        if _user_version(connection) != V5_SCHEMA_VERSION:
            connection.execute("ROLLBACK")
            return backup_path

        connection.execute(
            """
            ALTER TABLE award_settings
            ADD COLUMN layout TEXT NOT NULL DEFAULT 'classic'
                CHECK (layout IN ('classic', 'modern', 'highlight'))
            """
        )
        connection.execute(
            "ALTER TABLE award_settings ADD COLUMN banner_filename TEXT"
        )
        connection.execute(
            "ALTER TABLE award_settings ADD COLUMN background_filename TEXT"
        )
        connection.execute(
            """
            ALTER TABLE award_settings
            ADD COLUMN background_opacity INTEGER NOT NULL DEFAULT 35
                CHECK (background_opacity BETWEEN 0 AND 100)
            """
        )
        connection.execute(
            """
            ALTER TABLE award_settings
            ADD COLUMN background_dim INTEGER NOT NULL DEFAULT 55
                CHECK (background_dim BETWEEN 0 AND 100)
            """
        )
        connection.execute(
            "ALTER TABLE award_settings ADD COLUMN font_filename TEXT"
        )
        connection.execute(
            "ALTER TABLE award_settings ADD COLUMN font_format TEXT"
        )
        connection.execute(
            "ALTER TABLE award_settings ADD COLUMN opening_title TEXT NOT NULL DEFAULT 'Premiação'"
        )
        connection.execute(
            "ALTER TABLE award_settings ADD COLUMN opening_text TEXT NOT NULL DEFAULT ''"
        )
        connection.execute(
            "ALTER TABLE award_settings ADD COLUMN closing_title TEXT NOT NULL DEFAULT 'Obrigado!'"
        )
        connection.execute(
            "ALTER TABLE award_settings ADD COLUMN closing_text TEXT NOT NULL DEFAULT ''"
        )
        connection.execute(AWARD_SLIDE_TEXTS_TABLE_SQL)
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(
                "A migração v5 → v6 encontrou violações de chave estrangeira."
            )
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.execute("COMMIT")
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    return backup_path


def init_db(
    db_path: str | Path | None = None,
    *,
    backup_dir: str | Path | None = None,
) -> Path:
    path = resolve_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    target_backup_dir = Path(backup_dir) if backup_dir is not None else BACKUP_DIR
    target_backup_dir.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    connection = connect(path)
    try:
        version = _user_version(connection)
        if version == 0:
            if _user_tables(connection):
                raise RuntimeError(
                    "Banco não versionado com tabelas existentes. "
                    "Migração automática não disponível para este arquivo."
                )
            connection.executescript(schema)
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        else:
            if version == 1:
                migrate_v1_to_v2(connection, target_backup_dir)
                version = _user_version(connection)
            if version == V2_SCHEMA_VERSION:
                migrate_v2_to_v3(connection, target_backup_dir)
                version = _user_version(connection)
            if version == V3_SCHEMA_VERSION:
                migrate_v3_to_v4(connection, target_backup_dir)
                version = _user_version(connection)
            if version == V4_SCHEMA_VERSION:
                migrate_v4_to_v5(connection, target_backup_dir)
                version = _user_version(connection)
            if version == V5_SCHEMA_VERSION:
                migrate_v5_to_v6(connection, target_backup_dir)
                version = _user_version(connection)
            if version != SCHEMA_VERSION:
                raise RuntimeError(
                    f"Versão de banco não suportada: {version}. "
                    f"Esta aplicação usa a versão {SCHEMA_VERSION}."
                )
        ensure_race_groups(connection)
    finally:
        connection.close()
    return path
