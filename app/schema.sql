PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    event_date TEXT,
    location TEXT NOT NULL DEFAULT '',
    heat_limit INTEGER NOT NULL DEFAULT 10 CHECK (heat_limit BETWEEN 1 AND 1000),
    schedule_enabled INTEGER NOT NULL DEFAULT 0 CHECK (schedule_enabled IN (0, 1)),
    schedule_start TEXT NOT NULL DEFAULT '08:00',
    athlete_interval_seconds INTEGER NOT NULL DEFAULT 60 CHECK (athlete_interval_seconds BETWEEN 0 AND 86400),
    heat_interval_seconds INTEGER NOT NULL DEFAULT 300 CHECK (heat_interval_seconds BETWEEN 0 AND 86400),
    classification_tiebreak TEXT NOT NULL DEFAULT 'bib'
        CHECK (classification_tiebreak IN ('bib', 'name', 'registration', 'real')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS award_settings (
    event_id INTEGER PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
    preset TEXT NOT NULL DEFAULT 'classic'
        CHECK (preset IN ('classic', 'light', 'dark', 'custom')),
    accent_color TEXT,
    background_color TEXT,
    text_color TEXT,
    show_logo INTEGER NOT NULL DEFAULT 1 CHECK (show_logo IN (0, 1)),
    animations_enabled INTEGER NOT NULL DEFAULT 1
        CHECK (animations_enabled IN (0, 1)),
    layout TEXT NOT NULL DEFAULT 'classic'
        CHECK (layout IN ('classic', 'modern', 'highlight')),
    banner_filename TEXT,
    background_filename TEXT,
    background_opacity INTEGER NOT NULL DEFAULT 35
        CHECK (background_opacity BETWEEN 0 AND 100),
    background_dim INTEGER NOT NULL DEFAULT 55
        CHECK (background_dim BETWEEN 0 AND 100),
    font_filename TEXT,
    font_format TEXT,
    opening_title TEXT NOT NULL DEFAULT 'Premiação',
    opening_text TEXT NOT NULL DEFAULT '',
    closing_title TEXT NOT NULL DEFAULT 'Obrigado!',
    closing_text TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    min_age INTEGER CHECK (min_age IS NULL OR min_age BETWEEN 0 AND 120),
    max_age INTEGER CHECK (max_age IS NULL OR max_age BETWEEN 0 AND 120),
    classification_mode TEXT NOT NULL DEFAULT 'separate'
        CHECK (classification_mode IN ('separate', 'mixed')),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (min_age IS NULL OR max_age IS NULL OR min_age <= max_age),
    UNIQUE (event_id, name COLLATE NOCASE),
    UNIQUE (id, event_id)
);

CREATE TABLE IF NOT EXISTS award_slide_texts (
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL,
    group_sex TEXT NOT NULL CHECK (group_sex IN ('M', 'F', 'X')),
    title TEXT NOT NULL DEFAULT '',
    call_text TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (event_id, category_id, group_sex),
    FOREIGN KEY (category_id, event_id) REFERENCES categories(id, event_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (event_id, name COLLATE NOCASE),
    UNIQUE (id, event_id)
);

CREATE TABLE IF NOT EXISTS race_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL,
    sex TEXT NOT NULL CHECK (sex IN ('M', 'F')),
    FOREIGN KEY (category_id, event_id) REFERENCES categories(id, event_id) ON DELETE CASCADE,
    UNIQUE (category_id, sex),
    UNIQUE (id, event_id)
);

CREATE TABLE IF NOT EXISTS athletes (
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
);

CREATE TABLE IF NOT EXISTS heats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL,
    sex_mode TEXT NOT NULL CHECK (sex_mode IN ('M', 'F', 'X')),
    label TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    FOREIGN KEY (category_id, event_id) REFERENCES categories(id, event_id) ON DELETE RESTRICT,
    UNIQUE (category_id, sex_mode, label)
);

CREATE TABLE IF NOT EXISTS heat_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    heat_id INTEGER NOT NULL REFERENCES heats(id) ON DELETE CASCADE,
    athlete_id INTEGER NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    position INTEGER NOT NULL CHECK (position > 0),
    UNIQUE (heat_id, athlete_id),
    UNIQUE (athlete_id),
    UNIQUE (heat_id, position)
);

CREATE TABLE IF NOT EXISTS import_batches (
    id TEXT PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS import_rows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    raw_json TEXT NOT NULL,
    normalized_json TEXT NOT NULL,
    errors_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL CHECK (status IN ('VALID', 'WARNING', 'ERROR')),
    UNIQUE (batch_id, row_number)
);

CREATE TABLE IF NOT EXISTS results (
    athlete_id INTEGER PRIMARY KEY REFERENCES athletes(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'OK' CHECK (status IN ('OK', 'DNF', 'DSQ', 'DNS')),
    final_time_cs INTEGER CHECK (final_time_cs IS NULL OR final_time_cs >= 0),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (
        (status = 'OK' AND final_time_cs IS NOT NULL)
        OR (status <> 'OK' AND final_time_cs IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_categories_event ON categories(event_id, sort_order, name);
CREATE INDEX IF NOT EXISTS idx_teams_event ON teams(event_id, name);
CREATE INDEX IF NOT EXISTS idx_race_groups_event ON race_groups(event_id);
CREATE INDEX IF NOT EXISTS idx_athletes_event ON athletes(event_id, bib);
CREATE INDEX IF NOT EXISTS idx_athletes_group ON athletes(race_group_id);
CREATE INDEX IF NOT EXISTS idx_athletes_team ON athletes(event_id, team_id);
CREATE INDEX IF NOT EXISTS idx_heats_event_sequence ON heats(event_id, sequence);
CREATE INDEX IF NOT EXISTS idx_heat_entries_heat ON heat_entries(heat_id, position);
CREATE INDEX IF NOT EXISTS idx_import_rows_batch ON import_rows(batch_id, row_number);
