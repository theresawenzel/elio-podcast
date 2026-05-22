"""
Pillar selection logic.

Reads pillar history from the SQLite memory layer (memory.py) — the JSON file
this module used in Phase 4 is now deprecated. Kept as a module for clean separation
of concerns: `pick_pillar()` is rotation logic, `save_episode()` is persistence.
"""

import random
from memory import pillars_used_recently

ROTATION_WINDOW_DAYS = 7


def pick_pillar(all_pillars: list[dict], override: str | None = None) -> dict:
    """
    Picks today's pillar based on the SQLite memory.
    
    Args:
        all_pillars: List of pillar dicts from config.PILLARS
        override: If provided, returns that specific pillar (e.g. user-flagged topic
                  from a future Google Doc reader)
    
    Logic:
    - If override is given, use it (allows manual overrides from user notes later).
    - Otherwise, prefer pillars NOT used in the last ROTATION_WINDOW_DAYS days.
    - If all pillars have been used recently, fall back to random.
    - Among eligible pillars, pick randomly (so it doesn't feel mechanical).
    """
    if override:
        match = next((p for p in all_pillars if p["name"] == override), None)
        if match:
            return match
    
    recent = pillars_used_recently(days=ROTATION_WINDOW_DAYS)
    eligible = [p for p in all_pillars if p["name"] not in recent]
    
    if eligible:
        return random.choice(eligible)
    
    # All pillars were used recently — pick any (the rotation will naturally re-distribute)
    return random.choice(all_pillars)


# ───── Deprecated functions ─────
# Kept as no-ops so old code paths don't crash during the transition.
# Phase 6+ can remove these entirely.

def record_pillar(pillar_name, on_date=None):
    """DEPRECATED: pillars are now recorded via memory.save_episode()."""
    pass


def recent_pillars(days: int = 7) -> list[str]:
    """Compatibility shim — calls memory.pillars_used_recently() under the hood."""
    return pillars_used_recently(days=days)