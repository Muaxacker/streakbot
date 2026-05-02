# StreakBot Advanced Upgrade Guide

## What you are adding

| Phase | File | What it does |
|-------|------|--------------|
| 1 | voice.py | Transcribes voice notes, scores explanation 1-10 |
| 2 | lessons.py | Tracks Evangadi Tech lessons (video + notes + exercise) |
| 3 | lessons.py | Weekly project GitHub review + comparison |
| 4 | xp.py | XP points, levels, leaderboard |
| — | handlers.py | Wires everything into your existing bot |

---

## Step 1 — Copy new files

Copy these 4 files into your existing `streakbot/` folder:
- `voice.py`
- `lessons.py`
- `xp.py`
- `handlers.py`

Your folder should now look like:
```
streakbot/
├── bot.py          ← existing
├── ai.py           ← existing
├── storage.py      ← existing
├── voice.py        ← NEW
├── lessons.py      ← NEW
├── xp.py           ← NEW
├── handlers.py     ← NEW
├── data.json
├── requirements.txt
├── Procfile
└── .env
```

---

## Step 2 — Install new library

```bash
pip install groq
```

Groq handles BOTH the LLM (already using it) AND voice transcription.
No new API key needed — same GROQ_API_KEY you already have.

---

## Step 3 — Two lines to add in bot.py

Open `bot.py`. Find the top import section and add:

```python
from handlers import register_advanced_handlers
```

Then find the `main()` function. Find the line `app.run_polling(...)` and
add this ONE LINE directly above it:

```python
register_advanced_handlers(app)
```

So it looks like:

```python
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ... existing handlers ...

    scheduler = AsyncIOScheduler()
    # ... scheduler setup ...
    scheduler.start()

    register_advanced_handlers(app)   # ← ADD THIS LINE

    log.info(f"StreakBot started. Reminder at {reminder_time} daily.")
    app.run_polling(drop_pending_updates=True)
```

---

## Step 4 — Update requirements.txt

Make sure `groq` is in your requirements.txt:

```
python-telegram-bot==20.7
groq
apscheduler==3.10.4
python-dotenv==1.0.0
```

---

## Step 5 — Restart

```bash
python bot.py
```

---

## New commands after upgrade

### Phase 1 — Voice
- Send any voice message → bot auto-transcribes and scores it
- Minimum 60 seconds required (can't fake with a 5-second note)
- Score posted publicly in group

### Phase 2 — Lessons
```
/lesson                     → show current lesson and what's left
/lesson list                → all lessons this week
/lesson done video          → mark video watched
/lesson done notes          → mark notes read
/lesson done exercise       → mark exercise done
/lesson progress            → full course % and week progress
```

### Phase 3 — Weekly project (every Friday)
```
/project submit https://github.com/user/repo  → submit and get AI review
/project status                               → see who submitted
/project compare                              → compare both repos side by side
```

### Phase 4 — XP
```
/xp                         → your XP and level
/leaderboard                → ranking between you and Ayzal
```

---

## How XP is earned

| Action | XP |
|--------|-----|
| Daily report | +10 |
| Voice note (score 1-5) | +10 |
| Voice note (score 6-7) | +20 |
| Voice note (score 8-9) | +30 |
| Voice note (score 10) | +50 |
| Lesson step (1 of 3) | +5 |
| Lesson fully complete | +15 |
| Weekly project submitted | +50 |
| Project score 7-8 bonus | +20 |
| Project score 9-10 bonus | +40 |
| 7-day streak | +25 |
| 30-day streak | +100 |
| 100-day streak | +500 |

---

## How the Friday lock works

1. You finish all lessons in a week
2. Bot tells you: "Week X complete! Submit your project to unlock next week"
3. Until you submit `/project submit [repo]` — all `/lesson` commands are blocked
4. Once both of you submit — next week unlocks automatically

---

## How anti-fake works

**Voice notes:**
- Must be 60+ seconds (configurable in voice.py → MIN_DURATION_SECONDS)
- AI reads the full transcript and scores how well you actually explained it
- Vague answers = 3/10, detailed with examples = 9/10
- Score is public — Ayzal sees your score, you see hers

**Weekly projects:**
- Must be a real GitHub repo URL
- AI fetches the README and code structure
- Checks: does it match this week's topics? Is the code quality good?
- Compares your solution vs Ayzal's solution
- Score is public — no hiding a bad project

---

## Editing the course lessons

Open `lessons.py` and find `EVANGADI_COURSE` list at the top.
Add, remove, or rename lessons to match exactly what Evangadi Tech teaches.
Each lesson needs: week number, unique id, and title.

Example:
```python
{"week": 1, "id": "w1l1", "title": "HTML Structure and Semantics"},
```
