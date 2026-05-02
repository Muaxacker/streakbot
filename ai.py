import os
from groq import Groq


def _get_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    return Groq(api_key=api_key)


def _ask(prompt: str) -> str:
    try:
        client = _get_client()
        if client is None:
            return "AI is not configured yet. Add GROQ_API_KEY to your .env file and restart the bot."
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
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
        f"KEY TOPICS\n"
        f"- {name1}: {learned1}\n"
        f"- {name2}: {learned2}\n\n"
        f"SUMMARY\n"
        f"{name1} focused on {learned1}. {name2} focused on {learned2}.\n\n"
        f"NEXT UP\n"
        f"- {name1}: {topic1}\n"
        f"- {name2}: {topic2}"
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


def _fallback_next_topic(topic1: str, topic2: str, name1: str, name2: str) -> str:
    return (
        f"PAIRING CHECK\n"
        f"Both topics can work well together — keep building small connected projects.\n\n"
        f"TIP FOR {name1.upper()}\n"
        f"- Stay focused on the core of: {topic1}\n\n"
        f"TIP FOR {name2.upper()}\n"
        f"- Stay focused on the core of: {topic2}\n\n"
        f"STUDY TOGETHER IDEA\n"
        f"- Build a tiny project where both topics appear in one workflow."
    )


def _fallback_milestone(streak: int, name1: str, name2: str) -> str:
    return (
        f"{name1} and {name2} just hit {streak} days straight.\n"
        f"That kind of consistency is rare. Most people quit before day 7.\n"
        f"You two are still here. Keep protecting the streak."
    )


# ─── AI functions ─────────────────────────────────────────────────────────────

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
(2 to 3 sentences — warm, direct, and a little playful. Acknowledge the effort. If one studied longer or tackled something harder, call it out with a light troll like "someone's putting in extra hours...")

