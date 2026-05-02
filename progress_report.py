"""
progress_report.py — Feature 8: Monthly Progress Report

Generates a comprehensive progress report as a Telegram message.
/progressreport — full monthly summary
/progressreport week — this week only

Covers: streak, reports, lessons, projects, voice scores,
        quiz scores, interview scores, session time, XP, level.
"""

import logging
import os
from datetime import date, timedelta

from groq import Groq

log = logging.getLogger(__name__)


def generate_report(user_id: int, name: str, period: str = "month") -> str:
    """
    Build a full progress report for a user.
    period: 'month' | 'week'
    Returns formatted HTML string.
    """
    import storage
    import xp as xp_module
    import spaced_repetition as sr
    import accountability as acc

    days = 30 if period == "month" else 7
    label = "Monthly" if period == "month" else "Weekly"

    data = storage.load()
    uid = str(user_id)
    reports = data.get("reports", {})

    # ── Reports ───────────────────────────────────────────────────────────────
    period_dates = [str(date.today() - timedelta(days=i)) for i in range(days)]
    days_reported = sum(1 for d in period_dates if uid in reports.get(d, {}))
    completion_pct = round(days_reported / days * 100)

    # ── Study time ────────────────────────────────────────────────────────────
    total_hours = 0.0
    for d in period_dates:
        rep = reports.get(d, {}).get(uid, {})
        if rep:
            total_hours += _parse_hours(rep.get("time_spent", ""))

    # ── Difficulty breakdown ──────────────────────────────────────────────────
    diff_counts = {"easy": 0, "medium": 0, "hard": 0}
    for d in period_dates:
        rep = reports.get(d, {}).get(uid, {})
        if rep:
            diff = rep.get("difficulty", "")
            if diff in diff_counts:
                diff_counts[diff] += 1

    # ── Streak ────────────────────────────────────────────────────────────────
    streak = data.get("streak", 0)
    longest = data.get("longest_streak", 0)

    # ── XP & Level ────────────────────────────────────────────────────────────
    xp = xp_module.get_user_xp(user_id)
    level = xp_module.get_level(xp)

    # ── Lessons ───────────────────────────────────────────────────────────────
    try:
        import lessons as lessons_module
        course_summary = lessons_module.get_course_progress_summary(user_id)
        lessons_done = course_summary["completed"]
        lessons_total = course_summary["total"]
        course_pct = course_summary["percentage"]
    except Exception:
        lessons_done = lessons_total = course_pct = 0

    # ── Spaced repetition ─────────────────────────────────────────────────────
    mastered = sr.count_mastered(user_id)
    pending_reviews = len(sr.get_due_reviews(user_id))

    # ── Accountability score ──────────────────────────────────────────────────
    acc_data = data.get("accountability", {}).get(uid, {})
    voice_scores = acc_data.get("voice_scores", [])
    quiz_scores = acc_data.get("quiz_scores", [])
    avg_voice = round(sum(voice_scores) / len(voice_scores), 1) if voice_scores else None
    avg_quiz = round(sum(quiz_scores) / len(quiz_scores), 1) if quiz_scores else None

    # ── Sessions ──────────────────────────────────────────────────────────────
    try:
        import session_log
        stats = session_log.get_session_stats()
        session_count = stats["count"]
        session_hours = round(stats["total_minutes"] / 60, 1)
    except Exception:
        session_count = session_hours = 0

    # ── Struggles ─────────────────────────────────────────────────────────────
    struggles = storage.get_struggles(user_id, unresolved_only=True)

    # ── Build the report ──────────────────────────────────────────────────────
    def bar(val, max_val, width=10):
        if max_val == 0:
            return "░" * width
        filled = min(width, round(val / max_val * width))
        return "█" * filled + "░" * (width - filled)

    lines = [
        f"📋 <b>{label} Progress Report — {name}</b>",
        f"<i>{date.today() - timedelta(days=days-1)} → {date.today()}</i>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        "📅 <b>Consistency</b>",
        f"  Reported: {days_reported}/{days} days  ({completion_pct}%)",
        f"  {bar(days_reported, days)}",
        f"  🔥 Current streak: {streak}  |  🏆 Best: {longest}",
        "",
        "⏱ <b>Study Time</b>",
        f"  Total: {round(total_hours, 1)} hours over {days} days",
        f"  Avg/day: {round(total_hours / days, 1)}h",
        f"  🟢 Easy: {diff_counts['easy']}  🟡 Medium: {diff_counts['medium']}  🔴 Hard: {diff_counts['hard']}",
        "",
        "📚 <b>Course Progress</b>",
        f"  Lessons done: {lessons_done}/{lessons_total}  ({course_pct}%)",
        f"  {bar(lessons_done, lessons_total)}",
        "",
        "🔁 <b>Spaced Repetition</b>",
        f"  Topics mastered: {mastered}",
        f"  Reviews due today: {pending_reviews}",
        "",
        "🎙 <b>Voice Explanations</b>",
        f"  Sessions: {len(voice_scores)}",
        f"  Avg score: {avg_voice}/10" if avg_voice else "  No voice sessions yet",
        "",
        "🧠 <b>Quiz & Interview</b>",
        f"  Avg quiz score: {avg_quiz}%" if avg_quiz else "  No quiz data yet",
        "",
        "🎥 <b>Live Sessions</b>",
        f"  Sessions: {session_count}  |  Total: {session_hours}h",
        "",
        "⚡ <b>XP & Level</b>",
        f"  Total XP: {xp}",
        f"  Level {level['level']} — {level['title']}",
        "",
    ]

    if struggles:
        lines += [
            "⚠️ <b>Active Struggles</b>",
            *[f"  • {s['topic']}" for s in struggles[:5]],
            "",
        ]

    # AI narrative summary
    ai_summary = _generate_ai_narrative(
        name=name,
        days_reported=days_reported,
        days=days,
        total_hours=round(total_hours, 1),
        streak=streak,
        course_pct=course_pct,
        mastered=mastered,
        avg_voice=avg_voice,
        struggles=[s["topic"] for s in struggles[:3]],
        period=label.lower(),
    )
    if ai_summary:
        lines += [
            "━━━━━━━━━━━━━━━━━━━━",
            "🤖 <b>AI Assessment</b>",
            "",
            ai_summary,
        ]

    return "\n".join(lines)


def _generate_ai_narrative(name: str, days_reported: int, days: int,
                            total_hours: float, streak: int, course_pct: int,
                            mastered: int, avg_voice, struggles: list,
                            period: str) -> str:
    prompt = f"""You are StreakBot writing a {period} assessment for {name}.

Data:
- Reported {days_reported}/{days} days ({round(days_reported/days*100)}% consistency)
- Total study time: {total_hours} hours
- Current streak: {streak} days
- Course progress: {course_pct}%
- Topics mastered via spaced repetition: {mastered}
- Average voice score: {avg_voice}/10 if available
- Active struggles: {', '.join(struggles) if struggles else 'none'}

Write a 3-4 sentence honest assessment:
- What's going well (be specific)
- What needs improvement (be direct, not harsh)
- One actionable thing to focus on next {period}

Tone: direct, warm, slightly troll. Like a coach who genuinely wants them to succeed.
No markdown. No bullet points. Just flowing sentences."""

    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        log.error(f"Progress report AI error: {e}")
        return (
            f"{name} reported {days_reported} out of {days} days this {period}. "
            f"That's {round(days_reported/days*100)}% consistency. "
            f"The streak is at {streak} days and the course is {course_pct}% complete. "
            f"Keep the daily reports coming — the data tells the real story."
        )


def _parse_hours(s: str) -> float:
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
