"""CLI utility for inspecting episode memory."""

import argparse
import os
from collections import Counter
from datetime import date, timedelta

from memory import (
    USE_POSTGRES,
    episode_count,
    recent_episodes,
    recent_keywords,
    _connect,
    _placeholder,
)


def cmd_summary(args):
    if args.all:
        episodes = recent_episodes(days=10000)
    else:
        episodes = recent_episodes(days=args.days)
    if args.pillar:
        episodes = [e for e in episodes if e["pillar"] == args.pillar]
    
    backend = "Postgres" if USE_POSTGRES else "SQLite"
    print(f"\n📚 Episode Memory ({len(episodes)} episode{'s' if len(episodes) != 1 else ''})")
    print(f"   Backend: {backend}")
    print(f"   Total in DB: {episode_count()}\n")
    
    if not episodes:
        print("   (No episodes yet)")
        return
    
    for ep in episodes:
        date_str = ep["date"]
        pillar = ep["pillar"]
        topic = ep["topic_summary"]
        words = ep["word_count"] or 0
        print(f"  {date_str} | {pillar:30s} | {words} words")
        print(f"             {topic}")
        print()


def cmd_keywords(args):
    days = 10000 if args.all else args.days
    keywords = recent_keywords(days=days)
    print(f"\n🔑 Topic keywords from the last {days} days ({len(keywords)} distinct):\n")
    for kw in sorted(keywords):
        print(f"  - {kw}")
    print()


def cmd_sources(args):
    days = 10000 if args.all else args.days
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    p = _placeholder()
    
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""SELECT s.source_name, s.source_type, COUNT(*) AS count
                FROM sources s
                JOIN episodes e ON e.id = s.episode_id
                WHERE e.date >= {p}
                GROUP BY s.source_name, s.source_type
                ORDER BY count DESC, s.source_name""",
            (cutoff,),
        )
        rows = cur.fetchall()
    
    if not rows:
        print("\n   (No sources recorded yet)\n")
        return
    
    print(f"\n📖 Sources cited (last {days} days):\n")
    by_type = Counter()
    for r in rows:
        name = r["source_name"]
        stype = r["source_type"]
        count = r["count"]
        marker = "★" if stype == "peer_reviewed" else " "
        print(f"  {marker} [{count}x] {name} ({stype})")
        by_type[stype] += count
    
    print(f"\n  Total citations: {sum(by_type.values())}")
    for stype, count in by_type.most_common():
        print(f"    - {stype}: {count}")
    print()


def cmd_pillars(args):
    days = 10000 if args.all else args.days
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    p = _placeholder()
    
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""SELECT pillar, COUNT(*) AS count, MAX(date) AS last_used
                FROM episodes
                WHERE date >= {p}
                GROUP BY pillar
                ORDER BY count DESC""",
            (cutoff,),
        )
        rows = cur.fetchall()
    
    print(f"\n🎯 Pillar usage (last {days} days):\n")
    if not rows:
        print("   (No episodes yet)\n")
        return
    for r in rows:
        print(f"  {r['pillar']:30s} {r['count']:3d}x  (last: {r['last_used']})")
    print()


def main():
    parser = argparse.ArgumentParser(description="Inspect Elio podcast memory.")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--pillar", type=str)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--keywords", action="store_true")
    group.add_argument("--sources", action="store_true")
    group.add_argument("--pillars-summary", action="store_true")
    args = parser.parse_args()
    
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
