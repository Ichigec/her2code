#!/usr/bin/env python3
"""Curator: analyze sessions → propose skill creation. Run via cron every 72h."""
import json, os, sys, time
from pathlib import Path
from collections import Counter

STATE_DB = Path.home() / ".hermes" / "state.db"
SKILLS_DIR = Path.home() / ".hermes" / "skills"
MIN_SESSION_LENGTH = 10  # messages
MIN_OCCURRENCES = 2       # pattern must appear in ≥2 sessions

def analyze_sessions():
    """Find patterns across recent sessions that could become skills."""
    import sqlite3
    db = sqlite3.connect(str(STATE_DB))
    db.row_factory = sqlite3.Row

    # Get recent sessions (>10 messages, last 30 days)
    cutoff = (time.time() - 30*86400) * 1000  # ms
    sessions = db.execute("""
        SELECT s.id, s.title, COUNT(m.id) as msg_count
        FROM sessions s
        JOIN messages m ON m.session_id = s.id
        WHERE s.created_at > ? AND m.role = 'user'
        GROUP BY s.id
        HAVING msg_count >= ?
        ORDER BY s.created_at DESC
        LIMIT 50
    """, (cutoff, MIN_SESSION_LENGTH)).fetchall()

    if not sessions:
        print("No qualifying sessions found")
        return

    # Extract topics from session titles
    topics = Counter()
    for s in sessions:
        title = s["title"] or ""
        for word in title.lower().split():
            if len(word) > 3:
                topics[word] += 1

    # Find recurring topics (≥2 occurrences)
    recurring = [(w, c) for w, c in topics.items() if c >= MIN_OCCURRENCES]
    if not recurring:
        print("No recurring topics")
        return

    print(f"Found {len(recurring)} recurring topics across {len(sessions)} sessions:")
    for word, count in recurring[:5]:
        print(f"  {word}: {count}x")

    # Check if skill already exists for these topics
    for word, count in recurring[:3]:
        skill_name = f"auto-{word}"
        existing = list(SKILLS_DIR.rglob(f"*{word}*/SKILL.md"))
        if existing:
            print(f"  Skill already exists for '{word}': {existing[0]}")
            continue

        # Propose new skill
        related_sessions = [s for s in sessions if word in (s["title"] or "").lower()]
        print(f"\n  Would create skill: {skill_name}")
        print(f"  Based on {len(related_sessions)} sessions")
        for s in related_sessions[:3]:
            print(f"    - {s['title']}")

    db.close()

if __name__ == "__main__":
    analyze_sessions()
