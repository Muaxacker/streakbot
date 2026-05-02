"""
accountability.py — Feature 2: Accountability Score

A single 0-100 score per user that measures consistency AND quality.

Components:
  - Consistency (40 pts): % of days reported in last 30 days
  - Voice quality (20 pts): average voice explanation score
  - Quiz performance (20 pts): average quiz score
  - Study time (10 pts): average hours per session
  - Lesson progress (10 pts): % of course completed

Score is recalculated on demand and after each report.
Stored in data.json under "accountability" key.
"""

import logging
import os
from datetime import date, timedelta

log = logging.getLogger(__name__)


# ─── Score calculation ────────────────────────────────────────────────────────

def calculate_score(user_id: int) -> dict:
    """
    Calculate the full accountability score for a user.
    Returns: {
        total: int (0-100),
        consistency: int (0-40),
        voice: int (0-20),
        quiz: int (0-20),
        study_time: int (0-10),
        lesson_progress: int (0-10),
        breakdown: dict,
        grade: str,
        trend: str
    }
    """
    import storage
    data = storage.load()
    uid = str(user_id)

    # ── Consistency (40 pts) ──────────────────────────────────────────────────
    reports = data.get("reports", {})
    last_30 = [
        str(date.today() - timedelta(days=i)) for i in range(30)
    ]
    days_reported = sum(1 for d in last_30 if uid in reports.get(d, {}))
    consistency_score = round((days_reported / 30) * 40)

    # ── Voice quality (20 pts) ────────────────────────────────────────────────
    acc_data = data.get("accountability", {}).get(uid, {})
    voice_scores = acc_data.get("voice_scores", [])
    if voice_scores:
        avg_voice = sum(voice_scores[-10:]) / len(voice_scores[-10:])  # last 10
        voice_score = round((avg_voice / 10) * 20)
    else:
        voice_score = 0

    # ── Quiz performance (20 pts) ─────────────────────────────────────────────
    quiz_scores = acc_data.get("quiz_scores", [])
    if quiz_scores:
        avg_quiz = sum(quiz_scores[-10:]) / len(quiz_scores[-10:])  # last 10, 0-100%
        quiz_score = round((avg_quiz / 100) * 20)
    else:
        quiz_score = 0

    # ── Study time (10 pts) ───────────────────────────────────────────────────
    time_entries = []
    for day_reports in reports.values():
        rep = day_reports.get(uid, {})
        if rep:
            parsed = _parse_hours(rep.get("time_spent", ""))
            if parsed > 0:
                time_entries.append(parsed)

    if time_entries:
        avg_hours = sum(time_entries[-14:]) / len(time_entries[-14:])
        # 2+ hours = full 10 pts, scales down
        time_score = min(10, round((avg_hours / 2) * 10))
    else:
        time_score = 0

    # ── Lesson progress (10 pts) ──────────────────────────────────────────────
    try:
        import lessons as lessons_module
        summary = lessons_module.get_course_progress_summary(user_id)
        lesson_pct = summary.get("percentage", 0)
        lesson_score = round((lesson_pct / 100) * 10)
    except Exception:
        lesson_score = 0

    total = consistency_score + voice_score + quiz_score + time_score + lesson_score
    total = min(100, max(0, total))

    grade = _grade_label(total)
    trend = _calculate_trend(user_id, total, data)

    # Save current score
    _save_score(user_id, total, data)

    return {
        "total": total,
        "consistency": consistency_score,
        "voice": voice_score,
        "quiz": quiz_score,
        "study_time": time_score,
        "lesson_progress": lesson_score,
        "breakdown": {
            "days_reported_30": days_reported,
            "avg_voice": round(avg_voice, 1) if voice_scores else None,
            "avg_quiz_pct": round(avg_quiz, 1) if quiz_scores else None,
            "avg_hours": round(avg_hours, 1) if time_entries else None,
            "lesson_pct": lesson_pct if 'lesson_pct' in dir() else 0,
        },
        "grade": grade,
        "trend": trend,
    }


def _parse_hours(time_str: str) -> float:
    """Parse time strings like '2 hours', '45 minutes', '1.5 hours' into float hours."""
    if not time_str:
        return 0.0
    s = time_str.lower().strip()
    try:
        if "hour" in s:
            num = float(s.split("hour")[0].strip().split()[-1])
            return num
        elif "min" in s:
            num = float(s.split("min")[0].strip().split()[-1])
            return num / 60
        elif "hr" in s:
            num = float(s.replace("hr", "").strip())
            return num
        else:
            # Try parsing as a plain number
            return float(s.split()[0])
    except (ValueError, IndexError):
        return 0.0


def _grade_label(score: int) -> str:
    if score >= 85: return "🏆 Elite"
    if score >= 70: return "⭐ Strong"
    if score >= 55: return "👍 Solid"
    if score >= 40: return "📖 Building"
    if score >= 25: return "⚠️ Inconsistent"
    return "💀 Needs Work"


