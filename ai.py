"""
ai.py — All Groq AI calls for StreakBot.

Every public function has a _fallback_* counterpart used when the API
is unavailable or rate-limited.
"""

import os
from groq import Groq


def _get_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    return Groq(api_key=api_key)


def _ask(prompt: str, max_tokens: int = 800) -> str:
    try:
        client = _get_client()
        if client is None:
            return "AI is not configured yet. Add GROQ_API_KEY to your .env file and restart the bot."
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        message = str(e)
        if "429" in message or "quota" in message.lower() or "rate limit" in message.lower():
            return "AI is temporarily unavailable because the Groq quota is exhausted. Please wait a minute and try again."
        return f"(AI unavailable: {e})"


# ─── Fallbacks ────────────────────────────────────────────────────────────────

def _fallback_daily_summary(report1: dict, report2: dict, name1: str, name2: str) -> str:
    learned1 = report1.get("learned", "not specified")
    learned2 = report2.get("learned", "not specified")
    topic1 = report1.get("topic", "not specified")
    topic2 = report2.get("topic", "not specified")
    return (
        f"KEY TOPICS\n- {name1}: {learned1}\n- {name2}: {learned2}\n\n"
        f"SUMMARY\n{name1} focused on {learned1}. {name2} focused on {learned2}.\n\n"
        f"NEXT UP\n- {name1}: {topic1}\n- {name2}: {topic2}"
    )


def _fallback_weekly_summary(reports_list: list, name1: str, name2: str) -> str:
    lines = ["TOPICS COVERED THIS WEEK", ""]
    for entry in reports_list:
        day = entry.get("date", "unknown date")
        lines.append(day)
        for uid, label in entry.items():
            if uid == "date" or not isinstance(label, dict):
                continue
            name = name1 if uid == list(entry.keys())[1] else name2
            lines.append(f"- {name}: {label.get('learned', 'not specified')}")
        lines.append("")
    lines.extend([
        "PROGRESS THIS WEEK",
        f"{name1} and {name2} both put in work this week.",
        "Keep the daily reports coming — the AI review gets richer every week.",
    ])
    return "\n".join(lines)


def _fallback_quiz(report1: dict, report2: dict, name1: str, name2: str) -> list[dict]:
    topic1 = report1.get("learned", "your first topic")
    topic2 = report2.get("learned", "your second topic")
    return [
        {"question": f"Explain what {name1} studied today ({topic1}) in your own words with one example.",
         "ideal_answer": "A clear explanation of the topic with a concrete example."},
        {"question": f"Explain what {name2} studied today ({topic2}) in your own words with one example.",
         "ideal_answer": "A clear explanation of the topic with a concrete example."},
        {"question": "How could both of today's topics be combined in one small project?",
         "ideal_answer": "A mini project that uses both ideas together."},
    ]


def _fallback_next_topic(topic1: str, topic2: str, name1: str, name2: str) -> str:
    return (
        f"PAIRING CHECK\nBoth topics can work well together — keep building small connected projects.\n\n"
        f"TIP FOR {name1.upper()}\n- Stay focused on the core of: {topic1}\n\n"
        f"TIP FOR {name2.upper()}\n- Stay focused on the core of: {topic2}\n\n"
        f"STUDY TOGETHER IDEA\n- Build a tiny project where both topics appear in one workflow."
    )


def _fallback_milestone(streak: int, name1: str, name2: str) -> str:
    return (
        f"{name1} and {name2} just hit {streak} days straight.\n"
        f"That kind of consistency is rare. Most people quit before day 7.\n"
        f"You two are still here. Keep protecting the streak."
    )


# ─── Public AI functions ──────────────────────────────────────────────────────

