from __future__ import annotations

import sqlite3

import pytest

from app.database import connect, init_db

LEGACY_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    event_date TEXT,
    location TEXT NOT NULL DEFAULT '',
    heat_limit INTEGER NOT NULL DEFAULT 10,
    schedule_enabled INTEGER NOT NULL DEFAULT 0,
    schedule_start TEXT NOT NULL DEFAULT '08:00',
    athlete_interval_seconds INTEGER NOT NULL DEFAULT 60,
    heat_interval_seconds INTEGER NOT NULL DEFAULT 300,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    min_age INTEGER,
    max_age INTEGER,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (event_id, name COLLATE NOCASE),
    UNIQUE (id, event_id)
);

CREATE TABLE race_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL,
    sex TEXT NOT NULL,
    FOREIGN KEY (category_id, event_id) REFERENCES categories(id, event_id) ON DELETE CASCADE,
    UNIQUE (category_id, sex),
    UNIQUE (id, event_id)
);

CREATE TABLE athletes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    race_group_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    age INTEGER NOT NULL,
    team TEXT NOT NULL DEFAULT '',
    bib INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (race_group_id, event_id) REFERENCES race_groups(id, event_id) ON DELETE RESTRICT,
    UNIQUE (event_id, bib)
);

CREATE TABLE heats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL,
    sex_mode TEXT NOT NULL,
    label TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (category_id, event_id) REFERENCES categories(id, event_id) ON DELETE RESTRICT,
    UNIQUE (category_id, sex_mode, label)
);

CREATE TABLE heat_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    heat_id INTEGER NOT NULL REFERENCES heats(id) ON DELETE CASCADE,
    athlete_id INTEGER NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    UNIQUE (heat_id, athlete_id),
    UNIQUE (athlete_id),
    UNIQUE (heat_id, position)
);

