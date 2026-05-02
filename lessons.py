"""
lessons.py — Phase 2: Evangadi Tech course lesson tracker

Each lesson requires 3 steps to be marked complete:
1. Video watched
2. Notes read
3. Exercise done

Bot locks next week's lessons until Friday's project is submitted.
"""

import json
import os
import logging
from datetime import date, datetime, timedelta
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

LESSONS_FILE = "lessons.json"

# ─── Evangadi Tech Full Stack Course ─────────────────────────────────────────
# Add or edit lessons here to match the actual course order on Evangadi Tech

EVANGADI_COURSE = [
    # Week 1 — HTML & CSS Fundamentals
    {"week": 1, "id": "w1l1", "title": "HTML Structure and Semantics"},
    {"week": 1, "id": "w1l2", "title": "CSS Basics and Box Model"},
    {"week": 1, "id": "w1l3", "title": "Flexbox and Grid Layout"},
    {"week": 1, "id": "w1l4", "title": "Responsive Design and Media Queries"},

    # Week 2 — JavaScript Fundamentals
    {"week": 2, "id": "w2l1", "title": "JavaScript Variables and Data Types"},
    {"week": 2, "id": "w2l2", "title": "Functions and Scope"},
    {"week": 2, "id": "w2l3", "title": "Arrays and Objects"},
    {"week": 2, "id": "w2l4", "title": "DOM Manipulation"},
    {"week": 2, "id": "w2l5", "title": "Events and Event Listeners"},

    # Week 3 — Advanced JavaScript
    {"week": 3, "id": "w3l1", "title": "Async JavaScript and Promises"},
    {"week": 3, "id": "w3l2", "title": "Fetch API and AJAX"},
    {"week": 3, "id": "w3l3", "title": "ES6+ Features"},
    {"week": 3, "id": "w3l4", "title": "Error Handling"},

    # Week 4 — React Fundamentals
    {"week": 4, "id": "w4l1", "title": "React Introduction and JSX"},
    {"week": 4, "id": "w4l2", "title": "Components and Props"},
    {"week": 4, "id": "w4l3", "title": "State and useState Hook"},
    {"week": 4, "id": "w4l4", "title": "useEffect and Lifecycle"},
    {"week": 4, "id": "w4l5", "title": "React Router"},

    # Week 5 — React Advanced
    {"week": 5, "id": "w5l1", "title": "Context API and State Management"},
    {"week": 5, "id": "w5l2", "title": "Custom Hooks"},
    {"week": 5, "id": "w5l3", "title": "Forms in React"},
    {"week": 5, "id": "w5l4", "title": "API Integration in React"},

    # Week 6 — Node.js and Express
    {"week": 6, "id": "w6l1", "title": "Node.js Introduction"},
    {"week": 6, "id": "w6l2", "title": "Express.js Basics"},
    {"week": 6, "id": "w6l3", "title": "REST API Design"},
    {"week": 6, "id": "w6l4", "title": "Middleware and Routing"},

    # Week 7 — Database
    {"week": 7, "id": "w7l1", "title": "SQL and MySQL Basics"},
    {"week": 7, "id": "w7l2", "title": "Database Design and Relations"},
    {"week": 7, "id": "w7l3", "title": "MySQL with Node.js"},
    {"week": 7, "id": "w7l4", "title": "CRUD Operations"},

    # Week 8 — Authentication
    {"week": 8, "id": "w8l1", "title": "Authentication Concepts"},
    {"week": 8, "id": "w8l2", "title": "JWT Tokens"},
    {"week": 8, "id": "w8l3", "title": "Bcrypt and Password Security"},
    {"week": 8, "id": "w8l4", "title": "Protected Routes"},

    # Week 9 — Full Stack Integration
    {"week": 9, "id": "w9l1", "title": "Connecting React to Express"},
    {"week": 9, "id": "w9l2", "title": "CORS and Environment Variables"},
    {"week": 9, "id": "w9l3", "title": "Full Stack Project Structure"},
    {"week": 9, "id": "w9l4", "title": "Deployment Basics"},
]


# ─── Load / Save ──────────────────────────────────────────────────────────────

def _default_lessons():
    return {
        "progress": {},       # { "USER_ID": { "LESSON_ID": { video, notes, exercise, done_date } } }
        "weekly_projects": {},# { "WEEK_NUM": { "USER_ID": { repo, score, submitted_date } } }
        "week_locked": {}     # { "USER_ID": week_number_locked_at }
    }


