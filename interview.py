"""
interview.py — Feature 4: Interview Prep Mode

Every Friday after the weekly project, the bot sends 3 interview-style
questions based on everything studied that week.

Also available on demand via /interview command.

Questions are real interview questions — not quiz questions.
They test depth of understanding, not just recall.
"""

import logging
import os
from datetime import date

from groq import Groq

log = logging.getLogger(__name__)


def _ask(prompt: str, max_tokens: int = 600) -> str:
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        log.error(f"Interview AI error: {e}")
        return None


# ─── Generate interview questions ─────────────────────────────────────────────

def generate_interview_questions(topics: list[str], name: str) -> list[dict]:
    """
    Generate 3 real interview questions based on topics studied.
    Returns: [{ question, what_interviewer_wants, difficulty }]
    """
    topics_str = ", ".join(topics[:8])  # cap at 8 topics

    prompt = f"""You are a senior full stack developer conducting a technical interview for {name}, a bootcamp student who has been studying: {topics_str}.

Generate exactly 3 interview questions. These must be REAL interview questions — the kind asked at actual tech companies.

Rules:
- No "what is X" questions — those are too easy
- Ask them to explain trade-offs, debug scenarios, design decisions, or real-world applications
- Mix difficulty: 1 medium, 1 hard, 1 medium-hard
- Questions should be specific to what they studied, not generic

Format EXACTLY like this:

Q1: [question]
WANTS: [what the interviewer is really testing — 1 sentence]
DIFFICULTY: [medium/hard]

Q2: [question]
WANTS: [what the interviewer is really testing — 1 sentence]
DIFFICULTY: [medium/hard]

Q3: [question]
WANTS: [what the interviewer is really testing — 1 sentence]
DIFFICULTY: [medium/hard]

No extra text."""

    raw = _ask(prompt)
    if not raw:
        return _fallback_questions(topics_str)
    return _parse_interview_questions(raw)


def _parse_interview_questions(raw: str) -> list[dict]:
    questions = []
    current = {}
    for line in raw.strip().split("\n"):
        line = line.strip()
        if line.startswith("Q") and ":" in line and line[1].isdigit():
            if current:
                questions.append(current)
            current = {"question": line.split(":", 1)[1].strip(), "wants": "", "difficulty": "medium"}
        elif line.startswith("WANTS:"):
            current["wants"] = line.split(":", 1)[1].strip()
        elif line.startswith("DIFFICULTY:"):
            current["difficulty"] = line.split(":", 1)[1].strip().lower()
    if current:
        questions.append(current)

    if not questions:
        return _fallback_questions("full stack development")
    return questions[:3]


def _fallback_questions(topics: str) -> list[dict]:
    return [
        {
            "question": f"You're building a feature using {topics.split(',')[0] if topics else 'JavaScript'}. Walk me through how you'd approach it from scratch — what decisions would you make and why?",
            "wants": "Problem-solving process and decision-making",
            "difficulty": "medium"
        },
        {
            "question": "Tell me about a bug you encountered while studying recently. How did you find it and fix it?",
            "wants": "Debugging skills and persistence",
            "difficulty": "medium"
        },
        {
            "question": "If you had to explain what you've learned in the last week to a non-technical person, what would you say? Then explain it technically.",
            "wants": "Communication skills and depth of understanding",
            "difficulty": "medium"
        },
    ]


# ─── Grade interview answer ───────────────────────────────────────────────────

def grade_interview_answer(question: str, wants: str,
                            answer: str, name: str) -> dict:
    """
    Grade an interview answer like a real interviewer would.
    Returns: { score: 1-5, hire_signal: str, feedback: str, what_was_missing: str }
    """
    prompt = f"""You are a senior developer interviewing {name} for a junior full stack developer position.

Question asked: {question}
What you're testing: {wants}
Their answer: {answer}

Grade their answer as a real interviewer would. Be honest — this is practice for the real thing.

Score 1-5:
1 — Would not proceed with this candidate
2 — Weak answer, significant gaps
3 — Acceptable, would ask follow-up questions
4 — Good answer, shows real understanding
5 — Strong answer, would move to next round

Respond ONLY in this format:
SCORE: [1-5]
HIRE_SIGNAL: [would_not_hire / maybe / likely_hire / strong_hire]
FEEDBACK: [2 sentences — what they did well and what was missing, like a real interviewer]
MISSING: [the one most important thing they didn't cover]"""

    raw = _ask(prompt, max_tokens=300)
    if not raw:
        return {
            "score": 3,
            "hire_signal": "maybe",
            "feedback": "Could not grade — keep practicing.",
            "missing": "Unknown"
        }

    result = {"score": 3, "hire_signal": "maybe", "feedback": "", "missing": ""}
    for line in raw.strip().split("\n"):
        if line.startswith("SCORE:"):
            try:
                result["score"] = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("HIRE_SIGNAL:"):
            result["hire_signal"] = line.split(":", 1)[1].strip()
        elif line.startswith("FEEDBACK:"):
            result["feedback"] = line.split(":", 1)[1].strip()
        elif line.startswith("MISSING:"):
            result["missing"] = line.split(":", 1)[1].strip()
    return result


