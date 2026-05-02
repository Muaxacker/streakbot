# Changelog

All notable changes to StreakBot are documented here.

---

## [2.0.0] — 2026-05-02

### Major upgrade — Full accountability system

#### New Features
- **Unified report** — submit via free text or voice note. AI extracts all fields automatically (no more 4-step form)
- **Interactive quiz** — questions sent one at a time, AI grades each answer 1-5 with specific feedback
- **Interview prep** — real interview-style questions graded with hire/no-hire signal
- **Spaced repetition** — topics auto-scheduled for review at day 3, 7, and 14
- **Partner voice comparison** — both explain same topic, AI compares clarity, depth, examples
- **Accountability score (0-100)** — composite score across consistency, voice, quiz, study time, course progress
- **Struggle tracker** — auto-detects weak topics from hard difficulty, low quiz/voice scores
- **Monthly/weekly progress report** — full breakdown with AI narrative assessment
- **Live session logger** — `/session start/end/rate/log` for code review sessions
- **Lesson quick-pick** — tap-to-select lessons with inline keyboard
- **Personalized reminders** — uses real streak and consistency data instead of generic messages
- **Burnout detection** — alerts when study time drops 50%+ over 3 days
- **XP system** — 10 levels from Beginner to Elite Coder, leaderboard between partners

#### Improvements
- Voice notes now work as full reports (transcribed + parsed into all fields)
- Keyboard menu stays visible during all conversations (removed ForceReply)
- Bot pushes updated keyboard to both users on startup
- All AI prompts rewritten with personality and troll energy
- Dashboard now shows streak fire indicator and progress bar
- Reminders pick from 7 different troll messages randomly

#### Bug Fixes
- Fixed module-level Groq client initialization crashing on import
- Fixed env vars read at module level before dotenv loads
- Fixed duplicate project submission allowed
- Fixed leaderboard bar calculation for max level users

---

## [1.0.0] — 2026-04-15

### Initial release

- Daily learning reports (4-step conversation)
- Streak tracking with milestone celebrations (7, 14, 30, 60, 100 days)
- AI daily summary, weekly review, quiz
- Group dashboard with pinned message
- Lesson tracker for Evangadi Tech course
- Weekly GitHub project review with AI code analysis
- XP points and levels
- Daily reminder scheduling
- `/plan` with AI topic advice
