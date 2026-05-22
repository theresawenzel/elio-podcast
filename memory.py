"""
SQLite-backed memory for the Elio podcast agent.

Stores:
- episodes: one row per delivered episode
- topic_keywords: extracted keywords per episode (for fast "have we covered X" lookups)
- sources: source attribution per episode (for analytics / spotting source patterns)

Replaces pillar_history.py from Phase 4 — that JSON file becomes deprecated
but stays around for one migration cycle (we'll delete it in Step 4).

Design notes:
- All public functions accept an optional `db_path` for testability.
- All writes are atomic (single transaction, commit on success).
- All datetime values stored as ISO strings for portability.
- Schema migrations handled by IF NOT EXISTS on table creation.
"""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

DB_PATH = Path("episodes.db")

# ───── Schema ─────

SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT NOT NULL,                    -- YYYY-MM-DD
    pillar       TEXT NOT NULL,
    topic_summary TEXT NOT NULL,
    transcript   TEXT,                              -- full ALEX:/LAUREN: script
    audio_url    TEXT,                              -- R2 public URL
    word_count   INTEGER,
    created_at   TEXT NOT NULL                      -- ISO datetime
);

CREATE INDEX IF NOT EXISTS idx_episodes_date ON episodes(date);
CREATE INDEX IF NOT EXISTS idx_episodes_pillar ON episodes(pillar);

CREATE TABLE IF NOT EXISTS topic_keywords (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id  INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    keyword     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_topic_keywords_keyword ON topic_keywords(keyword);
CREATE INDEX IF NOT EXISTS idx_topic_keywords_episode ON topic_keywords(episode_id);

CREATE TABLE IF NOT EXISTS sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id  INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    claim       TEXT,
    source_name TEXT,
    source_url  TEXT,
    source_type TEXT,
    recency     TEXT
);

CREATE INDEX IF NOT EXISTS idx_sources_episode ON sources(episode_id);
"""


# ───── Connection helper ─────

@contextmanager
def _connect(db_path: Path = DB_PATH):
    """Context-managed SQLite connection with foreign keys + row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    """Idempotently creates tables and indexes."""
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


# ───── Public API: write ─────

def save_episode(
    pillar: str,
    topic_summary: str,
    transcript: str,
    audio_url: str = "",
    sources: list | None = None,
    keywords: list[str] | None = None,
    word_count: int = 0,
    on_date: date | None = None,
    db_path: Path = DB_PATH,
) -> int:
    """
    Saves a fully-delivered episode plus its sources and keywords.
    
    Args:
        sources: list of search.Finding objects (or dicts with same shape)
        keywords: list of strings — short topic markers like "separation_anxiety", 
                  "object_permanence", "code_switching"
    
    Returns: the new episode's row id.
    """
    init_db(db_path)
    on_date = on_date or date.today()
    sources = sources or []
    keywords = keywords or []
    
    with _connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO episodes
               (date, pillar, topic_summary, transcript, audio_url, word_count, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                on_date.isoformat(),
                pillar,
                topic_summary,
                transcript,
                audio_url,
                word_count,
                datetime.now().isoformat(),
            ),
        )
        episode_id = cur.lastrowid
        
        for kw in keywords:
            cur.execute(
                "INSERT INTO topic_keywords (episode_id, keyword) VALUES (?, ?)",
                (episode_id, kw.strip().lower()),
            )
        
        for src in sources:
            data = asdict(src) if is_dataclass(src) else dict(src)
            cur.execute(
                """INSERT INTO sources 
                   (episode_id, claim, source_name, source_url, source_type, recency)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    episode_id,
                    data.get("claim", ""),
                    data.get("source_name", ""),
                    data.get("source_url", ""),
                    data.get("source_type", "unknown"),
                    data.get("recency", "unknown"),
                ),
            )
        
        conn.commit()
        return episode_id


# ───── Public API: read ─────

def recent_episodes(days: int = 30, db_path: Path = DB_PATH) -> list[dict]:
    """Returns episodes from the last N days, newest first."""
    init_db(db_path)
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM episodes WHERE date >= ? ORDER BY date DESC, id DESC",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]


def recent_topics(days: int = 30, db_path: Path = DB_PATH) -> list[str]:
    """Returns topic_summary strings from the last N days, newest first.
    
    This is what the research module calls to know what to avoid repeating.
    """
    return [e["topic_summary"] for e in recent_episodes(days, db_path)]


def recent_keywords(days: int = 30, db_path: Path = DB_PATH) -> list[str]:
    """Returns distinct keywords used in the last N days."""
    init_db(db_path)
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT DISTINCT k.keyword 
               FROM topic_keywords k
               JOIN episodes e ON e.id = k.episode_id
               WHERE e.date >= ?
               ORDER BY k.keyword""",
            (cutoff,),
        ).fetchall()
        return [r["keyword"] for r in rows]


def pillar_last_used(pillar_name: str, db_path: Path = DB_PATH) -> date | None:
    """Returns the date a pillar was last used, or None if never."""
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT date FROM episodes WHERE pillar = ? ORDER BY date DESC LIMIT 1",
            (pillar_name,),
        ).fetchone()
        return date.fromisoformat(row["date"]) if row else None


def pillars_used_recently(days: int = 7, db_path: Path = DB_PATH) -> list[str]:
    """Returns distinct pillar names used in the last N days.
    
    This is what pillar rotation will call after Step 4.
    """
    init_db(db_path)
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT pillar FROM episodes WHERE date >= ?",
            (cutoff,),
        ).fetchall()
        return [r["pillar"] for r in rows]


def episode_count(db_path: Path = DB_PATH) -> int:
    """Total episodes ever recorded — useful for show_memory CLI."""
    init_db(db_path)
    with _connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]