# ─── Format messages ──────────────────────────────────────────────────────────

def format_question_card(q: dict, index: int, total: int) -> str:
    diff_icon = "🔴" if q["difficulty"] == "hard" else "🟡"
    return (
        f"💼 <b>Interview Question {index} of {total}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{diff_icon} <b>Difficulty:</b> {q['difficulty'].title()}\n\n"
        f"<b>{q['question']}</b>\n\n"
        f"<i>Answer as if you're in a real interview. Be specific.\n"
        f"Type /skipinterview to skip.</i>"
    )


def format_grade_card(q: dict, grade: dict, name: str) -> str:
    score = grade["score"]
    signal = grade["hire_signal"]

    signal_display = {
        "would_not_hire": "❌ Would not proceed",
        "maybe": "🤔 Maybe — needs follow-up",
        "likely_hire": "✅ Likely hire",
        "strong_hire": "🏆 Strong hire signal",
    }.get(signal, signal)

    score_icons = {5: "🏆", 4: "⭐", 3: "👍", 2: "📖", 1: "❌"}
    icon = score_icons.get(score, "❓")

    lines = [
        f"{icon} <b>Interviewer's Verdict: {score}/5</b>",
        f"📋 {signal_display}",
        "",
        f"💬 {grade['feedback']}",
    ]
    if grade["missing"] and score < 5:
        lines.append(f"\n📝 <b>What was missing:</b> {grade['missing']}")

    return "\n".join(lines)


def format_session_summary(name: str, scores: list[int],
                            questions: list[dict]) -> str:
    total = sum(scores)
    max_score = len(scores) * 5
    pct = round(total / max_score * 100) if max_score else 0

    bar_filled = round(pct / 10)
    bar = "█" * bar_filled + "░" * (10 - bar_filled)

    if pct >= 80:
        verdict = "🏆 Strong performance. You're interview-ready for these topics."
        readiness = "Interview Ready"
    elif pct >= 60:
        verdict = "⭐ Solid. A few gaps but you'd get to the next round."
        readiness = "Getting There"
    elif pct >= 40:
        verdict = "📖 Needs work. Study the topics you struggled with before your real interview."
        readiness = "Needs Practice"
    else:
        verdict = "💀 Not ready yet. These topics need more depth before you interview."
        readiness = "Not Ready"

    lines = [
        f"💼 <b>Interview Prep Complete — {name}</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"Score: <b>{total}/{max_score}</b>  ({pct}%)",
        f"{bar}",
        f"Readiness: <b>{readiness}</b>",
        "",
    ]

    for i, (q, s) in enumerate(zip(questions, scores), 1):
        icon = {5: "🏆", 4: "⭐", 3: "👍", 2: "📖", 1: "❌", 0: "⏭"}.get(s, "❓")
        diff = "🔴" if q.get("difficulty") == "hard" else "🟡"
        lines.append(f"{icon} Q{i} {diff}: {q['question'][:50]}... — {s}/5")

    lines += ["", verdict]
    return "\n".join(lines)


# ─── Weekly trigger ───────────────────────────────────────────────────────────

def should_send_weekly_interview() -> bool:
    """Returns True if today is Friday."""
    return date.today().weekday() == 4  # 4 = Friday


def get_weekly_topics(user1_id: int, user2_id: int) -> list[str]:
    """Get all topics studied this week by both users."""
    import storage
    reports = storage.get_reports_for_days(7)
    topics = []
    for entry in reports:
        for uid in [str(user1_id), str(user2_id)]:
            rep = entry.get(uid, {})
            if isinstance(rep, dict):
                if rep.get("learned"):
                    topics.append(rep["learned"])
                if rep.get("topic"):
                    topics.append(rep["topic"])
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for t in topics:
        if t not in seen and t != "not specified":
            seen.add(t)
            unique.append(t)
    return unique[:8]
