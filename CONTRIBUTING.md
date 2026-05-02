# Contributing to StreakBot

Thanks for your interest. Here's how the project is structured and how to extend it.

---

## Project Architecture

The bot is split into focused modules. Each feature lives in its own file:

| File | Responsibility |
|------|---------------|
| `bot.py` | Entry point. All Telegram command handlers, conversation flows, dashboard |
| `ai.py` | All Groq API calls. Every AI function has a fallback for when the API is unavailable |
| `storage.py` | All reads/writes to `data.json`. Single source of truth for streak, reports, user data |
| `handlers.py` | Advanced handlers registered via `register_advanced_handlers()`. Keeps `bot.py` clean |
| `voice.py` | Groq Whisper transcription + explanation scoring + partner comparison |
| `lessons.py` | Evangadi course structure, lesson progress tracking, inline keyboard |
| `xp.py` | XP actions, level calculation, leaderboard formatting |
| `spaced_repetition.py` | Review scheduling, grading, mastery tracking |
| `accountability.py` | 0-100 score calculation across 5 dimensions |
| `interview.py` | Interview question generation and interviewer-style grading |
| `session_log.py` | Live session storage and formatting |
| `progress_report.py` | Monthly/weekly report generation |

---

## Adding a New Feature

1. Create a new file for the feature (e.g. `my_feature.py`)
2. Add storage functions to `storage.py` if you need to persist data
3. Add AI functions to `ai.py` if you need Groq — always include a fallback
4. Add command handlers to `handlers.py`
5. Register them in `register_advanced_handlers()` at the bottom of `handlers.py`
6. Add the command to `set_bot_commands()` in `bot.py`
7. Add a button to `MAIN_MENU` in `bot.py` if it's a primary command

---

## Adding a New AI Function

All AI functions follow this pattern:

```python
def my_ai_function(param1: str, param2: str) -> str:
    prompt = f"""Your prompt here with {param1} and {param2}."""
    result = _ask(prompt)
    if result.startswith("AI is temporarily unavailable"):
        return _fallback_my_function(param1, param2)
    return result

def _fallback_my_function(param1: str, param2: str) -> str:
    # Always provide a fallback — the bot should work even without AI
    return f"Basic response using {param1} and {param2}."
```

---

## Updating the Course Curriculum

Open `lessons.py` and edit `EVANGADI_COURSE`:

```python
EVANGADI_COURSE = [
    {"week": 1, "id": "w1l1", "title": "Your Lesson Title"},
    # ...
]
```

Each lesson needs a unique `id` (format: `w{week}l{number}`), a `week` number, and a `title`.

---

## Code Style

- Functions are async where they interact with Telegram
- All user-facing text uses HTML parse mode (`ParseMode.HTML`)
- Escape user input with `escape()` from `html` before putting it in messages
- Env vars are read at call time, not at module import time
- Every storage function loads fresh data — no in-memory state

---

## Running Tests

There's no test suite yet. To manually test:

1. Copy `.env.example` to `.env` and fill in test credentials
2. Run `python bot.py`
3. Test commands in your Telegram private chat with the bot

---

## Reporting Issues

Open a GitHub issue with:
- What command you ran
- What you expected
- What actually happened
- Any error from the bot logs
