"""
session_log.py — Feature 5: Live Session Logger

Tracks live code review sessions between the two partners.
/session start  — starts a session timer
/session end    — ends it, logs duration, asks for rating + takeaway
/session log    — shows session history
"""

import json
import logging
import os
from datetime import datetime, date

log = logging.getLogger(__name__)
SESSION_FILE = "sessions.json"


# ─── Storage ──────────────────────────────────────────────────────────────────

def _load() -> dict:
    if not os.path.exists(SESSION_FILE):
        data = {"sessions": [], "active": None}
        _save(data)
        return data
    with open(SESSION_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ─── Session control ──────────────────────────────────────────────────────────

def start_session(started_by: int) -> dict:
    """Start a live session. Returns the session dict."""
    data = _load()
    if data.get("active"):
        return {"error": "already_active", "session": data["active"]}

    session = {
        "id": len(data["sessions"]) + 1,
        "started_by": started_by,
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "duration_minutes": None,
        "ratings": {},      # { "USER_ID": 1-5 }
        "takeaways": {},    # { "USER_ID": "what I learned from partner" }
        "date": str(date.today()),
    }
    data["active"] = session
    _save(data)
    return session


def end_session() -> dict | None:
    """End the active session. Returns the session with duration filled."""
    data = _load()
    session = data.get("active")
    if not session:
        return None

    end_time = datetime.now()
    start_time = datetime.fromisoformat(session["start_time"])
    duration = round((end_time - start_time).total_seconds() / 60)

    session["end_time"] = end_time.isoformat()
    session["duration_minutes"] = duration

    data["sessions"].append(session)
    data["active"] = None
    _save(data)
    return session


def add_rating(user_id: int, rating: int, takeaway: str):
    """Add a user's rating and takeaway to the most recent session."""
    data = _load()
    if not data["sessions"]:
        return
    session = data["sessions"][-1]
    session["ratings"][str(user_id)] = rating
    session["takeaways"][str(user_id)] = takeaway
    _save(data)


def get_active_session() -> dict | None:
    return _load().get("active")


def get_sessions(limit: int = 10) -> list[dict]:
    data = _load()
    return data["sessions"][-limit:]


def get_session_stats() -> dict:
    """Return aggregate stats across all sessions."""
    data = _load()
    sessions = data["sessions"]
    if not sessions:
        return {"count": 0, "total_minutes": 0, "avg_minutes": 0, "avg_rating": None}

    total_min = sum(s.get("duration_minutes", 0) or 0 for s in sessions)
    all_ratings = []
    for s in sessions:
        all_ratings.extend(s.get("ratings", {}).values())

    return {
        "count": len(sessions),
        "total_minutes": total_min,
        "avg_minutes": round(total_min / len(sessions)),
        "avg_rating": round(sum(all_ratings) / len(all_ratings), 1) if all_ratings else None,
    }


# ─── Format messages ──────────────────────────────────────────────────────────

def format_session_started(session: dict, name: str) -> str:
    return (
        f"🎥 <b>Live Session Started!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Started by: <b>{name}</b>\n"
        f"Time: {datetime.fromisoformat(session['start_time']).strftime('%H:%M')}\n\n"
        f"<i>Do your code review. When you're done, use /session end</i>"
    )


def format_session_ended(session: dict) -> str:
    duration = session.get("duration_minutes", 0)
    return (
        f"✅ <b>Session Complete!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏱ Duration: <b>{duration} minutes</b>\n\n"
        f"<i>Now rate the session and share one thing you learned from your partner.\n"
        f"Use /session rate [1-5] [what you learned]</i>\n\n"
        f"Example: <code>/session rate 5 I learned how to structure Express routes better</code>"
    )


def format_session_log(sessions: list[dict], name1: str, name2: str,
                        user1_id: int, user2_id: int) -> str:
    if not sessions:
        return (
            "📭 <b>No sessions logged yet.</b>\n\n"
            "Use /session start when you begin a live code review."
        )

    stats = get_session_stats()
    lines = [
        "🎥 <b>Live Session Log</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"Total sessions: <b>{stats['count']}</b>",
        f"Total time: <b>{stats['total_minutes']} min</b>",
        f"Avg duration: <b>{stats['avg_minutes']} min</b>",
        f"Avg rating: <b>{stats['avg_rating']}/5</b>" if stats['avg_rating'] else "Avg rating: <b>—</b>",
        "",
    ]

    for s in reversed(sessions[-5:]):
        dur = s.get("duration_minutes", "?")
        ratings = s.get("ratings", {})
        r1 = ratings.get(str(user1_id), "—")
        r2 = ratings.get(str(user2_id), "—")
        lines.append(f"📅 <b>{s['date']}</b>  ⏱ {dur}min  ⭐ {r1}/{r2}")

        takeaways = s.get("takeaways", {})
        t1 = takeaways.get(str(user1_id), "")
        t2 = takeaways.get(str(user2_id), "")
        if t1:
            lines.append(f"  💡 {name1}: {t1[:60]}")
        if t2:
            lines.append(f"  💡 {name2}: {t2[:60]}")
        lines.append("")

    return "\n".join(lines)
