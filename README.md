# StreakBot 🔥

A full-featured Telegram accountability bot for two learning partners tracking their full stack development journey together. Built for the [Evangadi Tech](https://www.evangadi.com/) bootcamp but works for any structured learning program.

> No excuses. No skipping. Let's build.

---

## What It Does

StreakBot is not just a streak tracker. It's a complete learning accountability system with AI coaching, spaced repetition, interview prep, voice explanations, live session logging, and a full XP/leveling system.

---

## Features

### 📅 Daily Accountability
- **Unified report** — submit via free text or voice note. AI extracts all fields automatically
- **Streak tracking** — both partners must report to count the day
- **Milestone celebrations** — at 7, 14, 30, 60, and 100 days
- **Personalized reminders** — daily reminder uses your real streak and consistency data, not a generic message
- **Burnout detection** — if study time drops 50%+ over 3 days, bot sends a caring heads-up

### 🧠 Learning Tools
- **Interactive quiz** — AI generates questions from today's topics, grades each answer 1-5 with feedback
- **Interview prep** — real interview-style questions (not quiz questions), graded like an actual interviewer with hire/no-hire signal
- **Spaced repetition** — topics auto-scheduled for review at day 3, 7, and 14 after studying. Bot asks a question, grades your recall, marks topics as mastered
- **Partner voice comparison** — both explain the same topic via voice, AI compares clarity, depth, and examples side by side

### 📊 Accountability & Progress
- **Accountability score (0-100)** — composite score across consistency, voice quality, quiz scores, study time, and course progress
- **Struggle tracker** — topics auto-added when you mark difficulty as hard or score low. Reminds you before weekly projects
- **Monthly/weekly progress report** — full breakdown with AI narrative assessment
- **Learning stats** — days reported, completion %, streak history

### 🎙 Voice System
- Send any voice note → transcribed with Groq Whisper → scored 1-10 with specific feedback
- Voice reports → transcribed and parsed into report fields automatically
- Partner comparison → both explain same topic, AI compares and declares winner per category

### 📚 Course Tracker (Evangadi Tech)
- Full 9-week full stack curriculum pre-loaded (HTML → CSS → JS → React → Node → MySQL → Auth → Full Stack)
- Each lesson requires 3 steps: video watched, notes read, exercise done
- **Lesson quick-pick** — tap-to-select lessons with inline keyboard, no typing IDs
- Week locked until Friday project is submitted

### 📦 Weekly Projects (Fridays)
- Submit GitHub repo link → AI reviews code quality, topic match, best practices
- Both repos compared side by side
- Week locked until project submitted — no skipping

### 🎥 Live Session Logger
- `/session start` / `/session end` — logs duration of live code review sessions
- Rate the session 1-5 and share one takeaway from your partner
- Session history with stats

### ⚡ XP & Levels
- Every action earns XP — reports, voice notes, quizzes, lessons, projects, reviews
- 10 levels from Beginner to Elite Coder
- Leaderboard between both partners

---

## Tech Stack

- **Python 3.10+**
- **python-telegram-bot 20.7** — async Telegram bot framework
- **Groq** — LLM (llama-3.3-70b) for AI features + Whisper for voice transcription
- **APScheduler** — daily reminder scheduling
- **python-dotenv** — environment variable management
- **JSON files** — lightweight local storage (no database needed)

---

## Project Structure

```
streakbot/
├── bot.py                  # Main bot — commands, report flow, quiz, dashboard
├── ai.py                   # All Groq AI calls — summaries, grading, parsing
├── storage.py              # data.json management, struggle tracker, burnout detection
├── voice.py                # Groq Whisper transcription, scoring, partner comparison
├── handlers.py             # Advanced command handlers (lessons, projects, XP, features)
├── lessons.py              # Evangadi course tracker, lesson quick-pick keyboard
├── xp.py                   # XP points, levels, leaderboard
├── spaced_repetition.py    # 3/7/14 day review scheduling and grading
├── accountability.py       # 0-100 accountability score across 5 dimensions
├── interview.py            # Real interview questions + interviewer-style grading
├── session_log.py          # Live code review session logging
├── progress_report.py      # Monthly/weekly progress report with AI narrative
├── data.json               # Streak, reports, user names (auto-created)
├── xp.json                 # XP history per user (auto-created)
├── lessons.json            # Lesson progress, weekly projects (auto-created)
├── sessions.json           # Live session log (auto-created)
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/streakbot.git
cd streakbot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create your Telegram bot

- Talk to [@BotFather](https://t.me/BotFather) on Telegram
- Use `/newbot` and follow the steps
- Copy your **Bot Token**

### 4. Get a Groq API key (free)

- Go to [console.groq.com](https://console.groq.com)
- Create a free account and generate an API key
- Groq handles both the LLM and voice transcription — no other AI key needed

### 5. Get your Telegram IDs

- Start a private chat with your bot and send `/start`
- Use [@userinfobot](https://t.me/userinfobot) to get your Telegram user ID
- Repeat for your learning partner
- Add the bot to your group, make it **admin** (required for pinning messages)
- Get the group chat ID using [@RawDataBot](https://t.me/RawDataBot)

### 6. Configure `.env`

```bash
cp .env.example .env
```

Fill in `.env`:

```env
BOT_TOKEN=your-telegram-bot-token
GROQ_API_KEY=your-groq-api-key
GROUP_CHAT_ID=-100xxxxxxxxxx
USER1_ID=123456789
USER2_ID=987654321
REMINDER_TIME=20:00
```

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | From BotFather |
| `GROQ_API_KEY` | From console.groq.com (free) |
| `GROUP_CHAT_ID` | Your Telegram group ID (starts with -100) |
| `USER1_ID` | Your Telegram user ID |
| `USER2_ID` | Your partner's Telegram user ID |
| `REMINDER_TIME` | Daily reminder time in 24h format (default: 20:00) |

### 7. Run

```bash
python bot.py
```

On first start, the bot sends both users a message with the full keyboard menu.

---

## Deploying (Free, 24/7)

### Railway.app (recommended)

1. Push your code to GitHub (without `.env` — it's in `.gitignore`)
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add environment variables in the Railway dashboard:
   - `BOT_TOKEN`, `GROQ_API_KEY`, `GROUP_CHAT_ID`, `USER1_ID`, `USER2_ID`, `REMINDER_TIME`
4. Deploy — the bot runs 24/7 for free

> **Note:** Railway's free tier has a monthly usage limit. The bot is lightweight and stays well within it.

### Other options
- **Render** — similar to Railway, free tier available
- **VPS** — any Linux server with Python 3.10+ works
- **Local** — runs fine on your machine while it's on

---

## All Commands

### Daily
| Command | Description |
|---------|-------------|
| `/report` | Submit today's learning (text or voice) |
| `/streak` | View the shared dashboard |
| `/summary` | AI summary of today (after both report) |
| `/weekly` | Week in review |
| `/stats` | Learning stats |
| `/history [N]` | Last N days of reports |

### Learning Tools
| Command | Description |
|---------|-------------|
| `/quiz` | Interactive quiz — AI grades each answer |
| `/interview` | Real interview questions from your recent topics |
| `/interview weekly` | Interview questions from this week's topics |
| `/reviews` | Spaced repetition — topics due for review today |
| `/reviews all` | Full review schedule |
| `/voicecompare` | Compare voice explanations with your partner |

### Accountability
| Command | Description |
|---------|-------------|
| `/score` | Your accountability score (0-100) |
| `/comparescores` | Side-by-side comparison with partner |
| `/struggles` | Your current struggle topics |
| `/struggles resolve [topic]` | Mark a struggle as conquered |
| `/progressreport` | Monthly progress report with AI assessment |
| `/progressreport week` | This week only |

### Live Sessions
| Command | Description |
|---------|-------------|
| `/session start` | Start a live code review session |
| `/session end` | End the session and log duration |
| `/session rate 5 [takeaway]` | Rate the session and share what you learned |
| `/session log` | Session history and stats |

### Course Tracker
| Command | Description |
|---------|-------------|
| `/lessonpick` | Pick a lesson from an interactive tap-to-select list |
| `/lesson` | Current lesson status |
| `/lesson done video` | Mark video watched |
| `/lesson done notes` | Mark notes read |
| `/lesson done exercise` | Mark exercise done |
| `/lesson progress` | Full course progress % |
| `/lesson list` | All lessons this week |

### Weekly Project
| Command | Description |
|---------|-------------|
| `/project submit [url]` | Submit GitHub repo for AI review |
| `/project status` | See who submitted this week |
| `/project compare` | Side-by-side AI comparison of both repos |

### XP & Levels
| Command | Description |
|---------|-------------|
| `/xp` | Your XP and level |
| `/leaderboard` | XP ranking between you two |

### Other
| Command | Description |
|---------|-------------|
| `/plan` | Both next topics + AI advice |
| `/nexttopic [topic]` | Set your next topic |
| `/setreminder HH:MM` | Change daily reminder time |
| `/resetstreak` | Reset the streak (admin) |
| `/menu` | Show full command menu |

---

## Customizing the Course

Open `lessons.py` and find the `EVANGADI_COURSE` list. Edit the lesson titles and weeks to match your actual course:

```python
EVANGADI_COURSE = [
    {"week": 1, "id": "w1l1", "title": "HTML Structure and Semantics"},
    {"week": 1, "id": "w1l2", "title": "CSS Basics and Box Model"},
    # ... add your lessons here
]
```

---

## Data Storage

All data is stored in local JSON files — no database required:

| File | Contents |
|------|----------|
| `data.json` | Streak, reports, user names, next topics, milestones |
| `xp.json` | XP history per user |
| `lessons.json` | Lesson progress, weekly project submissions |
| `sessions.json` | Live session log |

These files are created automatically on first run. Back them up regularly if you care about your streak history.

---

## License

MIT — use it, fork it, build on it.
