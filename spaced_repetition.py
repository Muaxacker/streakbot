"""
spaced_repetition.py — Feature 1: Spaced Repetition Review System

After each report, topics are tagged and scheduled for review at:
  Day 3, Day 7, Day 14 after they were first studied.

Each morning the bot checks if any topics are due for review
and sends a personal question to each user.

Storage: uses data.json via storage.py (adds "review_schedule" key)
"""

import json
import logging
import os
from datetime import date, timedelta

from groq import Groq

log = logging.getLogger(__name__)

# Review intervals in days
REVIEW_INTERVALS = [3, 7, 14]


# ─── Storage helpers ──────────────────────────────────────────────────────────

def _load():
    import storage
    return storage.load()


def _save(data):
    import storage
    storage.save(data)


def _ensure_schedule(data: dict) -> dict:
    if "review_schedule" not in data:
        data["review_schedule"] = {}
        # { "USER_ID": [ { topic, learned, studied_date, next_review, interval_index, done_dates } ] }
    return data


# ─── Schedule a topic for review ─────────────────────────────────────────────

def schedule_topic(user_id: int, topic: str, learned: str):
    """
    Called after a report is saved.
    Schedules the topic for review at day 3, 7, 14.
    """
    data = _load()
    _ensure_schedule(data)
    uid = str(user_id)
    today = str(date.today())

    if uid not in data["review_schedule"]:
        data["review_schedule"][uid] = []

    # Avoid duplicate scheduling for same topic on same day
    existing = [
        r for r in data["review_schedule"][uid]
        if r["topic"] == topic and r["studied_date"] == today
    ]
    if existing:
        _save(data)
        return

    next_review = str(date.today() + timedelta(days=REVIEW_INTERVALS[0]))

    data["review_schedule"][uid].append({
        "topic": topic,
        "learned": learned,
        "studied_date": today,
        "next_review": next_review,
        "interval_index": 0,   # index into REVIEW_INTERVALS
        "done_dates": [],       # dates when review was completed
    })

    _save(data)


def advance_review(user_id: int, topic: str, studied_date: str):
    """
    Move a topic to the next review interval after it's been reviewed.
    """
    data = _load()
    _ensure_schedule(data)
    uid = str(user_id)
    today = str(date.today())

    for item in data["review_schedule"].get(uid, []):
        if item["topic"] == topic and item["studied_date"] == studied_date:
            item["done_dates"].append(today)
            next_idx = item["interval_index"] + 1
            if next_idx < len(REVIEW_INTERVALS):
                item["interval_index"] = next_idx
                item["next_review"] = str(
                    date.today() + timedelta(days=REVIEW_INTERVALS[next_idx])
                )
            else:
                # All intervals done — mark as mastered
                item["next_review"] = None
                item["mastered"] = True
            break

    _save(data)


def dismiss_review(user_id: int, topic: str, studied_date: str):
    """Dismiss a review without advancing (user skipped it)."""
    data = _load()
    _ensure_schedule(data)
    uid = str(user_id)
    today = str(date.today())

    for item in data["review_schedule"].get(uid, []):
        if item["topic"] == topic and item["studied_date"] == studied_date:
            # Push to next interval anyway so it doesn't spam
            next_idx = item["interval_index"] + 1
            if next_idx < len(REVIEW_INTERVALS):
                item["interval_index"] = next_idx
                item["next_review"] = str(
                    date.today() + timedelta(days=REVIEW_INTERVALS[next_idx])
                )
            else:
                item["next_review"] = None
            break

    _save(data)


# ─── Get due reviews ──────────────────────────────────────────────────────────

def get_due_reviews(user_id: int) -> list[dict]:
    """
    Return all topics due for review today or overdue.
    Each item: { topic, learned, studied_date, interval_index }
    """
    data = _load()
    _ensure_schedule(data)
    uid = str(user_id)
    today = date.today()

    due = []
    for item in data["review_schedule"].get(uid, []):
        if item.get("mastered"):
            continue
        next_review = item.get("next_review")
        if not next_review:
            continue
        if date.fromisoformat(next_review) <= today:
            due.append(item)

    return due


