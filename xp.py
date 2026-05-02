"""
xp.py — Phase 4: XP points and level system

Every action earns XP. Levels unlock titles.
XP is tracked per user and shown on the dashboard.
"""

import json
import os
from datetime import date

XP_FILE = "xp.json"

# ─── XP Values per action ─────────────────────────────────────────────────────

XP_ACTIONS = {
    "daily_report":        10,
    "voice_basic":         10,
    "voice_good":          20,
    "voice_great":         30,
    "voice_exceptional":   50,
    "lesson_step":          5,
    "lesson_complete":     15,
    "weekly_project":      50,
    "project_good":        20,
    "project_great":       40,
    "streak_7":            25,
    "streak_14":           50,
    "streak_30":          100,
    "streak_60":          200,
    "streak_100":         500,
    # Feature 1 — Spaced Repetition
    "review_remembered":   15,   # answered a review correctly
    "review_mastered":     30,   # completed all 3 review intervals for a topic
    # Feature 2 — Accountability
    "score_80_plus":       25,   # accountability score hits 80+
    # Feature 3 — Struggle resolved
    "struggle_resolved":   20,   # marked a struggle as resolved
    # Feature 4 — Interview Prep
    "interview_completed":  20,  # finished an interview session
    "interview_strong":     30,  # scored 80%+ in interview session
}

# ─── Levels ───────────────────────────────────────────────────────────────────

LEVELS = [
    {"level": 1,  "title": "Beginner",        "xp_needed": 0},
    {"level": 2,  "title": "Explorer",        "xp_needed": 100},
    {"level": 3,  "title": "Builder",         "xp_needed": 250},
    {"level": 4,  "title": "Developer",       "xp_needed": 500},
    {"level": 5,  "title": "Engineer",        "xp_needed": 900},
    {"level": 6,  "title": "Senior Dev",      "xp_needed": 1400},
    {"level": 7,  "title": "Architect",       "xp_needed": 2000},
    {"level": 8,  "title": "Full Stack Pro",  "xp_needed": 3000},
    {"level": 9,  "title": "Tech Lead",       "xp_needed": 4500},
    {"level": 10, "title": "Elite Coder",     "xp_needed": 7000},
]


# ─── Load / Save ──────────────────────────────────────────────────────────────

def _default_xp():
    return {
        "users": {}  # { "USER_ID": { "total": int, "history": [ {action, xp, date} ] } }
    }


def load_xp():
    if not os.path.exists(XP_FILE):
        data = _default_xp()
        save_xp(data)
        return data
    with open(XP_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_xp(data):
    with open(XP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ─── Award XP ─────────────────────────────────────────────────────────────────

def award_xp(user_id: int, action: str, bonus: int = 0) -> dict:
    """
    Award XP to a user for an action.
    Returns dict with: xp_earned, total_xp, level_before, level_after, leveled_up
    """
    data = load_xp()
    uid = str(user_id)

    if uid not in data["users"]:
        data["users"][uid] = {"total": 0, "history": []}

    xp_earned = XP_ACTIONS.get(action, 0) + bonus
    if xp_earned <= 0:
        return {"xp_earned": 0, "total_xp": data["users"][uid]["total"],
                "leveled_up": False}

    level_before = get_level(data["users"][uid]["total"])["level"]

    data["users"][uid]["total"] += xp_earned
    data["users"][uid]["history"].append({
        "action": action,
        "xp": xp_earned,
        "date": str(date.today())
    })

    level_after = get_level(data["users"][uid]["total"])["level"]
    save_xp(data)

    return {
        "xp_earned": xp_earned,
        "total_xp": data["users"][uid]["total"],
        "level_before": level_before,
        "level_after": level_after,
        "leveled_up": level_after > level_before,
        "new_level_title": get_level(data["users"][uid]["total"])["title"]
    }


def get_user_xp(user_id: int) -> int:
    data = load_xp()
    return data["users"].get(str(user_id), {}).get("total", 0)


def get_level(xp: int) -> dict:
    """Return the level dict for a given XP amount."""
    current = LEVELS[0]
    for lvl in LEVELS:
        if xp >= lvl["xp_needed"]:
            current = lvl
    return current


def get_xp_to_next_level(xp: int) -> int | None:
    """Return XP needed to reach next level, or None if max level."""
    current_level = get_level(xp)
    for lvl in LEVELS:
        if lvl["level"] == current_level["level"] + 1:
            return lvl["xp_needed"] - xp
    return None  # Already max level


def voice_xp_action(score: int) -> str:
    """Return the XP action key based on voice score."""
    if score == 10:
        return "voice_exceptional"
    elif score >= 8:
        return "voice_great"
    elif score >= 6:
        return "voice_good"
    else:
        return "voice_basic"


def project_xp_bonus(score: int) -> str | None:
    """Return bonus XP action for project score."""
    if score >= 9:
        return "project_great"
    elif score >= 7:
        return "project_good"
    return None


# ─── Leaderboard ──────────────────────────────────────────────────────────────

def get_leaderboard(user1_id: int, user2_id: int,
                     name1: str, name2: str) -> str:
    xp1 = get_user_xp(user1_id)
    xp2 = get_user_xp(user2_id)
    lvl1 = get_level(xp1)
    lvl2 = get_level(xp2)
    next1 = get_xp_to_next_level(xp1)
    next2 = get_xp_to_next_level(xp2)

    def bar(xp, level_data):
        next_lvl = next((l for l in LEVELS if l["level"] == level_data["level"] + 1), None)
        if not next_lvl:
            return "██████████ MAX"
        needed = level_data["xp_needed"]
        progress = xp - needed
        total_needed = next_lvl["xp_needed"] - needed
        filled = min(10, int(progress / total_needed * 10)) if total_needed else 10
        return "█" * filled + "░" * (10 - filled)

    if xp1 > xp2:
        u1_crown, u2_crown = "👑", "  "
        gap_line = f"\n<i>{name1} is leading by {xp1 - xp2} XP. {name2}, you sleeping? 😴</i>"
    elif xp2 > xp1:
        u1_crown, u2_crown = "  ", "👑"
        gap_line = f"\n<i>{name2} is leading by {xp2 - xp1} XP. {name1}, you sleeping? 😴</i>"
    else:
        u1_crown, u2_crown = "🤝", "🤝"
        gap_line = f"\n<i>Perfectly tied. One of you needs to pull ahead. 👀</i>"

    lines = [
        "🏆 <b>XP Leaderboard</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"{u1_crown} <b>{name1}</b>",
        f"   Level {lvl1['level']} — {lvl1['title']}",
        f"   ⚡ {xp1} XP  {bar(xp1, lvl1)}",
        f"   {'Next level: ' + str(next1) + ' XP away' if next1 else '🏆 MAX LEVEL'}",
        "",
        f"{u2_crown} <b>{name2}</b>",
        f"   Level {lvl2['level']} — {lvl2['title']}",
        f"   ⚡ {xp2} XP  {bar(xp2, lvl2)}",
        f"   {'Next level: ' + str(next2) + ' XP away' if next2 else '🏆 MAX LEVEL'}",
        gap_line,
    ]
    return "\n".join(lines)


def format_xp_award(result: dict, name: str) -> str:
    if result["xp_earned"] <= 0:
        return ""
    lines = [f"⚡ <b>+{result['xp_earned']} XP</b> for {name}"]
    if result.get("leveled_up"):
        lines.append(
            f"🎉 <b>LEVEL UP!</b> {name} is now <b>Level {result['level_after']} "
            f"— {result['new_level_title']}</b> 🚀"
        )
    return "\n".join(lines)
