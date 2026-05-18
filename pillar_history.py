"""
Tracks which pillar ran on which date. Persisted to a local JSON file.

In Phase 5 this gets replaced by SQLite. For now, simple JSON is fine —
the read/write pattern is identical, just changing the storage backend.
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

HISTORY_PATH = Path("pillar_history.json")
ROTATION_WINDOW_DAYS = 7   # No pillar repeats within this many days
                            # (unless all pillars have been used recently)


def _load() -> dict:
    """Loads the history file, returning {} if it doesn't exist yet."""
    if not HISTORY_PATH.exists():
        return {}
    with open(HISTORY_PATH) as f:
        return json.load(f)


def _save(history: dict) -> None:
    """Writes the history file atomically (write-then-rename to prevent corruption)."""
    tmp = HISTORY_PATH.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(history, f, indent=2, sort_keys=True)
    tmp.replace(HISTORY_PATH)


def record_pillar(pillar_name: str, on_date: date | None = None) -> None:
    """Records that a pillar was used on a given date (defaults to today)."""
    on_date = on_date or date.today()
    history = _load()
    history[on_date.isoformat()] = pillar_name
    _save(history)


def recent_pillars(days: int = ROTATION_WINDOW_DAYS) -> list[str]:
    """Returns the list of pillars used in the last N days, oldest first."""
    history = _load()
    cutoff = date.today() - timedelta(days=days)
    used = []
    for date_str, pillar in sorted(history.items()):
        if date.fromisoformat(date_str) >= cutoff:
            used.append(pillar)
    return used


def pick_pillar(all_pillars: list[dict], override: str | None = None) -> dict:
    """
    Picks today's pillar.
    
    Args:
        all_pillars: List of pillar dicts from config.PILLARS
        override: If provided, returns that specific pillar (e.g. user-flagged topic)
    
    Logic:
    - If override is given, use it (allows manual overrides from user notes later).
    - Otherwise, prefer pillars NOT used in the last ROTATION_WINDOW_DAYS days.
    - If all pillars have been used recently, fall back to the least-recently-used.
    - Among eligible pillars, pick randomly (so it doesn't feel mechanical).
    """
    if override:
        match = next((p for p in all_pillars if p["name"] == override), None)
        if match:
            return match
        # If override name doesn't match any pillar, fall through to normal logic
    
    recent = recent_pillars()
    eligible = [p for p in all_pillars if p["name"] not in recent]
    
    if eligible:
        return random.choice(eligible)
    
    # All pillars were used in the rotation window — pick the one used longest ago
    history = _load()
    pillar_last_used = {}
    for date_str, pillar in history.items():
        # Track the MOST RECENT use of each pillar
        if pillar not in pillar_last_used or date_str > pillar_last_used[pillar]:
            pillar_last_used[pillar] = date_str
    
    # Sort by date ascending (oldest first), pick the first one that's in our pillar list
    sorted_by_oldest = sorted(pillar_last_used.items(), key=lambda x: x[1])
    for pillar_name, _ in sorted_by_oldest:
        match = next((p for p in all_pillars if p["name"] == pillar_name), None)
        if match:
            return match
    
    # Defensive fallback: if pillar_history.json has stale pillar names, just pick random
    return random.choice(all_pillars)