def summarize_reports(report1: dict, report2: dict, name1: str, name2: str) -> str:
    prompt = f"""You are StreakBot — a sharp, witty, and genuinely motivating AI coach for two full stack web development students learning together.

{name1} reported today:
- Studied: {report1.get('learned', 'not specified')}
- Next topic: {report1.get('topic', 'not specified')}
- Time spent: {report1.get('time_spent', 'not specified')}
- Difficulty: {report1.get('difficulty', 'not specified')}

{name2} reported today:
- Studied: {report2.get('learned', 'not specified')}
- Next topic: {report2.get('topic', 'not specified')}
- Time spent: {report2.get('time_spent', 'not specified')}
- Difficulty: {report2.get('difficulty', 'not specified')}

Write a daily learning summary with exactly these 3 sections:

KEY TOPICS
(3 to 5 bullet points — the most important things they covered today, be specific)

SUMMARY
(2 to 3 sentences — warm, direct, and a little playful. If one studied longer or tackled something harder, call it out.)

CONNECTION
(1 sentence — how do their topics connect? If they don't, say so and suggest how they could link up tomorrow.)

Rules: warm but not cheesy, light humor welcome, no markdown like ** or #, under 200 words."""

    result = _ask(prompt)
    if result.startswith("AI is temporarily unavailable"):
        return _fallback_daily_summary(report1, report2, name1, name2)
    return result


def generate_quiz_questions(report1: dict, report2: dict, name1: str, name2: str) -> list[dict]:
    """Generate 3 quiz questions. Returns [{ question, ideal_answer }]."""
    prompt = f"""You are StreakBot — a tough quiz master for two full stack web development students.

{name1} studied today: {report1.get('learned', 'not specified')}
{name2} studied today: {report2.get('learned', 'not specified')}

Generate exactly 3 quiz questions. Mix topics from both students.
Make them practical — expose whether they actually understood it, not just watched the video.
No easy "what is X" questions. Ask them to explain, apply, compare, or debug.

Respond ONLY in this exact format:

Q1: [question]
A1: [ideal answer — 2 to 4 sentences, clear and specific]

Q2: [question]
A2: [ideal answer — 2 to 4 sentences, clear and specific]

Q3: [question]
A3: [ideal answer — 2 to 4 sentences, clear and specific]"""

    raw = _ask(prompt)
    return _parse_quiz_questions(raw, report1, report2, name1, name2)


def _parse_quiz_questions(raw: str, report1: dict = None, report2: dict = None,
                           name1: str = "", name2: str = "") -> list[dict]:
    questions = []
    current_q = current_a = None
    for line in raw.strip().split("\n"):
        line = line.strip()
        if line.startswith("Q") and ":" in line and len(line) > 1 and line[1].isdigit():
            if current_q and current_a:
                questions.append({"question": current_q, "ideal_answer": current_a})
            current_q = line.split(":", 1)[1].strip()
            current_a = None
        elif line.startswith("A") and ":" in line and len(line) > 1 and line[1].isdigit():
            current_a = line.split(":", 1)[1].strip()
    if current_q and current_a:
        questions.append({"question": current_q, "ideal_answer": current_a})

    if not questions and report1 is not None:
        return _fallback_quiz(report1, report2 or {}, name1, name2)
    return questions[:3]


def grade_answer(question: str, ideal_answer: str, user_answer: str, name: str) -> dict:
    """Grade a quiz answer 1-5. Returns { score, feedback, correct }."""
    prompt = f"""You are StreakBot grading a quiz answer for {name}.

Question: {question}
Ideal answer: {ideal_answer}
{name}'s answer: {user_answer}

Grade 1-5:
1 — Wrong or off topic
2 — Partially right, missing key points
3 — Mostly right, small gaps
4 — Good answer, covers main points
5 — Excellent, complete and clear

Respond ONLY in this format:
SCORE: [1-5]
FEEDBACK: [2 sentences max — direct, specific, with personality]
CORRECT: [yes/no — yes if score is 3 or above]"""

    raw = _ask(prompt, max_tokens=200)
    return _parse_grade(raw)


def _parse_grade(raw: str) -> dict:
    result = {"score": 0, "feedback": "Could not grade this answer.", "correct": False}
    for line in raw.strip().split("\n"):
        if line.startswith("SCORE:"):
            try:
                result["score"] = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("FEEDBACK:"):
            result["feedback"] = line.split(":", 1)[1].strip()
        elif line.startswith("CORRECT:"):
            result["correct"] = line.split(":", 1)[1].strip().lower() == "yes"
    return result