def _calculate_trend(user_id: int, current_score: int, data: dict) -> str:
    """Compare to previous score to show trend."""
    uid = str(user_id)
    history = data.get("accountability", {}).get(uid, {}).get("score_history", [])
    if len(history) < 2:
        return "→ New"
    prev = history[-1]
    diff = current_score - prev
    if diff >= 5:
        return f"↑ +{diff} pts"
    elif diff <= -5:
        return f"↓ {diff} pts"
    return "→ Stable"


def _save_score(user_id: int, score: int, data: dict):
    """Save score to history."""
    import storage
    uid = str(user_id)
    if "accountability" not in data:
        data["accountability"] = {}
    if uid not in data["accountability"]:
        data["accountability"][uid] = {
            "voice_scores": [],
            "quiz_scores": [],
            "score_history": [],
        }
    history = data["accountability"][uid].get("score_history", [])
    history.append(score)
    data["accountability"][uid]["score_history"] = history[-30:]  # keep last 30
    storage.save(data)


# ─── Record individual scores ─────────────────────────────────────────────────

def record_voice_score(user_id: int, score: int):
    """Called after a voice explanation is scored."""
    import storage
    data = storage.load()
    uid = str(user_id)
    if "accountability" not in data:
        data["accountability"] = {}
    if uid not in data["accountability"]:
        data["accountability"][uid] = {"voice_scores": [], "quiz_scores": [], "score_history": []}
    data["accountability"][uid].setdefault("voice_scores", []).append(score)
    storage.save(data)


def record_quiz_score(user_id: int, pct: int):
    """Called after a quiz is completed. pct = 0-100."""
    import storage
    data = storage.load()
    uid = str(user_id)
    if "accountability" not in data:
        data["accountability"] = {}
    if uid not in data["accountability"]:
        data["accountability"][uid] = {"voice_scores": [], "quiz_scores": [], "score_history": []}
    data["accountability"][uid].setdefault("quiz_scores", []).append(pct)
    storage.save(data)


# ─── Format messages ──────────────────────────────────────────────────────────

def format_score_card(user_id: int, name: str, score_data: dict) -> str:
    total = score_data["total"]
    grade = score_data["grade"]
    trend = score_data["trend"]
    b = score_data["breakdown"]

    def bar(val, max_val):
        filled = round((val / max_val) * 10) if max_val else 0
        return "█" * filled + "░" * (10 - filled)

    lines = [
        f"📊 <b>Accountability Score — {name}</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"<b>{total}/100</b>  {grade}  {trend}",
        f"{bar(total, 100)}",
        "",
        "── Breakdown ──",
        f"📅 Consistency:    {score_data['consistency']}/40"
        f"  ({b['days_reported_30']}/30 days)",
        f"🎙 Voice quality:  {score_data['voice']}/20"
        + (f"  (avg {b['avg_voice']}/10)" if b['avg_voice'] else "  (no voice yet)"),
        f"🧠 Quiz scores:    {score_data['quiz']}/20"
        + (f"  (avg {b['avg_quiz_pct']}%)" if b['avg_quiz_pct'] else "  (no quizzes yet)"),
        f"⏱ Study time:     {score_data['study_time']}/10"
        + (f"  (avg {b['avg_hours']}h/day)" if b['avg_hours'] else "  (no data yet)"),
        f"📚 Course progress:{score_data['lesson_progress']}/10"
        + (f"  ({b['lesson_pct']}%)" if b['lesson_pct'] else ""),
    ]

    # Troll/motivate based on score
    if total >= 85:
        lines.append("\n<i>🔥 You're in the top tier. Keep it there.</i>")
    elif total >= 70:
        lines.append("\n<i>⭐ Solid work. A few more consistent days and you hit Elite.</i>")
    elif total >= 55:
        lines.append("\n<i>👍 Good foundation. Your voice scores and quiz consistency will push this higher.</i>")
    elif total >= 40:
        lines.append("\n<i>📖 You're showing up but the quality needs work. More voice notes, more quizzes.</i>")
    else:
        lines.append("\n<i>💀 This score doesn't lie. You know what needs to change.</i>")

    return "\n".join(lines)


def format_comparison(user1_id: int, user2_id: int,
                       name1: str, name2: str,
                       score1: dict, score2: dict) -> str:
    t1 = score1["total"]
    t2 = score2["total"]

    if t1 > t2:
        leader = name1
        gap = t1 - t2
        troll = f"<i>{name2}, you're {gap} points behind. The gap is visible. 👀</i>"
    elif t2 > t1:
        leader = name2
        gap = t2 - t1
        troll = f"<i>{name1}, you're {gap} points behind. The gap is visible. 👀</i>"
    else:
        leader = None
        troll = "<i>Perfectly tied. One of you needs to pull ahead.</i>"

    lines = [
        "⚔️ <b>Accountability Comparison</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"{'👑' if t1 >= t2 else '  '} <b>{name1}</b>: {t1}/100  {score1['grade']}",
        f"{'👑' if t2 > t1 else '  '} <b>{name2}</b>: {t2}/100  {score2['grade']}",
        "",
        troll,
    ]
    return "\n".join(lines)