def load_lessons():
    if not os.path.exists(LESSONS_FILE):
        data = _default_lessons()
        save_lessons(data)
        return data
    with open(LESSONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_lessons(data):
    with open(LESSONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ─── Lesson helpers ───────────────────────────────────────────────────────────

def get_lesson_by_id(lesson_id: str) -> dict | None:
    for l in EVANGADI_COURSE:
        if l["id"] == lesson_id:
            return l
    return None


def get_lessons_for_week(week: int) -> list:
    return [l for l in EVANGADI_COURSE if l["week"] == week]


def get_current_week_for_user(user_id: int) -> int:
    """Return the week the user is currently on."""
    data = load_lessons()
    progress = data["progress"].get(str(user_id), {})

    # Find highest week with any completed lesson
    completed_weeks = set()
    for lesson in EVANGADI_COURSE:
        lp = progress.get(lesson["id"], {})
        if lp.get("video") and lp.get("notes") and lp.get("exercise"):
            completed_weeks.add(lesson["week"])

    if not completed_weeks:
        return 1
    return max(completed_weeks)


def get_user_lesson_progress(user_id: int, lesson_id: str) -> dict:
    data = load_lessons()
    return data["progress"].get(str(user_id), {}).get(lesson_id, {
        "video": False, "notes": False, "exercise": False, "done_date": None
    })


def mark_lesson_step(user_id: int, lesson_id: str, step: str) -> dict:
    """
    Mark one step of a lesson (video, notes, or exercise).
    Returns updated progress for that lesson.
    step must be: 'video', 'notes', or 'exercise'
    """
    data = load_lessons()
    uid = str(user_id)

    if uid not in data["progress"]:
        data["progress"][uid] = {}
    if lesson_id not in data["progress"][uid]:
        data["progress"][uid][lesson_id] = {
            "video": False, "notes": False, "exercise": False, "done_date": None
        }

    data["progress"][uid][lesson_id][step] = True

    # If all 3 done, mark the done date
    lp = data["progress"][uid][lesson_id]
    if lp["video"] and lp["notes"] and lp["exercise"] and not lp["done_date"]:
        lp["done_date"] = str(date.today())

    save_lessons(data)
    return data["progress"][uid][lesson_id]


def is_lesson_complete(user_id: int, lesson_id: str) -> bool:
    lp = get_user_lesson_progress(user_id, lesson_id)
    return lp["video"] and lp["notes"] and lp["exercise"]


def is_week_locked(user_id: int) -> tuple[bool, int | None]:
    """
    Returns (is_locked, locked_at_week).
    A user is locked if they completed a week but haven't submitted that week's project.
    """
    data = load_lessons()
    uid = str(user_id)
    current_week = get_current_week_for_user(user_id)

    # Check if all lessons in current week are complete
    week_lessons = get_lessons_for_week(current_week)
    all_done = all(is_lesson_complete(user_id, l["id"]) for l in week_lessons)

    if not all_done:
        return False, None  # Not done yet — not locked, just not finished

    # Check if project for this week is submitted
    week_projects = data["weekly_projects"].get(str(current_week), {})
    user_submitted = uid in week_projects

    if not user_submitted:
        return True, current_week  # Locked — week done but no project yet

    return False, None


def get_course_progress_summary(user_id: int) -> dict:
    """Return a summary of overall course progress."""
    total = len(EVANGADI_COURSE)
    completed = sum(
        1 for l in EVANGADI_COURSE if is_lesson_complete(user_id, l["id"])
    )
    percentage = round(completed / total * 100)
    current_week = get_current_week_for_user(user_id)
    total_weeks = max(l["week"] for l in EVANGADI_COURSE)

    return {
        "completed": completed,
        "total": total,
        "percentage": percentage,
        "current_week": current_week,
        "total_weeks": total_weeks
    }


# ─── Weekly project ───────────────────────────────────────────────────────────

def submit_weekly_project(user_id: int, week: int, repo_url: str,
                           score: int, review: str):
    data = load_lessons()
    week_str = str(week)
    if week_str not in data["weekly_projects"]:
        data["weekly_projects"][week_str] = {}
    data["weekly_projects"][week_str][str(user_id)] = {
        "repo": repo_url,
        "score": score,
        "review": review,
        "submitted_date": str(date.today())
    }
    save_lessons(data)


def get_weekly_project(week: int, user_id: int) -> dict | None:
    data = load_lessons()
    return data["weekly_projects"].get(str(week), {}).get(str(user_id))


def both_submitted_project(week: int, user1_id: int, user2_id: int) -> bool:
    data = load_lessons()
    week_data = data["weekly_projects"].get(str(week), {})
    return str(user1_id) in week_data and str(user2_id) in week_data


# ─── AI repo review ───────────────────────────────────────────────────────────

def review_github_repo(repo_url: str, week_topics: str,
                        name: str, partner_code: str = None) -> dict:
    """
    Fetch and review a GitHub repo.
    Returns dict with: score, topic_match, quality, best_practices, comparison
    """
    # Convert github.com URL to raw API URL for reading
    raw_content = _fetch_github_readme(repo_url)
    if not raw_content:
        raw_content = f"Repository: {repo_url} (could not fetch content — reviewing URL only)"

    comparison_section = ""
    if partner_code:
        comparison_section = f"""
Also compare this code with their partner's solution:
Partner's code summary: {partner_code[:800]}

Add a COMPARISON section showing:
- Key differences in approach
- Who handled edge cases better
- What each can learn from the other"""

    prompt = f"""You are reviewing a student's weekly project code for a full stack web development bootcamp.

Student name: {name}
Week topics covered: {week_topics}
GitHub repository: {repo_url}
Code/README content:
\"\"\"{raw_content[:2000]}\"\"\"
{comparison_section}

Review and score the project. Respond ONLY in this exact format:

SCORE: [number 1-10]
TOPIC_MATCH: [Does the code match this week's topics? 1-2 sentences]
QUALITY: [Code quality assessment — structure, naming, logic. 1-2 sentences]
BEST_PRACTICES: [Are they following good practices? What could improve? 1-2 sentences]
STRENGTHS: [2-3 specific things done well]
IMPROVE: [The single most important thing to improve]
COMPARISON: [If partner code provided: how the two solutions differ and what each can learn. Otherwise: "Submit both repos to enable comparison."]"""

    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
        )
        raw = response.choices[0].message.content.strip()
        return _parse_repo_review(raw)
    except Exception as e:
        log.error(f"Repo review error: {e}")
        return {"score": 0, "error": str(e)}


def _fetch_github_readme(repo_url: str) -> str | None:
    """Try to fetch README from a GitHub repo URL."""
    import urllib.request
    try:
        # Convert https://github.com/user/repo to API URL
        url = repo_url.strip().rstrip("/")
        parts = url.replace("https://github.com/", "").split("/")
        if len(parts) < 2:
            return None
        user, repo = parts[0], parts[1]
        raw_url = f"https://raw.githubusercontent.com/{user}/{repo}/main/README.md"
        req = urllib.request.Request(raw_url, headers={"User-Agent": "StreakBot"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.read().decode("utf-8")[:3000]
    except Exception:
        return None


def _parse_repo_review(raw: str) -> dict:
    result = {
        "score": 0, "topic_match": "", "quality": "",
        "best_practices": "", "strengths": "",
        "improve": "", "comparison": ""
    }
    for line in raw.split("\n"):
        for key in result:
            prefix = key.upper().replace("_", "_") + ":"
            if line.startswith(prefix):
                val = line.replace(prefix, "").strip()
                if key == "score":
                    try:
                        result[key] = int(val)
                    except ValueError:
                        result[key] = 0
                else:
                    result[key] = val
    return result


def format_repo_review_message(name: str, week: int, repo_url: str,
                                review: dict) -> str:
    score = review.get("score", 0)
    emoji = "🏆" if score >= 9 else "⭐" if score >= 7 else "👍" if score >= 5 else "📖"

    lines = [
        f"📦 Week {week} Project Review — {name}",
        f"Repo: {repo_url}",
        "",
        f"Score: {emoji} {score}/10",
        "",
        f"Topic match: {review.get('topic_match', '—')}",
        f"Code quality: {review.get('quality', '—')}",
        f"Best practices: {review.get('best_practices', '—')}",
        "",
        f"Strengths: {review.get('strengths', '—')}",
        f"Top improvement: {review.get('improve', '—')}",
    ]

    comparison = review.get("comparison", "")
    if comparison and comparison != "Submit both repos to enable comparison.":
        lines.append(f"\n🔄 Comparison with partner:\n{comparison}")

    return "\n".join(lines)


# ─── Quick-pick lesson selector ───────────────────────────────────────────────

def get_lesson_inline_keyboard(user_id: int, week: int = None):
    """
    Build an InlineKeyboardMarkup for picking a lesson.
    Returns list of button rows for use with InlineKeyboardMarkup.
    """
    from telegram import InlineKeyboardButton
    if week is None:
        week = get_current_week_for_user(user_id)

    week_lessons = get_lessons_for_week(week)
    rows = []
    for lesson in week_lessons:
        lp = get_user_lesson_progress(user_id, lesson["id"])
        done = lp["video"] and lp["notes"] and lp["exercise"]
        icon = "✅" if done else "📖"
        rows.append([
            InlineKeyboardButton(
                f"{icon} {lesson['title']}",
                callback_data=f"lesson_pick:{lesson['id']}"
            )
        ])
    # Navigation row
    nav = []
    if week > 1:
        nav.append(InlineKeyboardButton(f"◀ Week {week-1}", callback_data=f"lesson_week:{week-1}"))
    max_week = max(l["week"] for l in EVANGADI_COURSE)
    if week < max_week:
        nav.append(InlineKeyboardButton(f"Week {week+1} ▶", callback_data=f"lesson_week:{week+1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="lesson_cancel")])
    return rows, week
