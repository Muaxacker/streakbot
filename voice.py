"""
voice.py — Phase 1: Voice explanation handler

When a user sends a voice note to the bot:
1. Download the voice file from Telegram
2. Transcribe it using Groq Whisper (free, fast)
3. Score the explanation quality 1-10 using Groq LLM
4. Post results publicly in the group

Install: pip install groq
"""

import os
import logging
import tempfile
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

MIN_DURATION_SECONDS = 60  # voice must be at least 60 seconds


def _get_client() -> Groq:
    return Groq(api_key=os.getenv("GROQ_API_KEY"))


# ─── Transcribe ───────────────────────────────────────────────────────────────

async def transcribe_voice(file_path: str) -> str:
    """
    Send an audio file to Groq Whisper and return the transcript.
    file_path: local path to the downloaded .ogg voice file
    """
    try:
        client = _get_client()
        with open(file_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=("voice.ogg", f, "audio/ogg"),
                response_format="text"
            )
        return transcription.strip()
    except Exception as e:
        log.error(f"Transcription error: {e}")
        return None


# ─── Score explanation ─────────────────────────────────────────────────────────

def score_explanation(transcript: str, topic: str, name: str) -> dict:
    """
    Use Groq LLM to score the voice explanation.
    Returns dict with: score, feedback, key_points, missing
    """
    prompt = f"""You are StreakBot — a sharp, honest AI evaluating a student's voice explanation of what they learned today in full stack web development.

Student: {name}
Topic they studied: {topic}
Their spoken explanation (transcribed from voice):
\"\"\"{transcript}\"\"\"

Score their explanation from 1 to 10:
- Clarity: Can they explain it simply?
- Depth: Do they go beyond just naming the topic?
- Examples: Do they give concrete code examples or real use cases?
- Understanding: Do they show they actually get it, not just memorized it?

Scoring guide:
1-2: Just said the topic name, nothing else
3-4: Very vague, no real explanation
5-6: Basic understanding, some details but shallow
7-8: Good explanation with examples
9-10: Could teach this to someone else

Respond ONLY in this exact format, no extra text:
SCORE: [number 1-10]
FEEDBACK: [2 sentences of specific, direct feedback addressing {name} by name]
KEY POINTS: [bullet list of what they explained well, max 3 points — or "Nothing stood out" if score is below 4]
MISSING: [the one most important thing they left out — or "Nothing major" if score is 8+]"""

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
        )
        raw = response.choices[0].message.content.strip()
        return _parse_score_response(raw)
    except Exception as e:
        log.error(f"Scoring error: {e}")
        return {
            "score": 0,
            "feedback": "AI scoring unavailable right now.",
            "key_points": "",
            "missing": ""
        }


def _parse_score_response(raw: str) -> dict:
    """Parse the structured AI response."""
    result = {"score": 0, "feedback": "", "key_points": "", "missing": ""}
    for line in raw.split("\n"):
        if line.startswith("SCORE:"):
            try:
                result["score"] = int(line.replace("SCORE:", "").strip())
            except ValueError:
                result["score"] = 0
        elif line.startswith("FEEDBACK:"):
            result["feedback"] = line.replace("FEEDBACK:", "").strip()
        elif line.startswith("KEY POINTS:"):
            result["key_points"] = line.replace("KEY POINTS:", "").strip()
        elif line.startswith("MISSING:"):
            result["missing"] = line.replace("MISSING:", "").strip()
    return result


# ─── Score to emoji ────────────────────────────────────────────────────────────

def score_emoji(score: int) -> str:
    if score >= 9: return "🏆"
    if score >= 7: return "⭐"
    if score >= 5: return "👍"
    if score >= 3: return "📖"
    return "💀"


def score_label(score: int) -> str:
    if score >= 9: return "Exceptional — you could teach this"
    if score >= 7: return "Solid explanation"
    if score >= 5: return "Decent — could go deeper"
    if score >= 3: return "Surface level — try again"
    return "That was not an explanation 😬"


def score_troll(score: int, name: str) -> str:
    if score >= 9:
        return f"Okay {name}, the bot is actually impressed. Don't let it go to your head. 👀"
    if score >= 7:
        return f"Good job {name}. Your partner better step up now."
    if score >= 5:
        return f"{name}, you know more than you explained. Next time go deeper."
    if score >= 3:
        return f"Come on {name}... you watched the video. We know you did. Explain it properly."
    return f"{name}, was that an explanation or a prayer? 😂 Try again with more detail."


# ─── Format group message ─────────────────────────────────────────────────────