def get_all_scheduled(user_id: int) -> list[dict]:
    """Return all scheduled reviews (for /reviews command)."""
    data = _load()
    _ensure_schedule(data)
    uid = str(user_id)
    return data["review_schedule"].get(uid, [])


def count_mastered(user_id: int) -> int:
    data = _load()
    _ensure_schedule(data)
    uid = str(user_id)
    return sum(1 for r in data["review_schedule"].get(uid, []) if r.get("mastered"))


# ─── AI review question ───────────────────────────────────────────────────────

def generate_review_question(topic: str, learned: str, name: str,
                              days_ago: int) -> str:
    """
    Generate a spaced repetition question for a topic studied N days ago.
    Returns a question string.
    """
    prompt = f"""You are StreakBot running a spaced repetition review for a full stack web development student.

Student: {name}
Topic they studied {days_ago} days ago: {topic}
What they learned: {learned}

Generate ONE review question that tests whether they still remember and understand this topic.

Rules:
- Make it practical — ask them to explain, apply, or give an example
- Don't ask "what is X" — ask them to demonstrate understanding
- Keep it to 1-2 sentences
- Add a short troll opener like "Time to see if it stuck..." or "{days_ago} days later, let's check..."
- No markdown

Respond with ONLY the question, nothing else."""

    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        log.error(f"Review question error: {e}")
        days_label = f"{days_ago} days ago"
        return (
            f"{days_ago} days later... You studied {topic} {days_label}. "
            f"Can you still explain it clearly with an example?"
        )


def grade_review_answer(topic: str, learned: str, answer: str, name: str) -> dict:
    """
    Grade a spaced repetition review answer.
    Returns: { remembered: bool, score: 1-5, feedback: str }
    """
    prompt = f"""You are StreakBot grading a spaced repetition review answer.

Student: {name}
Topic: {topic}
Original learning: {learned}
Their answer now: {answer}

Did they remember it? Grade 1-5:
1 — Completely forgot
2 — Vague memory, mostly wrong
3 — Partial memory, key points missing
4 — Good recall, minor gaps
5 — Perfect recall, could teach it

Respond ONLY in this format:
SCORE: [1-5]
REMEMBERED: [yes/no — yes if score 3+]
FEEDBACK: [1 sentence, direct and a little playful]"""

    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
        )
        raw = response.choices[0].message.content.strip()
        result = {"score": 3, "remembered": True, "feedback": ""}
        for line in raw.split("\n"):
            if line.startswith("SCORE:"):
                try:
                    result["score"] = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("REMEMBERED:"):
                result["remembered"] = line.split(":", 1)[1].strip().lower() == "yes"
            elif line.startswith("FEEDBACK:"):
                result["feedback"] = line.split(":", 1)[1].strip()
        return result
    except Exception as e:
        log.error(f"Review grading error: {e}")
        return {"score": 3, "remembered": True, "feedback": "Could not grade — keep reviewing!"}


# ─── Format messages ──────────────────────────────────────────────────────────

def format_review_prompt(item: dict, question: str, name: str) -> str:
    studied = date.fromisoformat(item["studied_date"])
    days_ago = (date.today() - studied).days
    interval_label = {0: "3-day", 1: "7-day", 2: "14-day"}.get(
        item["interval_index"], "final"
    )

    return (
        f"🔁 <b>Spaced Review — {interval_label} check</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📌 Topic: <b>{item['topic']}</b>\n"
        f"📅 Studied: {days_ago} days ago ({item['studied_date']})\n\n"
        f"❓ {question}\n\n"
        f"<i>Answer below. /skipreview to skip this one.</i>"
    )


def format_review_result(item: dict, grade: dict, name: str) -> str:
    score = grade["score"]
    remembered = grade["remembered"]
    icons = {5: "🏆", 4: "⭐", 3: "👍", 2: "📖", 1: "💀"}
    icon = icons.get(score, "❓")

    if remembered:
        status = "✅ Still in your head!"
        next_msg = "Moving to next review interval."
    else:
        status = "❌ Fading — needs more practice."
        next_msg = "Scheduled for another review soon."

    return (
        f"{icon} <b>Review Result</b>\n\n"
        f"Score: {score}/5 — {status}\n"
        f"💬 {grade['feedback']}\n\n"
        f"<i>{next_msg}</i>"
    )
