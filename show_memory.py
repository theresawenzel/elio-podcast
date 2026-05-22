"""
CLI utility for inspecting the episode memory.

Run examples:
    python show_memory.py                   # Last 30 days, summary view
    python show_memory.py --days 7          # Last week
    python show_memory.py --all             # Everything
    python show_memory.py --keywords        # List all topic keywords
    python show_memory.py --sources         # List sources cited
    python show_memory.py --pillar bilingual_trilingual   # Filter by pillar
"""

import argparse
import sqlite3
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from memory import (
    DB_PATH,
    episode_count,
    recent_episodes,
    recent_keywords,
)


def cmd_summary(args):
    """Show recent episodes in a clean table."""
    if args.all:
        episodes = recent_episodes(days=10000)
    else:
        episodes = recent_episodes(days=args.days)
    
    if args.pillar:
        episodes = [e for e in episodes if e["pillar"] == args.pillar]
    
    print(f"\n📚 Episode Memory ({len(episodes)} episode{'s' if len(episodes) != 1 else ''})")
    print(f"   Total in DB: {episode_count()}\n")
    
    if not episodes:
        print("   (No episodes yet)")
        return
    
    for ep in episodes:
        date_str = ep["date"]
        pillar = ep["pillar"]
        topic = ep["topic_summary"]
        words = ep["word_count"] or 0
        
        # Show the topic on its own line for readability
        print(f"  {date_str} | {pillar:30s} | {words} words")
        print(f"             {topic}")
        print()


def cmd_keywords(args):
    """Show all distinct keywords used in recent episodes."""
    days = 10000 if args.all else args.days
    keywords = recent_keywords(days=days)
    
    print(f"\n🔑 Topic keywords from the last {days} days ({len(keywords)} distinct):\n")
    for kw in sorted(keywords):
        print(f"  - {kw}")
    print()


def cmd_sources(args):
    """Show source citations grouped by source name."""
    cutoff = (date.today() - timedelta(days=10000 if args.all else args.days)).isoformat()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT s.source_name, s.source_type, COUNT(*) as count
           FROM sources s
           JOIN episodes e ON e.id = s.episode_id
           WHERE e.date >= ?
           GROUP BY s.source_name, s.source_type
           ORDER BY count DESC, s.source_name""",
        (cutoff,),
    ).fetchall()
    conn.close()
    
    if not rows:
        print("\n   (No sources recorded yet)\n")
        return
    
    print(f"\n📖 Sources cited (last {10000 if args.all else args.days} days):\n")
    by_type = Counter()
    for r in rows:
        marker = "★" if r["source_type"] == "peer_reviewed" else " "
        print(f"  {marker} [{r['count']}x] {r['source_name']} ({r['source_type']})")
        by_type[r["source_type"]] += r["count"]
    
    print(f"\n  Total citations: {sum(by_type.values())}")
    for stype, count in by_type.most_common():
        print(f"    - {stype}: {count}")
    print()


def cmd_pillars(args):
    """Show pillar usage distribution."""
    days = 10000 if args.all else args.days
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """SELECT pillar, COUNT(*) as count, MAX(date) as last_used
           FROM episodes
           WHERE date >= ?
           GROUP BY pillar
           ORDER BY count DESC""",
        (cutoff,),
    ).fetchall()
    conn.close()
    
    print(f"\n🎯 Pillar usage (last {days} days):\n")
    if not rows:
        print("   (No episodes yet)\n")
        return
    
    for pillar, count, last_used in rows:
        print(f"  {pillar:30s} {count:3d}x  (last: {last_used})")
    print()


def main():
    parser = argparse.ArgumentParser(description="Inspect Elio podcast memory.")
    parser.add_argument("--days", type=int, default=30, help="Window in days (default: 30)")
    parser.add_argument("--all", action="store_true", help="Show everything, ignoring --days")
    parser.add_argument("--pillar", type=str, help="Filter to a specific pillar")
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--keywords", action="store_true", help="Show topic keywords")
    group.add_argument("--sources", action="store_true", help="Show source citations")
    group.add_argument("--pillars-summary", action="store_true", help="Show pillar usage distribution")
    
    args = parser.parse_args()
    
    if not Path(DB_PATH).exists():
        print(f"\n❌ No memory database found at {DB_PATH}")
        print("   Run `python agent.py` to generate your first episode.\n")
        return
    
    if args.keywords:
        cmd_keywords(args)
    elif args.sources:
        cmd_sources(args)
    elif args.pillars_summary:
        cmd_pillars(args)
    else:
        cmd_summary(args)


if __name__ == "__main__":
    main()