def weekly_summary(reports_list: list, name1: str, name2: str) -> str:
    if not reports_list:
        return "No reports found for the past week. Start reporting daily!"

    reports_text = ""
    for entry in reports_list:
        day = entry.get("date", "unknown date")
        reports_text += f"\n{day}:\n"
        for uid, report in entry.items():
            if uid == "date":
                continue
            if isinstance(report, dict):
                name = name1 if uid == list(entry.keys())[1] else name2
                reports_text += f"  {name}: {report.get('learned', '-')}\n"

    prompt = f"""You are StreakBot reviewing a week of learning for two full stack web development students.

Reports:
{reports_text}

Write a weekly review with exactly these 4 sections:

TOPICS COVERED THIS WEEK
(bullet list — every topic studied)

PROGRESS THIS WEEK
(2 to 3 sentences — honest. If one reported more days, call it out.)

SUGGESTED FOCUS FOR NEXT WEEK
(1 to 2 specific topics based on what they've done)

MOTIVATION
(1 powerful sentence — reference something specific from their week)

Rules: personality and light humor welcome, honest, no markdown, under 250 words."""

    result = _ask(prompt)
    if result.startswith("AI is temporarily unavailable"):
        return _fallback_weekly_summary(reports_list, name1, name2)
    return result


def suggest_next_topic(topic1: str, topic2: str, name1: str, name2: str, history: str = "") -> str:
    history_text = f"Topics already covered: {history}" if history else ""
    prompt = f"""You are StreakBot — a practical, slightly sarcastic AI study advisor.

{name1} plans to study: {topic1}
{name2} plans to study: {topic2}
{history_text}

Respond with exactly these 4 sections:

PAIRING CHECK
(Are their topics complementary? Be honest.)

TIP FOR {name1.upper()}
(1 specific, actionable tip)

TIP FOR {name2.upper()}
(1 specific, actionable tip)

STUDY TOGETHER IDEA
(1 concrete mini-project combining both topics, buildable in a day)

Rules: short and punchy, light troll energy welcome, no markdown."""

    result = _ask(prompt)
    if result.startswith("AI is temporarily unavailable"):
        return _fallback_next_topic(topic1, topic2, name1, name2)
    return result


def milestone_message(streak: int, name1: str, name2: str) -> str:
    prompt = f"""You are StreakBot celebrating a milestone for {name1} and {name2}.

They just hit a {streak}-day learning streak — {streak} consecutive days of reports.

Write a short celebration (4 to 6 sentences) that:
- Opens with genuine excitement
- Puts {streak} days in perspective (most people quit before day 7)
- Throws in a light troll — "we didn't think you'd make it this far"
- Ends with a push toward the next milestone

Personal, energetic, fun. No markdown."""

    result = _ask(prompt)
    if result.startswith("AI is temporarily unavailable"):
        return _fallback_milestone(streak, name1, name2)
    return result


def parse_report_text(text: str, name: str) -> dict:
    """Extract report fields from free text or voice transcript."""
    prompt = f"""You are StreakBot extracting data from {name}'s daily learning report.

Report:
\"\"\"{text}\"\"\"

Extract exactly these 4 fields:

LEARNED: [what they studied — keep their own words]
TIME_SPENT: [how long — e.g. "2 hours". If not mentioned: "not specified"]
DIFFICULTY: [easy, medium, or hard — infer if not stated. If unclear: "medium"]
NEXT_TOPIC: [what they plan next — if not mentioned: "not specified"]

Respond ONLY in the exact format above. DIFFICULTY must be: easy, medium, or hard."""

    raw = _ask(prompt, max_tokens=200)
    return _parse_report_fields(raw)


def _parse_report_fields(raw: str) -> dict:
    result = {
        "learned": "",
        "time_spent": "not specified",
        "difficulty": "medium",
        "next_topic": "not specified",
    }
    for line in raw.strip().split("\n"):
        if line.startswith("LEARNED:"):
            result["learned"] = line.split(":", 1)[1].strip()
        elif line.startswith("TIME_SPENT:"):
            result["time_spent"] = line.split(":", 1)[1].strip()
        elif line.startswith("DIFFICULTY:"):
            val = line.split(":", 1)[1].strip().lower()
            result["difficulty"] = val if val in ("easy", "medium", "hard") else "medium"
        elif line.startswith("NEXT_TOPIC:"):
            result["next_topic"] = line.split(":", 1)[1].strip()
    return result


