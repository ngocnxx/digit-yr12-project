-- NCEA Review Navigator — database schema (SQLite)
-- Data model: users -> subjects -> topics -> reviews


PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL,
    email           TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash   TEXT    NOT NULL,
    year_level      INTEGER NOT NULL DEFAULT 12,
    onboarding_done INTEGER NOT NULL DEFAULT 0,
    daily_cap       INTEGER NOT NULL DEFAULT 5,  -- max review suggestions/day (3-8, Sutherland-Paradox loop)
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS subjects (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT    NOT NULL,
    emoji      TEXT,
    colour     TEXT,
    internal_mode INTEGER NOT NULL DEFAULT 0,  -- 1 = paused during an internal assessment
    archived   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS topics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id      INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    name            TEXT    NOT NULL,
    emoji           TEXT,
    standard_number TEXT,                       -- optional, e.g. 'AS 91156'
    review_count    INTEGER NOT NULL DEFAULT 0, -- set by the scheduling engine (slice 2)
    next_due        TEXT,                       -- ISO date or NULL (NULL = NEW / never reviewed)
    archived        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS reviews (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id      INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    reviewed_date TEXT    NOT NULL,             -- ISO date
    confidence    TEXT,                         -- 'shaky' | 'okay' | 'solid' | 'internal_assessment' | NULL
    interval      INTEGER,                      -- days until next_due at log time
    next_due      TEXT,                         -- ISO date
    evidence      TEXT,                         -- optional accountability note (never affects the schedule)
    reflection    TEXT,                         -- optional accountability note (never affects the schedule)
    attachment      TEXT,                       -- optional photo saved as a data URL
    attachment_name TEXT,                       -- the original file name, for the label
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_subjects_user  ON subjects(user_id, archived);
CREATE INDEX IF NOT EXISTS idx_topics_subject ON topics(subject_id, archived);
CREATE INDEX IF NOT EXISTS idx_reviews_topic  ON reviews(topic_id);
