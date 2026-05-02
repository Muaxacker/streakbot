import json
import os
from datetime import date, datetime, timedelta

DATA_FILE = "data.json"


# ─── Default data structure ───────────────────────────────────────────────────

def _default():
    return {
        "streak": 0,
        "longest_streak": 0,
        "last_streak_date": None,
        "pinned_msg_id": None,
        "reminder_time": "20:00",
        "reports": {},        # { "YYYY-MM-DD": { "USER_ID": { text, topic, time_spent, difficulty } } }
        "next_topics": {},    # { "USER_ID": "topic string" }
        "user_names": {},     # { "USER_ID": "display name" }
        "milestones_sent": [] # list of milestone numbers already celebrated
    }


# ─── Load / Save ──────────────────────────────────────────────────────────────

def load():
    if not os.path.exists(DATA_FILE):
        data = _default()
        save(data)
        return data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Fill in any missing keys if upgrading from older version
    default = _default()
    for key, val in default.items():
        if key not in data:
            data[key] = val
    return data


def save(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ─── User names ───────────────────────────────────────────────────────────────

def set_user_name(user_id: int, name: str):
    data = load()
    data["user_names"][str(user_id)] = name
    save(data)


def get_user_name(user_id: int, data=None) -> str:
    if data is None:
        data = load()
    return data["user_names"].get(str(user_id), f"User {user_id}")


# ─── Reports ──────────────────────────────────────────────────────────────────

def add_report(user_id: int, learned: str, topic: str, time_spent: str, difficulty: str):
    data = load()
    today = str(date.today())

    if today not in data["reports"]:
        data["reports"][today] = {}

    data["reports"][today][str(user_id)] = {
        "learned": learned,
        "topic": topic,
        "time_spent": time_spent,
        "difficulty": difficulty,
        "submitted_at": datetime.now().strftime("%H:%M")
    }

    # Also update next_topics from report
    if topic.strip():
        data["next_topics"][str(user_id)] = topic.strip()

    save(data)
    return data


def get_today_reports(data=None):
    if data is None:
        data = load()
    today = str(date.today())
    return data["reports"].get(today, {})


def get_reports_for_days(n: int):
    """Return reports for the last n days (most recent first)."""
    data = load()
    result = []
    for i in range(n):
        day = str(date.today() - timedelta(days=i))
        if day in data["reports"]:
            result.append({"date": day, **data["reports"][day]})
    return result


def both_reported_today(user1_id: int, user2_id: int, data=None) -> bool:
    today_reports = get_today_reports(data)
    return (
        str(user1_id) in today_reports and
        str(user2_id) in today_reports
    )


def who_reported_today(user1_id: int, user2_id: int, data=None):
    today_reports = get_today_reports(data)
    reported = []
    not_reported = []
    for uid in [user1_id, user2_id]:
        if str(uid) in today_reports:
            reported.append(uid)
        else:
            not_reported.append(uid)
    return reported, not_reported


# ─── Streak logic ─────────────────────────────────────────────────────────────

def update_streak(user1_id: int, user2_id: int) -> dict:
    """
    Called when both users have reported today.
    Updates streak count and longest streak.
    Returns updated data dict.
    """
    data = load()
    today = str(date.today())
    yesterday = str(date.today() - timedelta(days=1))

    # Already updated today — don't double count
    if data["last_streak_date"] == today:
        return data

    # Check if yesterday both reported (streak continues) or it's first day
    if data["last_streak_date"] == yesterday:
        data["streak"] += 1
    else:
        # Streak broken — reset to 1
        data["streak"] = 1

    data["last_streak_date"] = today

    if data["streak"] > data["longest_streak"]:
        data["longest_streak"] = data["streak"]

    save(data)
    return data


def get_streak(data=None) -> int:
    if data is None:
        data = load()
    return data.get("streak", 0)


def reset_streak():
    data = load()
    data["streak"] = 0
    data["last_streak_date"] = None
    save(data)


# ─── Next topics ──────────────────────────────────────────────────────────────

def set_next_topic(user_id: int, topic: str):
    data = load()
    data["next_topics"][str(user_id)] = topic.strip()
    save(data)


def get_next_topics(data=None) -> dict:
    if data is None:
        data = load()
    return data.get("next_topics", {})


# ─── Pinned message ───────────────────────────────────────────────────────────

def set_pinned_msg_id(msg_id: int):
    data = load()
    data["pinned_msg_id"] = msg_id
    save(data)


def get_pinned_msg_id(data=None):
    if data is None:
        data = load()
    return data.get("pinned_msg_id")


# ─── Reminder time ────────────────────────────────────────────────────────────

def set_reminder_time(time_str: str):
    """time_str format: HH:MM"""
    data = load()
    data["reminder_time"] = time_str
    save(data)


def get_reminder_time(data=None) -> str:
    if data is None:
        data = load()
    return data.get("reminder_time", "20:00")


# ─── Milestones ───────────────────────────────────────────────────────────────

def check_milestone(streak: int) -> int | None:
    """Returns the milestone number if this streak hits one, else None."""
    milestones = [7, 14, 30, 60, 100]
    data = load()
    for m in milestones:
        if streak >= m and m not in data["milestones_sent"]:
            data["milestones_sent"].append(m)
            save(data)
            return m
    return None


def reset_milestones():
    data = load()
    data["milestones_sent"] = []
    save(data)


# ─── Struggle Tracker ─────────────────────────────────────────────────────────

def add_struggle(user_id: int, topic: str, reason: str = ""):
    """
    Record a topic as a struggle for a user.
    reason: 'hard_difficulty' | 'low_quiz' | 'low_voice' | 'manual'
    """
    data = load()
    uid = str(user_id)
    today = str(date.today())

    if "struggles" not in data:
        data["struggles"] = {}
    if uid not in data["struggles"]:
        data["struggles"][uid] = []

    # Avoid exact duplicates on same day
    existing = [s for s in data["struggles"][uid]
                if s["topic"] == topic and s["date"] == today]
    if existing:
        save(data)
        return

    data["struggles"][uid].append({
        "topic": topic,
        "reason": reason,
        "date": today,
        "resolved": False,
    })
    save(data)


def resolve_struggle(user_id: int, topic: str):
    """Mark a struggle as resolved."""
    data = load()
    uid = str(user_id)
    for s in data.get("struggles", {}).get(uid, []):
        if s["topic"] == topic and not s["resolved"]:
            s["resolved"] = True
            break
    save(data)


def get_struggles(user_id: int, unresolved_only: bool = True) -> list[dict]:
    """Return struggles for a user."""
    data = load()
    uid = str(user_id)
    struggles = data.get("struggles", {}).get(uid, [])
    if unresolved_only:
        return [s for s in struggles if not s["resolved"]]
    return struggles


def get_recent_difficulty_pattern(user_id: int, days: int = 3) -> str | None:
    """
    Check if user has reported 'hard' difficulty for N consecutive days.
    Returns the pattern description or None.
    """
    uid = str(user_id)
    data = load()
    reports = data.get("reports", {})

    difficulties = []
    for i in range(days):
        day = str(date.today() - timedelta(days=i))
        rep = reports.get(day, {}).get(uid, {})
        if rep:
            difficulties.append(rep.get("difficulty", ""))

    if len(difficulties) == days and all(d == "hard" for d in difficulties):
        return f"hard_{days}_days"

    return None


def get_study_time_trend(user_id: int) -> dict | None:
    """
    Detect if study time has dropped significantly (burnout signal).
    Returns { drop_pct, recent_avg, previous_avg } or None.
    """
    uid = str(user_id)
    data = load()
    reports = data.get("reports", {})

    def parse_hours(s: str) -> float:
        if not s:
            return 0.0
        s = s.lower().strip()
        try:
            if "hour" in s:
                return float(s.split("hour")[0].strip().split()[-1])
            elif "min" in s:
                return float(s.split("min")[0].strip().split()[-1]) / 60
            elif "hr" in s:
                return float(s.replace("hr", "").strip())
            else:
                return float(s.split()[0])
        except (ValueError, IndexError):
            return 0.0

    recent_hours = []
    prev_hours = []

    for i in range(7):
        day = str(date.today() - timedelta(days=i))
        rep = reports.get(day, {}).get(uid, {})
        if rep:
            h = parse_hours(rep.get("time_spent", ""))
            if h > 0:
                if i < 3:
                    recent_hours.append(h)
                else:
                    prev_hours.append(h)

    if not recent_hours or not prev_hours:
        return None

    recent_avg = sum(recent_hours) / len(recent_hours)
    prev_avg = sum(prev_hours) / len(prev_hours)

    if prev_avg == 0:
        return None

    drop_pct = round((1 - recent_avg / prev_avg) * 100)
    if drop_pct >= 50:
        return {
            "drop_pct": drop_pct,
            "recent_avg": round(recent_avg, 1),
            "previous_avg": round(prev_avg, 1),
        }
    return None