def format_voice_result(name: str, topic: str, transcript: str,
                         score_data: dict, duration: int) -> str:
    score = score_data["score"]
    emoji = score_emoji(score)
    label = score_label(score)
    troll = score_troll(score, name)

    lines = [
        f"🎙 <b>Voice Explanation — {name}</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"📌 Topic: {topic}",
        f"⏱ Duration: {duration}s",
        "",
        f"{emoji} <b>Score: {score}/10</b> — {label}",
        "",
        f"💬 <b>Feedback:</b> {score_data['feedback']}",
    ]

    if score_data["key_points"]:
        lines.append(f"✅ <b>Strengths:</b> {score_data['key_points']}")

    if score_data["missing"] and score_data["missing"] != "Nothing major":
        lines.append(f"📝 <b>Add next time:</b> {score_data['missing']}")

    lines.append("")
    lines.append(f"<i>🤖 {troll}</i>")
    lines.append("")
    lines.append(
        f"<i>Transcript: {transcript[:200]}{'...' if len(transcript) > 200 else ''}</i>"
    )

    return "\n".join(lines)


# ─── Partner Voice Comparison ─────────────────────────────────────────────────

def compare_explanations(transcript1: str, name1: str,
                          transcript2: str, name2: str,
                          topic: str) -> str:
    """
    Compare two voice explanations of the same topic.
    Returns a formatted comparison string.
    """
    prompt = f"""You are StreakBot comparing two students' voice explanations of the same topic.

Topic: {topic}

{name1}'s explanation:
\"\"\"{transcript1[:800]}\"\"\"

{name2}'s explanation:
\"\"\"{transcript2[:800]}\"\"\"

Compare them honestly. Respond ONLY in this format:

CLARITY_WINNER: [{name1}/{name2}/tie]
DEPTH_WINNER: [{name1}/{name2}/tie]
EXAMPLES_WINNER: [{name1}/{name2}/tie]
OVERALL_WINNER: [{name1}/{name2}/tie]

{name1.upper()}_STRENGTHS: [what they explained better — 1 sentence]
{name2.upper()}_STRENGTHS: [what they explained better — 1 sentence]

WHAT_{name1.upper()}_MISSED: [one key thing {name1} left out that {name2} covered]
WHAT_{name2.upper()}_MISSED: [one key thing {name2} left out that {name1} covered]

COMBINED_INSIGHT: [one thing that emerges when you combine both explanations — 1 sentence]"""

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
        )
        raw = response.choices[0].message.content.strip()
        return _format_comparison(raw, name1, name2, topic)
    except Exception as e:
        log.error(f"Voice comparison error: {e}")
        return f"Could not compare explanations right now. Try again in a moment."


def _format_comparison(raw: str, name1: str, name2: str, topic: str) -> str:
    """Parse and format the comparison response."""
    parsed = {}
    for line in raw.strip().split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            parsed[key.strip()] = val.strip()

    clarity = parsed.get("CLARITY_WINNER", "tie")
    depth = parsed.get("DEPTH_WINNER", "tie")
    examples = parsed.get("EXAMPLES_WINNER", "tie")
    overall = parsed.get("OVERALL_WINNER", "tie")

    s1 = parsed.get(f"{name1.upper()}_STRENGTHS", "—")
    s2 = parsed.get(f"{name2.upper()}_STRENGTHS", "—")
    m1 = parsed.get(f"WHAT_{name1.upper()}_MISSED", "—")
    m2 = parsed.get(f"WHAT_{name2.upper()}_MISSED", "—")
    combined = parsed.get("COMBINED_INSIGHT", "—")

    def winner_icon(winner, name):
        if winner.lower() == name.lower():
            return "👑"
        if winner.lower() == "tie":
            return "🤝"
        return "  "

    lines = [
        f"🎙 <b>Voice Comparison — {topic}</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"{'Clarity':12} {winner_icon(clarity, name1)} {name1}  vs  {name2} {winner_icon(clarity, name2)}",
        f"{'Depth':12} {winner_icon(depth, name1)} {name1}  vs  {name2} {winner_icon(depth, name2)}",
        f"{'Examples':12} {winner_icon(examples, name1)} {name1}  vs  {name2} {winner_icon(examples, name2)}",
        "",
        f"🏆 <b>Overall:</b> {overall}",
        "",
        f"✅ <b>{name1}:</b> {s1}",
        f"✅ <b>{name2}:</b> {s2}",
        "",
        f"📝 <b>{name1} missed:</b> {m1}",
        f"📝 <b>{name2} missed:</b> {m2}",
        "",
        f"💡 <b>Combined insight:</b> {combined}",
    ]
    return "\n".join(lines)