def generate_burnout_message(name: str, drop_pct: int,
                              recent_avg: float, prev_avg: float) -> str:
    prompt = f"""You are StreakBot. {name}'s study time dropped {drop_pct}% — from {prev_avg}h/day to {recent_avg}h/day.

Write a short, caring but direct message (3-4 sentences):
- Acknowledge the drop without being harsh
- Suggest a lighter approach rather than quitting
- Remind them 30 focused minutes beats zero
- Warm and human, not robotic

No markdown. Under 80 words."""

    result = _ask(prompt, max_tokens=150)
    if not result or result.startswith("AI is"):
        return (
            f"{name}, your study time has dropped {drop_pct}% this week. "
            "That's a burnout pattern — it happens. "
            "Don't skip entirely. Even 30 focused minutes keeps the momentum alive. "
            "Protect the streak, not the hours."
        )
    return result


def generate_struggle_reminder(name: str, struggles: list[str], project_topic: str) -> str:
    struggles_str = ", ".join(struggles[:5])
    prompt = f"""You are StreakBot reminding {name} about their weak spots before a weekly project.

Struggles: {struggles_str}
Project topic: {project_topic}

Write 2-3 sentences: point out relevant struggles, encourage using the project to practice them.
Light troll tone. No markdown. Under 60 words."""

    result = _ask(prompt, max_tokens=100)
    if not result or result.startswith("AI is"):
        return (
            f"{name}, you've marked {struggles_str} as struggles. "
            f"This week's project is your chance to practice them. "
            "Don't avoid the hard parts — that's exactly where the growth is."
        )
    return result


def generate_personalized_reminder(name: str, streak: int, days_reported: int,
                                    total_days: int, acc_score: int,
                                    missing_partner: bool) -> str:
    consistency_pct = round(days_reported / total_days * 100) if total_days else 0
    prompt = f"""You are StreakBot sending a personalized daily reminder to {name}.

Data:
- Streak: {streak} days
- Reported {days_reported}/{total_days} days ({consistency_pct}% consistency)
- Accountability score: {acc_score}/100
- Partner also hasn't reported: {missing_partner}

Write 2-3 sentences:
- Reference their actual streak number
- Use consistency % to praise or push
- streak > 7: acknowledge and raise stakes. streak < 3: be urgent
- Has personality, ends with /report

No markdown. Under 60 words."""

    result = _ask(prompt, max_tokens=100)
    if not result or result.startswith("AI is"):
        if streak >= 7:
            return (
                f"{name}, {streak} days straight. That's real. "
                f"Don't let today be the day it ends. Use /report before midnight."
            )
        return (
            f"{name}, the streak is at {streak}. "
            f"Every day you report makes the next one easier. Use /report now."
        )
    return result


def analyze_speaking(transcript: str, name: str, duration: int) -> dict:
    """
    Full English speaking analysis for interview preparation.
    Returns a structured dict with all analysis sections.
    """
    words = transcript.split()
    word_count = len(words)
    words_per_minute = round(word_count / (duration / 60)) if duration > 0 else 0

    prompt = f"""You are an expert English speaking coach helping {name} improve their spoken English for technical job interviews.

They spoke for {duration} seconds ({word_count} words, ~{words_per_minute} words/minute).

Transcription of what they said:
\"\"\"{transcript}\"\"\"

Analyze their speaking across ALL of these areas. Be specific — reference their actual words, not generic advice.

GRAMMAR
List up to 3 grammar mistakes found. For each: show the wrong version, then the correct version.
Format: "Said: [wrong] → Should be: [correct] — [brief reason]"
If no mistakes: write "No grammar errors found."

VOCABULARY
List up to 3 weak or repeated words with better alternatives.
Format: "[word used] → better: [alternatives] — [why it's stronger]"
If vocabulary is strong: write "Vocabulary is solid."

FILLER WORDS
List any filler words or phrases found (um, uh, like, you know, basically, kind of, sort of, I mean).
Count how many times each appeared.
If none: write "No filler words detected — clean delivery."

CLARITY
Rate their sentence structure: Clear / Mostly clear / Needs work
Note any incomplete thoughts, run-on sentences, or confusing phrasing.

FLUENCY SCORE
Give a score from 1 to 10.
1-3: Very broken, hard to follow
4-5: Basic, many gaps
6-7: Conversational, some rough edges
8-9: Smooth and confident
10: Native-level fluency

SPEAKING PACE
{words_per_minute} words/minute. Comment on whether this is too fast, too slow, or ideal for an interview.
Ideal interview pace: 120-150 words/minute.

INTERVIEW READINESS
Would this answer impress a technical interviewer? Rate: Not ready / Needs work / Acceptable / Strong / Excellent
Give 1 sentence of honest feedback.

ONE DRILL
Give ONE specific exercise they should practice daily to fix their biggest weakness.
Make it concrete and doable in 5 minutes.

Respond ONLY in the exact format above with these exact section headers. Be direct and honest — this person wants to improve, not be flattered."""

    raw = _ask(prompt, max_tokens=900)
    return _parse_speaking_analysis(raw, words_per_minute)


