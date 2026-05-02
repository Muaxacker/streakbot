"""
api.py — REST API for the StreakBot React Mini App

Runs alongside bot.py on port 8001.
Provides read-only endpoints for the dashboard.

Start: python api.py
Or alongside bot: both run in separate threads via bot.py
"""

import os
import json
from datetime import date, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

import storage
import xp as xp_module
import spaced_repetition as sr
import accountability as acc

app = FastAPI(title="StreakBot API", version="1.0.0")

# Allow requests from the React app (Telegram Mini App or localhost dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Middleware to handle ngrok browser warning bypass
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class NgrokBypassMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["ngrok-skip-browser-warning"] = "true"
        return response

app.add_middleware(NgrokBypassMiddleware)

USER1_ID = int(os.getenv("USER1_ID", "0"))
USER2_ID = int(os.getenv("USER2_ID", "0"))


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/")
def health():
    return {"status": "ok", "service": "StreakBot API"}


# ─── Dashboard — main endpoint ────────────────────────────────────────────────

@app.get("/dashboard")
def dashboard():
    """
    Full dashboard data for both users.
    Used by the React app home screen.
    """
    data = storage.load()
    today = str(date.today())
    today_reports = data.get("reports", {}).get(today, {})

    def user_status(uid: int) -> dict:
        uid_str = str(uid)
        name = storage.get_user_name(uid, data)
        reported_today = uid_str in today_reports
        rep = today_reports.get(uid_str, {})

        xp = xp_module.get_user_xp(uid)
        level = xp_module.get_level(xp)
        next_xp = xp_module.get_xp_to_next_level(xp)

        acc_data = data.get("accountability", {}).get(uid_str, {})
        voice_scores = acc_data.get("voice_scores", [])
        quiz_scores = acc_data.get("quiz_scores", [])

        return {
            "id": uid,
            "name": name,
            "reported_today": reported_today,
            "today_report": {
                "learned": rep.get("learned", ""),
                "time_spent": rep.get("time_spent", ""),
                "difficulty": rep.get("difficulty", ""),
                "next_topic": rep.get("topic", ""),
                "submitted_at": rep.get("submitted_at", ""),
            } if reported_today else None,
            "next_topic": data.get("next_topics", {}).get(uid_str, ""),
            "xp": xp,
            "level": level["level"],
            "level_title": level["title"],
            "xp_to_next": next_xp,
            "avg_voice_score": round(sum(voice_scores[-10:]) / len(voice_scores[-10:]), 1) if voice_scores else None,
            "avg_quiz_score": round(sum(quiz_scores[-10:]) / len(quiz_scores[-10:]), 1) if quiz_scores else None,
        }

    return {
        "streak": data.get("streak", 0),
        "longest_streak": data.get("longest_streak", 0),
        "last_streak_date": data.get("last_streak_date"),
        "both_reported_today": str(USER1_ID) in today_reports and str(USER2_ID) in today_reports,
        "user1": user_status(USER1_ID),
        "user2": user_status(USER2_ID),
        "today": today,
    }


# ─── Calendar — last 30 days ──────────────────────────────────────────────────

@app.get("/calendar")
def calendar():
    """
    Last 30 days of report activity.
    Used for the calendar heatmap.
    """
    data = storage.load()
    reports = data.get("reports", {})
    result = []

    for i in range(30):
        day = str(date.today() - timedelta(days=i))
        day_reports = reports.get(day, {})
        u1 = str(USER1_ID) in day_reports
        u2 = str(USER2_ID) in day_reports
        result.append({
            "date": day,
            "user1_reported": u1,
            "user2_reported": u2,
            "both": u1 and u2,
            "streak_day": u1 and u2,
        })

    return {"days": result}


# ─── XP Leaderboard ───────────────────────────────────────────────────────────

@app.get("/leaderboard")
def leaderboard():
    """XP and level data for both users."""
    data = storage.load()

    def user_xp(uid: int) -> dict:
        xp = xp_module.get_user_xp(uid)
        level = xp_module.get_level(xp)
        next_xp = xp_module.get_xp_to_next_level(xp)
        xp_data = xp_module.load_xp()
        history = xp_data.get("users", {}).get(str(uid), {}).get("history", [])
        # Last 14 days of XP gains
        recent = [h for h in history[-30:]]
        return {
            "id": uid,
            "name": storage.get_user_name(uid, data),
            "xp": xp,
            "level": level["level"],
            "level_title": level["title"],
            "xp_to_next": next_xp,
            "xp_needed_for_level": level["xp_needed"],
            "recent_history": recent[-14:],
        }

    u1 = user_xp(USER1_ID)
    u2 = user_xp(USER2_ID)
    leader = u1["name"] if u1["xp"] >= u2["xp"] else u2["name"]
    gap = abs(u1["xp"] - u2["xp"])

    return {
        "user1": u1,
        "user2": u2,
        "leader": leader,
        "gap": gap,
    }