CREATE TABLE results (
    athlete_id INTEGER PRIMARY KEY REFERENCES athletes(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'OK',
    final_time_cs INTEGER,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX idx_athletes_event ON athletes(event_id, bib);
CREATE INDEX idx_athletes_group ON athletes(race_group_id);

PRAGMA user_version = 1;
"""


def build_legacy_database(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        connection.executescript(LEGACY_SCHEMA)
        connection.executescript(
            """
            INSERT INTO events (id, name, event_date, location, heat_limit,
                                schedule_enabled, schedule_start,
                                athlete_interval_seconds, heat_interval_seconds)
            VALUES
                (1, 'Prova Um', '2026-08-15', 'Cidade', 4, 1, '07:00', 60, 300),
                (2, 'Prova Dois', '2026-09-20', 'Outra', 10, 0, '08:00', 45, 240);

            INSERT INTO categories (id, event_id, name, min_age, max_age, sort_order)
            VALUES (1, 1, 'Adulto', 30, 39, 10),
                   (2, 2, 'Geral', NULL, NULL, 10);

            INSERT INTO race_groups (id, event_id, category_id, sex)
            VALUES (1, 1, 1, 'M'),
                   (2, 1, 1, 'F'),
                   (3, 2, 2, 'M'),
                   (4, 2, 2, 'F');

            INSERT INTO athletes
                (id, event_id, race_group_id, name, age, team, bib,
                 created_at, updated_at)
            VALUES
                (1, 1, 2, 'Alice', 30, ' Cardume ', 101,
                 '2026-01-01T10:00:00.000Z', '2026-01-02T10:00:00.000Z'),
                (2, 1, 1, 'Bruno', 31, 'CARDUME', 102,
                 '2026-01-01T11:00:00.000Z', '2026-01-02T11:00:00.000Z'),
                (3, 1, 2, 'Carla', 32, '   ', 103,
                 '2026-01-01T12:00:00.000Z', '2026-01-02T12:00:00.000Z'),
                (4, 1, 1, 'Diego', 33, 'Outra  Equipe', 104,
                 '2026-01-01T13:00:00.000Z', '2026-01-02T13:00:00.000Z'),
                (5, 2, 3, 'Eva', 34, 'cardume', 201,
                 '2026-01-01T14:00:00.000Z', '2026-01-02T14:00:00.000Z'),
                (6, 1, 2, 'Fábio', 35, 'Équipe Azul', 105,
                 '2026-01-01T15:00:00.000Z', '2026-01-02T15:00:00.000Z'),
                (7, 1, 1, 'Gabi', 36, 'équipe azul', 106,
                 '2026-01-01T16:00:00.000Z', '2026-01-02T16:00:00.000Z');

            INSERT INTO heats (id, event_id, category_id, sex_mode, label, sequence)
            VALUES (10, 1, 1, 'F', 'A', 1);

            INSERT INTO heat_entries (id, heat_id, athlete_id, position)
            VALUES (20, 10, 1, 1),
                   (21, 10, 3, 2);

            INSERT INTO results (athlete_id, status, final_time_cs)
            VALUES (1, 'OK', 123456),
                   (3, 'DNF', NULL);

            UPDATE sqlite_sequence SET seq = 50 WHERE name = 'athletes';
            """
        )
        connection.commit()
    finally:
        connection.close()


def test_migration_v1_to_v2_preserves_data_and_creates_backup(tmp_path):
    database = tmp_path / "legacy.db"
    backup_dir = tmp_path / "backups"
    build_legacy_database(database)

    source = sqlite3.connect(database)
    source.row_factory = sqlite3.Row
    athletes_before = [dict(row) for row in source.execute("SELECT * FROM athletes ORDER BY id")]
    heats_before = [dict(row) for row in source.execute("SELECT * FROM heats ORDER BY id")]
    entries_before = [
        dict(row) for row in source.execute("SELECT * FROM heat_entries ORDER BY id")
    ]
    results_before = [dict(row) for row in source.execute("SELECT * FROM results ORDER BY athlete_id")]
    source.close()

    init_db(database, backup_dir=backup_dir)

    backups = sorted(backup_dir.glob("triscore-pre-v2-*.db"))
    assert len(backups) == 1
    backup = sqlite3.connect(backups[0])
    try:
        assert backup.execute("PRAGMA user_version").fetchone()[0] == 1
        columns = {row[1] for row in backup.execute("PRAGMA table_info(athletes)")}
        assert "team" in columns and "team_id" not in columns
        assert backup.execute("SELECT COUNT(*) FROM athletes").fetchone()[0] == 7
    finally:
        backup.close()
    v3_backups = sorted(backup_dir.glob("triscore-pre-v3-*.db"))
    assert len(v3_backups) == 1
    backup = sqlite3.connect(v3_backups[0])
    try:
        assert backup.execute("PRAGMA user_version").fetchone()[0] == 2
        event_columns = {
            row[1] for row in backup.execute("PRAGMA table_info(events)")
        }
        assert "classification_tiebreak" not in event_columns
        assert backup.execute("SELECT COUNT(*) FROM athletes").fetchone()[0] == 7
    finally:
        backup.close()
    v4_backups = sorted(backup_dir.glob("triscore-pre-v4-*.db"))
    assert len(v4_backups) == 1
    backup = sqlite3.connect(v4_backups[0])
    try:
        assert backup.execute("PRAGMA user_version").fetchone()[0] == 3
        event_columns = {
            row[1] for row in backup.execute("PRAGMA table_info(events)")
        }
        category_columns = {
            row[1] for row in backup.execute("PRAGMA table_info(categories)")
        }
        assert "classification_tiebreak" in event_columns
        assert "classification_mode" not in category_columns
        assert backup.execute("SELECT COUNT(*) FROM athletes").fetchone()[0] == 7
    finally:
        backup.close()
    v5_backups = sorted(backup_dir.glob("triscore-pre-v5-*.db"))
    assert len(v5_backups) == 1
    backup = sqlite3.connect(v5_backups[0])
    try:
        assert backup.execute("PRAGMA user_version").fetchone()[0] == 4
        assert backup.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'award_settings'"
        ).fetchone() is None
        assert backup.execute("SELECT COUNT(*) FROM athletes").fetchone()[0] == 7
    finally:
        backup.close()
    v6_backups = sorted(backup_dir.glob("triscore-pre-v6-*.db"))
    assert len(v6_backups) == 1
    backup = sqlite3.connect(v6_backups[0])
    try:
        assert backup.execute("PRAGMA user_version").fetchone()[0] == 5
        award_columns = {
            row[1] for row in backup.execute("PRAGMA table_info(award_settings)")
        }
        assert "layout" not in award_columns
        assert backup.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'award_slide_texts'"
        ).fetchone() is None
    finally:
        backup.close()

    connection = connect(database)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 6
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(athletes)")}
        assert "team_id" in columns and "team" not in columns
        event_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(events)")
        }
        assert "classification_tiebreak" in event_columns
        category_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(categories)")
        }
        assert "classification_mode" in category_columns
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'award_settings'"
        ).fetchone() is not None
        award_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(award_settings)")
        }
        assert {
            "layout",
            "banner_filename",
            "background_filename",
            "font_filename",
            "opening_title",
            "closing_title",
        } <= award_columns
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'award_slide_texts'"
        ).fetchone() is not None
        event_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'events'"
        ).fetchone()["sql"]
        assert "'real'" in event_sql
        tiebreaks = {
            row[0]
            for row in connection.execute(
                "SELECT classification_tiebreak FROM events"
            ).fetchall()
        }
        assert tiebreaks == {"bib"}
        modes = {
            row[0]
            for row in connection.execute(
                "SELECT classification_mode FROM categories"
            ).fetchall()
        }
        assert modes == {"separate"}

        athletes_after = [
            dict(row)
            for row in connection.execute(
                """
                SELECT a.id, a.event_id, a.race_group_id, a.name, a.age, a.bib,
                       a.created_at, a.updated_at, t.name AS team
                FROM athletes a
                LEFT JOIN teams t ON t.id = a.team_id
                ORDER BY a.id
                """
            )
        ]
        assert [
            (
                row["id"],
                row["event_id"],
                row["race_group_id"],
                row["name"],
                row["age"],
                row["bib"],
                row["created_at"],
                row["updated_at"],
            )
            for row in athletes_after
        ] == [
            (
                row["id"],
                row["event_id"],
                row["race_group_id"],
                row["name"],
                row["age"],
                row["bib"],
                row["created_at"],
                row["updated_at"],
            )
            for row in athletes_before
        ]
        assert athletes_after[0]["team"] == "Cardume"
        assert athletes_after[1]["team"] == "Cardume"
        assert athletes_after[2]["team"] is None
        assert athletes_after[3]["team"] == "Outra Equipe"
        assert athletes_after[4]["team"] == "cardume"
        assert athletes_after[5]["team"] == athletes_after[6]["team"] == "Équipe Azul"

        teams = connection.execute(
            "SELECT t.event_id, t.name, COUNT(a.id) AS total FROM teams t "
            "LEFT JOIN athletes a ON a.team_id = t.id "
            "GROUP BY t.id ORDER BY t.event_id, t.name"
        ).fetchall()
        assert [(row["event_id"], row["name"], row["total"]) for row in teams] == [
            (1, "Cardume", 2),
            (1, "Outra Equipe", 1),
            (1, "Équipe Azul", 2),
            (2, "cardume", 1),
        ]

        heats_after = [
            dict(row) for row in connection.execute("SELECT * FROM heats ORDER BY id")
        ]
        entries_after = [
            dict(row)
            for row in connection.execute("SELECT * FROM heat_entries ORDER BY id")
        ]
        results_after = [
            dict(row)
            for row in connection.execute("SELECT * FROM results ORDER BY athlete_id")
        ]
        assert heats_after == heats_before
        assert entries_after == entries_before
        assert results_after == results_before
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute(
            "SELECT seq FROM sqlite_sequence WHERE name = 'athletes'"
        ).fetchone()[0] == 50
        indexes = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'athletes'"
            )
        }
        assert {"idx_athletes_event", "idx_athletes_group", "idx_athletes_team"} <= indexes
    finally:
        connection.close()

    init_db(database, backup_dir=backup_dir)
    assert len(list(backup_dir.glob("triscore-pre-v2-*.db"))) == 1
    assert len(list(backup_dir.glob("triscore-pre-v3-*.db"))) == 1
    assert len(list(backup_dir.glob("triscore-pre-v4-*.db"))) == 1
    assert len(list(backup_dir.glob("triscore-pre-v5-*.db"))) == 1
    assert len(list(backup_dir.glob("triscore-pre-v6-*.db"))) == 1
    connection = connect(database)
    try:
        assert connection.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 4
        assert connection.execute("SELECT COUNT(*) FROM athletes").fetchone()[0] == 7
    finally:
        connection.close()


def test_new_database_starts_at_v6(tmp_path):
    database = tmp_path / "new.db"
    init_db(database, backup_dir=tmp_path / "backups")
    connection = connect(database)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 6
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(athletes)")}
        assert "team_id" in columns and "team" not in columns
        event_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(events)")
        }
        assert "classification_tiebreak" in event_columns
        category_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(categories)")
        }
        assert "classification_mode" in category_columns
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'teams'"
        ).fetchone() is not None
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'award_settings'"
        ).fetchone() is not None
        award_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(award_settings)")
        }
        assert "layout" in award_columns and "background_filename" in award_columns
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'award_slide_texts'"
        ).fetchone() is not None
    finally:
        connection.close()


def test_future_database_version_is_rejected(tmp_path):
    database = tmp_path / "future.db"
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA user_version = 99")
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(RuntimeError, match="não suportada"):
        init_db(database, backup_dir=tmp_path / "backups")