def _parse_speaking_analysis(raw: str, wpm: int) -> dict:
    """Parse the structured speaking analysis response."""
    sections = {
        "grammar": "",
        "vocabulary": "",
        "filler_words": "",
        "clarity": "",
        "fluency_score": "",
        "speaking_pace": "",
        "interview_readiness": "",
        "one_drill": "",
        "wpm": wpm,
        "raw": raw,
    }

    current_section = None
    lines_buffer = []

    section_map = {
        "GRAMMAR": "grammar",
        "VOCABULARY": "vocabulary",
        "FILLER WORDS": "filler_words",
        "CLARITY": "clarity",
        "FLUENCY SCORE": "fluency_score",
        "SPEAKING PACE": "speaking_pace",
        "INTERVIEW READINESS": "interview_readiness",
        "ONE DRILL": "one_drill",
    }

    for line in raw.strip().split("\n"):
        stripped = line.strip()
        matched = False
        for header, key in section_map.items():
            if stripped.upper().startswith(header):
                if current_section and lines_buffer:
                    sections[current_section] = "\n".join(lines_buffer).strip()
                current_section = key
                lines_buffer = []
                # Capture inline content after the header
                after = stripped[len(header):].lstrip(": ").strip()
                if after:
                    lines_buffer.append(after)
                matched = True
                break
        if not matched and current_section and stripped:
            lines_buffer.append(stripped)

    if current_section and lines_buffer:
        sections[current_section] = "\n".join(lines_buffer).strip()

    return sections


def format_speaking_analysis(name: str, transcript: str,
                              duration: int, analysis: dict) -> str:
    """Format the full speaking analysis as a Telegram HTML message."""
    wpm = analysis.get("wpm", 0)
    word_count = len(transcript.split())

    # Fluency score emoji
    score_text = analysis.get("fluency_score", "")
    score_num = 0
    for part in score_text.split():
        try:
            score_num = int(part)
            break
        except ValueError:
            continue

    score_emoji = (
        "🏆" if score_num >= 9 else
        "⭐" if score_num >= 7 else
        "👍" if score_num >= 5 else
        "📖" if score_num >= 3 else "💀"
    )

    lines = [
        f"🎙 <b>Speaking Analysis — {name}</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"⏱ {duration}s  |  📝 {word_count} words  |  🚀 {wpm} wpm",
        "",
    ]

    if analysis.get("fluency_score"):
        lines += [
            f"{score_emoji} <b>Fluency Score</b>",
            analysis["fluency_score"],
            "",
        ]

    if analysis.get("interview_readiness"):
        lines += [
            "💼 <b>Interview Readiness</b>",
            analysis["interview_readiness"],
            "",
        ]

    if analysis.get("grammar"):
        lines += [
            "📝 <b>Grammar</b>",
            analysis["grammar"],
            "",
        ]

    if analysis.get("vocabulary"):
        lines += [
            "💬 <b>Vocabulary</b>",
            analysis["vocabulary"],
            "",
        ]

    if analysis.get("filler_words"):
        lines += [
            "🔇 <b>Filler Words</b>",
            analysis["filler_words"],
            "",
        ]

    if analysis.get("clarity"):
        lines += [
            "🔍 <b>Clarity</b>",
            analysis["clarity"],
            "",
        ]

    if analysis.get("speaking_pace"):
        lines += [
            "⚡ <b>Speaking Pace</b>",
            analysis["speaking_pace"],
            "",
        ]

    if analysis.get("one_drill"):
        lines += [
            "🎯 <b>Daily Drill (5 min)</b>",
            analysis["one_drill"],
            "",
        ]

    lines.append("<i>Use /voicetranscript again to practice and track improvement.</i>")

    return "\n".join(lines)