# ─── Accountability Scores ────────────────────────────────────────────────────

@app.get("/scores")
def scores():
    """Accountability scores for both users."""
    score1 = acc.calculate_score(USER1_ID)
    score2 = acc.calculate_score(USER2_ID)
    data = storage.load()

    return {
        "user1": {
            "name": storage.get_user_name(USER1_ID, data),
            **score1,
        },
        "user2": {
            "name": storage.get_user_name(USER2_ID, data),
            **score2,
        },
    }


# ─── Course Progress ──────────────────────────────────────────────────────────

@app.get("/progress")
def progress():
    """Course progress for both users across all 5 phases."""
    from lessons import EVANGADI_COURSE, PHASE_LABELS, get_user_lesson_progress

    data = storage.load()

    def user_progress(uid: int) -> dict:
        phases = {}
        for phase_num, label in PHASE_LABELS.items():
            phase_lessons = [l for l in EVANGADI_COURSE if l.get("phase") == phase_num]
            completed = 0
            lessons_detail = []
            for lesson in phase_lessons:
                lp = get_user_lesson_progress(uid, lesson["id"])
                done = lp["video"] and lp["notes"] and lp["exercise"]
                if done:
                    completed += 1
                lessons_detail.append({
                    "id": lesson["id"],
                    "title": lesson["title"],
                    "week": lesson["week"],
                    "video": lp["video"],
                    "notes": lp["notes"],
                    "exercise": lp["exercise"],
                    "done": done,
                    "done_date": lp.get("done_date"),
                })
            phases[phase_num] = {
                "label": label,
                "total": len(phase_lessons),
                "completed": completed,
                "pct": round(completed / len(phase_lessons) * 100) if phase_lessons else 0,
                "lessons": lessons_detail,
            }

        total = len(EVANGADI_COURSE)
        total_done = sum(p["completed"] for p in phases.values())

        return {
            "name": storage.get_user_name(uid, data),
            "total_lessons": total,
            "total_completed": total_done,
            "overall_pct": round(total_done / total * 100) if total else 0,
            "phases": phases,
        }

    return {
        "user1": user_progress(USER1_ID),
        "user2": user_progress(USER2_ID),
    }


# ─── Struggles ────────────────────────────────────────────────────────────────

@app.get("/struggles")
def struggles():
    """Active struggle topics for both users."""
    data = storage.load()
    return {
        "user1": {
            "name": storage.get_user_name(USER1_ID, data),
            "struggles": storage.get_struggles(USER1_ID, unresolved_only=True),
        },
        "user2": {
            "name": storage.get_user_name(USER2_ID, data),
            "struggles": storage.get_struggles(USER2_ID, unresolved_only=True),
        },
    }


# ─── Stats — last 30 days ─────────────────────────────────────────────────────

@app.get("/stats")
def stats():
    """Aggregated stats for both users."""
    data = storage.load()
    reports = data.get("reports", {})

    def user_stats(uid: int) -> dict:
        uid_str = str(uid)
        days_reported = sum(1 for d in reports.values() if uid_str in d)
        total_days = len(reports)

        difficulties = {"easy": 0, "medium": 0, "hard": 0}
        total_hours = 0.0
        for day_reports in reports.values():
            rep = day_reports.get(uid_str, {})
            if rep:
                diff = rep.get("difficulty", "")
                if diff in difficulties:
                    difficulties[diff] += 1
                # Parse hours
                ts = rep.get("time_spent", "")
                try:
                    if "hour" in ts.lower():
                        total_hours += float(ts.lower().split("hour")[0].strip().split()[-1])
                    elif "hr" in ts.lower():
                        total_hours += float(ts.lower().replace("hr", "").strip())
                    elif "min" in ts.lower():
                        total_hours += float(ts.lower().split("min")[0].strip().split()[-1]) / 60
                except (ValueError, IndexError):
                    pass

        return {
            "name": storage.get_user_name(uid, data),
            "days_reported": days_reported,
            "total_days": total_days,
            "completion_pct": round(days_reported / total_days * 100) if total_days else 0,
            "total_hours": round(total_hours, 1),
            "avg_hours_per_day": round(total_hours / days_reported, 1) if days_reported else 0,
            "difficulties": difficulties,
        }

    return {
        "streak": data.get("streak", 0),
        "longest_streak": data.get("longest_streak", 0),
        "user1": user_stats(USER1_ID),
        "user2": user_stats(USER2_ID),
    }


# ─── Run standalone ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