CONNECTION
(1 sentence — how do their topics connect or complement each other? If they don't connect at all, say so honestly and suggest how they could link up tomorrow)

Rules:
- Be warm but not cheesy
- Light humor and personality are welcome — this is a fun accountability system between friends
- No markdown like ** or #
- Keep it under 200 words total"""

    result = _ask(prompt)
    if result.startswith("AI is temporarily unavailable"):
        return _fallback_daily_summary(report1, report2, name1, name2)
    return result


def generate_quiz_questions(report1: dict, report2: dict, name1: str, name2: str) -> list[dict]:
    """
    Generate 3 quiz questions as a structured list.
    Each item: { "question": str, "ideal_answer": str }
    """
    prompt = f"""You are StreakBot — a tough quiz master for two full stack web development students.

{name1} studied today: {report1.get('learned', 'not specified')}
{name2} studied today: {report2.get('learned', 'not specified')}

Generate exactly 3 quiz questions. Mix topics from both students.
Make them practical — expose whether they actually understood it, not just watched the video.
No easy "what is X" questions. Ask them to explain, apply, compare, or debug.

Respond ONLY in this exact format, no extra text:

Q1: [question]
A1: [ideal answer — 2 to 4 sentences, clear and specific]

Q2: [question]
A2: [ideal answer — 2 to 4 sentences, clear and specific]

Q3: [question]
A3: [ideal answer — 2 to 4 sentences, clear and specific]"""

    raw = _ask(prompt)
    return _parse_quiz_questions(raw)


def _parse_quiz_questions(raw: str) -> list[dict]:
    """Parse Q1/A1 format into a list of dicts."""
    questions = []
    lines = raw.strip().split("\n")
    current_q = None
    current_a = None
    for line in lines:
        line = line.strip()
        if line.startswith("Q") and ":" in line and line[1].isdigit():
            if current_q and current_a:
                questions.append({"question": current_q, "ideal_answer": current_a})
            current_q = line.split(":", 1)[1].strip()
            current_a = None
        elif line.startswith("A") and ":" in line and line[1].isdigit():
            current_a = line.split(":", 1)[1].strip()
    if current_q and current_a:
        questions.append({"question": current_q, "ideal_answer": current_a})

    # Fallback if parsing failed
    if not questions:
        questions = [
            {"question": "What did you study today and how would you explain it to a beginner?",
             "ideal_answer": "A clear explanation of the topic with an example."},
            {"question": "What was the hardest part of what you learned today and how did you work through it?",
             "ideal_answer": "Specific description of the challenge and the solution."},
            {"question": "How would you use what you learned today in a real project?",
             "ideal_answer": "A concrete use case or mini-project idea."},
        ]
    return questions[:3]


def grade_answer(question: str, ideal_answer: str, user_answer: str, name: str) -> dict:
    """
    Grade a user's answer against the ideal answer.
    Returns: { score: int (1-5), feedback: str, correct: bool }
    """
    prompt = f"""You are StreakBot grading a quiz answer for a full stack web development student named {name}.

Question: {question}

Ideal answer: {ideal_answer}

{name}'s answer: {user_answer}

Grade their answer from 1 to 5:
1 — Wrong or completely off topic
2 — Partially right but missing key points
3 — Mostly right, small gaps
4 — Good answer, covers the main points
5 — Excellent, complete and clear

Be direct and a little playful in your feedback. If they got it right, give them credit. If they missed something, call it out specifically.

Respond ONLY in this exact format:
SCORE: [1-5]
FEEDBACK: [2 sentences max — direct, specific, with personality]
CORRECT: [yes/no — yes if score is 3 or above]"""

    raw = _ask(prompt)
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


def generate_quiz(report1: dict, report2: dict, name1: str, name2: str) -> str:
    """Legacy function — kept for fallback use. Returns plain text quiz."""
    questions = generate_quiz_questions(report1, report2, name1, name2)
    lines = ["Alright, no Googling. Let's see if you actually learned anything today.", ""]
    for i, q in enumerate(questions, 1):
        lines.append(f"Q{i}: {q['question']}")
        lines.append(f"Answer: {q['ideal_answer']}")
        lines.append("")
    return "\n".join(lines)


def weekly_summary(reports_list: list, name1: str, name2: str) -> str:
    if not reports_list:
        return "No reports found for the past week. The weekly review needs data — start reporting daily!"

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

    prompt = f"""You are StreakBot — a sharp, motivating AI coach reviewing a week of learning for two full stack web development students.

Here are their daily reports from this week:
{reports_text}

Write a weekly review with exactly these 4 sections:

TOPICS COVERED THIS WEEK
(bullet list — every topic studied, grouped by person if they studied different things)

PROGRESS THIS WEEK
(2 to 3 sentences — honest assessment of how much they covered. If one person reported more days than the other, call it out. Be direct but not harsh.)

SUGGESTED FOCUS FOR NEXT WEEK
(1 to 2 specific topics they should tackle next, based on what they've done so far in the full stack journey)

MOTIVATION
(1 powerful sentence — make it hit. Not generic. Reference something specific from their week.)

Rules:
- Personality and light humor are welcome
- Be honest — if they had a weak week, say so and push them
- No markdown like ** or #
- Keep it under 250 words"""

    result = _ask(prompt)
    if result.startswith("AI is temporarily unavailable"):
        return _fallback_weekly_summary(reports_list, name1, name2)
    return result


def suggest_next_topic(topic1: str, topic2: str, name1: str, name2: str, history: str = "") -> str:
    history_text = f"Topics they've already covered: {history}" if history else ""

    prompt = f"""You are StreakBot — a practical, slightly sarcastic AI study advisor for two full stack web development students.

{name1} plans to study next: {topic1}
{name2} plans to study next: {topic2}
{history_text}

Give a short, useful response with exactly these 4 sections:

PAIRING CHECK
(Are their topics complementary? Do they fit together in the full stack journey? Be honest — if one person picked something random, say so.)

TIP FOR {name1.upper()}
(1 practical tip — specific, actionable, not generic advice like "practice a lot")

TIP FOR {name2.upper()}
(1 practical tip — specific, actionable)

STUDY TOGETHER IDEA
(1 mini-project or exercise they could do together that combines both their topics — make it concrete and buildable in a day)

Rules:
- Keep it short and punchy
- Light troll energy is welcome — these are friends pushing each other
- No markdown like ** or #"""

    result = _ask(prompt)
    if result.startswith("AI is temporarily unavailable"):
        return _fallback_next_topic(topic1, topic2, name1, name2)
    return result


def milestone_message(streak: int, name1: str, name2: str) -> str:
    prompt = f"""You are StreakBot — celebrating a major milestone for two full stack web development students.

{name1} and {name2} just hit a {streak}-day learning streak. They've submitted daily reports for {streak} consecutive days without missing a single one.

Write a short celebration message (4 to 6 sentences) that:
- Opens with genuine excitement — this is a real achievement
- Puts the {streak} days in perspective (most people quit in week 1)
- Throws in a light troll — something like "we didn't think you'd make it this far" or "the bot is actually impressed"
- Ends with a push toward the next milestone

Make it feel personal, energetic, and fun. Not corporate. Not generic.
No markdown like ** or #."""

    result = _ask(prompt)
    if result.startswith("AI is temporarily unavailable"):
        return _fallback_milestone(streak, name1, name2)
    return result


# ─── Fallbacks ────────────────────────────────────────────────────────────────

def _fallback_daily_summary(report1: dict, report2: dict, name1: str, name2: str) -> str:
    learned1 = report1.get("learned", "not specified")
    learned2 = report2.get("learned", "not specified")
    topic1 = report1.get("topic", "not specified")
    topic2 = report2.get("topic", "not specified")
    return (
        f"KEY TOPICS\n"
        f"- {name1}: {learned1}\n"
        f"- {name2}: {learned2}\n\n"
        f"SUMMARY\n"
        f"{name1} focused on {learned1}. {name2} focused on {learned2}.\n\n"
        f"NEXT UP\n"
        f"- {name1}: {topic1}\n"
        f"- {name2}: {topic2}"
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


def _fallback_quiz(report1: dict, report2: dict, name1: str, name2: str) -> str:
    topic1 = report1.get("learned", "your first topic")
    topic2 = report2.get("learned", "your second topic")
    return (
        f"Q1: What is one practical thing {name1} learned about {topic1}?\n"
        "Answer: Explain it in your own words with one real example.\n\n"
        f"Q2: What is one practical thing {name2} learned about {topic2}?\n"
        "Answer: Explain it in your own words with one real example.\n\n"
        "Q3: How can both of today's topics be combined in one small project?\n"
        "Answer: Describe a mini project that uses both ideas together."
    )


def _fallback_next_topic(topic1: str, topic2: str, name1: str, name2: str) -> str:
    return (
        f"PAIRING CHECK\n"
        f"Both topics can work well together — keep building small connected projects.\n\n"
        f"TIP FOR {name1.upper()}\n"
        f"- Stay focused on the core of: {topic1}\n\n"
        f"TIP FOR {name2.upper()}\n"
        f"- Stay focused on the core of: {topic2}\n\n"
        f"STUDY TOGETHER IDEA\n"
        f"- Build a tiny project where both topics appear in one workflow."
    )


def _fallback_milestone(streak: int, name1: str, name2: str) -> str:
    return (
        f"{name1} and {name2} just hit {streak} days straight.\n"
        f"That kind of consistency is rare. Most people quit before day 7.\n"
        f"You two are still here. Keep protecting the streak."
    )


# ─── AI functions ─────────────────────────────────────────────────────────────

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
(2 to 3 sentences — warm, direct, and a little playful. Acknowledge the effort. If one studied longer or tackled something harder, call it out with a light troll like "someone's putting in extra hours...")

CONNECTION
(1 sentence — how do their topics connect or complement each other? If they don't connect at all, say so honestly and suggest how they could link up tomorrow)

Rules:
- Be warm but not cheesy
- Light humor and personality are welcome — this is a fun accountability system between friends
- No markdown like ** or #
- Keep it under 200 words total"""

    result = _ask(prompt)
    if result.startswith("AI is temporarily unavailable"):
        return _fallback_daily_summary(report1, report2, name1, name2)
    return result


def generate_quiz(report1: dict, report2: dict, name1: str, name2: str) -> str:
    prompt = f"""You are StreakBot — a tough but fair quiz master for two full stack web development students.

{name1} studied today: {report1.get('learned', 'not specified')}
{name2} studied today: {report2.get('learned', 'not specified')}

Generate exactly 3 quiz questions. Mix topics from both students.
Make the questions practical — the kind that expose whether they actually understood it or just watched the video.
No easy "what is X" questions. Ask them to explain, apply, or debug.

Add a short troll intro line before the questions like:
"Alright, no Googling. Let's see if you actually learned anything today."

Format exactly like this:

[troll intro line]

Q1: [question]
Answer: [clear answer]

Q2: [question]
Answer: [clear answer]

Q3: [question]
Answer: [clear answer]

No extra text. No markdown."""

    result = _ask(prompt)
    if result.startswith("AI is temporarily unavailable"):
        return _fallback_quiz(report1, report2, name1, name2)
    return result


def weekly_summary(reports_list: list, name1: str, name2: str) -> str:
    if not reports_list:
        return "No reports found for the past week. The weekly review needs data — start reporting daily!"

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

    prompt = f"""You are StreakBot — a sharp, motivating AI coach reviewing a week of learning for two full stack web development students.

Here are their daily reports from this week:
{reports_text}

Write a weekly review with exactly these 4 sections:

TOPICS COVERED THIS WEEK
(bullet list — every topic studied, grouped by person if they studied different things)

PROGRESS THIS WEEK
(2 to 3 sentences — honest assessment of how much they covered. If one person reported more days than the other, call it out. Be direct but not harsh.)

SUGGESTED FOCUS FOR NEXT WEEK
(1 to 2 specific topics they should tackle next, based on what they've done so far in the full stack journey)

MOTIVATION
(1 powerful sentence — make it hit. Not generic. Reference something specific from their week.)

Rules:
- Personality and light humor are welcome
- Be honest — if they had a weak week, say so and push them
- No markdown like ** or #
- Keep it under 250 words"""

    result = _ask(prompt)
    if result.startswith("AI is temporarily unavailable"):
        return _fallback_weekly_summary(reports_list, name1, name2)
    return result


def suggest_next_topic(topic1: str, topic2: str, name1: str, name2: str, history: str = "") -> str:
    history_text = f"Topics they've already covered: {history}" if history else ""

    prompt = f"""You are StreakBot — a practical, slightly sarcastic AI study advisor for two full stack web development students.

{name1} plans to study next: {topic1}
{name2} plans to study next: {topic2}
{history_text}

Give a short, useful response with exactly these 4 sections:

PAIRING CHECK
(Are their topics complementary? Do they fit together in the full stack journey? Be honest — if one person picked something random, say so.)

TIP FOR {name1.upper()}
(1 practical tip — specific, actionable, not generic advice like "practice a lot")

TIP FOR {name2.upper()}
(1 practical tip — specific, actionable)

STUDY TOGETHER IDEA
(1 mini-project or exercise they could do together that combines both their topics — make it concrete and buildable in a day)

Rules:
- Keep it short and punchy
- Light troll energy is welcome — these are friends pushing each other
- No markdown like ** or #"""

    result = _ask(prompt)
    if result.startswith("AI is temporarily unavailable"):
        return _fallback_next_topic(topic1, topic2, name1, name2)
    return result


def milestone_message(streak: int, name1: str, name2: str) -> str:
    prompt = f"""You are StreakBot — celebrating a major milestone for two full stack web development students.

{name1} and {name2} just hit a {streak}-day learning streak. They've submitted daily reports for {streak} consecutive days without missing a single one.

Write a short celebration message (4 to 6 sentences) that:
- Opens with genuine excitement — this is a real achievement
- Puts the {streak} days in perspective (most people quit in week 1)
- Throws in a light troll — something like "we didn't think you'd make it this far" or "the bot is actually impressed"
- Ends with a push toward the next milestone

Make it feel personal, energetic, and fun. Not corporate. Not generic.
No markdown like ** or #."""

    result = _ask(prompt)
    if result.startswith("AI is temporarily unavailable"):
        return _fallback_milestone(streak, name1, name2)
    return result


def parse_report_text(text: str, name: str) -> dict:
    """
    Extract report fields from a free-text or voice-transcribed report.
    Returns: { learned, time_spent, difficulty, next_topic }
    All fields are strings; missing ones default to empty string.
    """
    prompt = f"""You are StreakBot extracting structured data from a student's daily learning report.

Student name: {name}
Their report (written or transcribed from voice):
\"\"\"{text}\"\"\"

Extract exactly these 4 fields:

LEARNED: [what they studied today — be specific, keep their own words where possible]
TIME_SPENT: [how long they studied — e.g. "2 hours", "45 minutes". If not mentioned, write "not specified"]
DIFFICULTY: [easy, medium, or hard — infer from their words if not stated directly. If unclear, write "medium"]
NEXT_TOPIC: [what they plan to study next — if not mentioned, write "not specified"]

Rules:
- Respond ONLY in the exact format above, one field per line
- Do not add explanations or extra text
- DIFFICULTY must be exactly one of: easy, medium, hard"""

    raw = _ask(prompt)
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
    prompt = f"""You are StreakBot detecting a potential burnout pattern for {name}.

Their study time dropped {drop_pct}% — from {prev_avg} hours/day to {recent_avg} hours/day over the last 3 days.

Write a short, caring but direct message (3-4 sentences) that:
- Acknowledges the drop without being harsh
- Suggests a lighter approach rather than quitting
- Reminds them that 30 focused minutes beats zero
- Keeps the tone warm and human, not robotic

No markdown. Keep it under 80 words."""

    result = _ask(prompt)
    if not result or result.startswith("AI is"):
        return (
            f"{name}, your study time has dropped {drop_pct}% this week. "
            "That's a burnout pattern — it happens. "
            "Don't skip entirely. Even 30 focused minutes keeps the momentum alive. "
            "Protect the streak, not the hours."
        )
    return result


def generate_struggle_reminder(name: str, struggles: list[str],
                                project_topic: str) -> str:
    struggles_str = ", ".join(struggles[:5])
    prompt = f"""You are StreakBot reminding {name} about their weak spots before a weekly project.

Topics they've struggled with: {struggles_str}
This week's project topic: {project_topic}

Write a short message (2-3 sentences) that:
- Points out which struggle topics are relevant to the project
- Encourages them to use the project as practice for those weak spots
- Has a light troll tone — friendly but direct

No markdown. Keep it under 60 words."""

    result = _ask(prompt)
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
    """
    Generate a personalized daily reminder using real data.
    Much more impactful than a generic message.
    """
    consistency_pct = round(days_reported / total_days * 100) if total_days else 0

    prompt = f"""You are StreakBot sending a personalized daily reminder to {name}.

Their real data:
- Current streak: {streak} days
- Reported {days_reported}/{total_days} days total ({consistency_pct}% consistency)
- Accountability score: {acc_score}/100
- Partner also hasn't reported yet: {missing_partner}

Write a 2-3 sentence reminder that:
- References their ACTUAL streak number (not generic)
- Uses their consistency % to either praise or push them
- If streak > 7: acknowledge the achievement and raise the stakes
- If streak < 3: be more urgent about building the habit
- Has personality — not robotic, not corporate
- Ends with a direct call to action: /report

No markdown. Keep it under 60 words."""

    result = _ask(prompt)
    if not result or result.startswith("AI is"):
        if streak >= 7:
            return (
                f"{name}, {streak} days straight. That's real. "
                f"Don't let today be the day it ends. "
                f"Use /report before midnight."
            )
        return (
            f"{name}, the streak is at {streak}. "
            f"Every day you report makes the next one easier. "
            f"Use /report now."
        )
    return result
