"""
handlers.py — Advanced handlers for StreakBot (Phases 1-4)

Registered into bot.py via register_advanced_handlers(app).
"""

import os
import logging
from html import escape
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)
import storage
import voice as voice_module
import lessons as lessons_module
import xp as xp_module
import spaced_repetition as sr
import accountability as acc
import interview as interview_module
import session_log as session_module
import progress_report as report_module

log = logging.getLogger(__name__)


# ─── Env helpers (read at call time, not import time) ─────────────────────────

def _user1() -> int:
    return int(os.getenv("USER1_ID", "0"))


def _user2() -> int:
    return int(os.getenv("USER2_ID", "0"))


def _group() -> int:
    return int(os.getenv("GROUP_CHAT_ID", "0"))


def _is_member(user_id: int) -> bool:
    return user_id in (_user1(), _user2())


def _get_name(user_id: int) -> str:
    return storage.get_user_name(user_id)


def _partner_id(user_id: int) -> int:
    return _user2() if user_id == _user1() else _user1()


def _get_week_topics(week: int) -> str:
    return ", ".join(l["title"] for l in lessons_module.get_lessons_for_week(week))


# ─── PHASE 1: Voice handler ───────────────────────────────────────────────────

async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-triggered when a member sends a voice message."""
    user = update.effective_user
    if not _is_member(user.id):
        return

    voice = update.message.voice
    if not voice:
        return

    duration = voice.duration
    name = _get_name(user.id)

    if duration < voice_module.MIN_DURATION_SECONDS:
        await update.message.reply_text(
            f"⏱ <b>Too short!</b> That was only {duration}s.\n\n"
            f"Minimum is {voice_module.MIN_DURATION_SECONDS}s.\n"
            f"<i>A real explanation takes more than {duration} seconds. Try again. 😏</i>",
            parse_mode="HTML",
        )
        return

    await update.message.reply_text(
        f"🎙 Got your voice note ({duration}s).\n"
        f"<i>Transcribing and scoring — takes about 15 seconds...</i>",
        parse_mode="HTML",
    )

    data = storage.load()
    topic = data.get("next_topics", {}).get(str(user.id), "today's topic")

    voice_file = await context.bot.get_file(voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name
    await voice_file.download_to_drive(tmp_path)

    try:
        transcript = await voice_module.transcribe_voice(tmp_path)
        if not transcript:
            await update.message.reply_text(
                "😕 Couldn't transcribe that. Try again with a clearer recording."
            )
            return

        score_data = voice_module.score_explanation(transcript, topic, name)
        score = score_data["score"]

        xp_action = xp_module.voice_xp_action(score)
        xp_result = xp_module.award_xp(user.id, xp_action)

        # Record for accountability score
        acc.record_voice_score(user.id, score)

        # Auto-add to struggles if score is low
        import storage as _storage
        if score <= 4:
            _storage.add_struggle(user.id, topic, reason="low_voice")

        result_msg = voice_module.format_voice_result(
            name, topic, transcript, score_data, duration
        )
        xp_msg = xp_module.format_xp_award(xp_result, name)
        if xp_msg:
            result_msg += f"\n\n{xp_msg}"

        await context.bot.send_message(
            chat_id=_group(), text=result_msg, parse_mode="HTML"
        )

        if update.effective_chat.id != _group():
            await update.message.reply_text(
                f"✅ Score posted to the group: <b>{score}/10</b>\n"
                f"⚡ +{xp_result['xp_earned']} XP earned.",
                parse_mode="HTML",
            )

        if xp_result.get("leveled_up"):
            await context.bot.send_message(
                chat_id=_group(),
                text=(
                    f"🎉 <b>{name} just leveled up!</b>\n"
                    f"Now Level {xp_result['level_after']} — <b>{xp_result['new_level_title']}</b> 🚀"
                ),
                parse_mode="HTML",
            )
    finally:
        os.unlink(tmp_path)


# ─── PHASE 2: Lesson tracking ─────────────────────────────────────────────────

async def lesson_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /lesson                    — show current lesson
    /lesson list               — all lessons this week
    /lesson progress           — full course progress
    /lesson done video         — mark video watched
    /lesson done notes         — mark notes read
    /lesson done exercise      — mark exercise done
    /lesson done video w1l2    — mark specific lesson step
    """
    user = update.effective_user
    if not _is_member(user.id):
        return

    args = context.args or []
    name = _get_name(user.id)

    locked, locked_week = lessons_module.is_week_locked(user.id)
    if locked:
        await update.message.reply_text(
            f"⛔ Week {locked_week} is LOCKED.\n\n"
            "You finished all lessons but haven't submitted the weekly project yet.\n"
            "Submit your GitHub repo to unlock next week:\n\n"
            "/project submit https://github.com/your/repo"
        )
        return

    current_week = lessons_module.get_current_week_for_user(user.id)

    # /lesson list
    if args and args[0] == "list":
        week_lessons = lessons_module.get_lessons_for_week(current_week)
        lines = [f"📚 Week {current_week} Lessons\n"]
        for l in week_lessons:
            lp = lessons_module.get_user_lesson_progress(user.id, l["id"])
            v = "✅" if lp["video"] else "⬜"
            n = "✅" if lp["notes"] else "⬜"
            e = "✅" if lp["exercise"] else "⬜"
            done_mark = "✅ " if lp["done_date"] else "   "
            lines.append(f"{done_mark}{l['title']}  ({l['id']})")
            lines.append(f"    {v} Video  {n} Notes  {e} Exercise")
            lines.append("")
        await update.message.reply_text("\n".join(lines))
        return

    # /lesson progress
    if args and args[0] == "progress":
        summary = lessons_module.get_course_progress_summary(user.id)
        bar_filled = int(summary["percentage"] / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        lines = [
            f"📊 Course Progress — {name}",
            "",
            f"Lessons done: {summary['completed']}/{summary['total']}",
            f"Progress: {bar} {summary['percentage']}%",
            f"Current week: {summary['current_week']}/{summary['total_weeks']}",
        ]
        await update.message.reply_text("\n".join(lines))
        return

    # /lesson done [step] [optional lesson_id]
    if len(args) >= 2 and args[0] == "done":
        step = args[1].lower()
        if step not in ("video", "notes", "exercise"):
            await update.message.reply_text(
                "Invalid step. Use: video, notes, or exercise\n"
                "Example: /lesson done video\n"
                "Example: /lesson done video w1l2"
            )
            return

        if len(args) >= 3:
            lesson_id = args[2]
        else:
            week_lessons = lessons_module.get_lessons_for_week(current_week)
            lesson_id = None
            for l in week_lessons:
                lp = lessons_module.get_user_lesson_progress(user.id, l["id"])
                if not lp[step]:
                    lesson_id = l["id"]
                    break
            if not lesson_id:
                await update.message.reply_text(
                    f"All {step}s already done for week {current_week}! 🎉"
                )
                return

        lesson = lessons_module.get_lesson_by_id(lesson_id)
        if not lesson:
            await update.message.reply_text(
                f"Lesson ID '{lesson_id}' not found.\n"
                "Use /lesson list to see valid IDs."
            )
            return

        lp = lessons_module.mark_lesson_step(user.id, lesson_id, step)
        step_labels = {
            "video": "📹 Video watched",
            "notes": "📝 Notes read",
            "exercise": "💻 Exercise done",
        }

        xp_result = xp_module.award_xp(user.id, "lesson_step")
        msg_lines = [
            f"✅ {step_labels[step]}",
            f"Lesson: {lesson['title']}",
            "",
            f"{'✅' if lp['video'] else '⬜'} Video  "
            f"{'✅' if lp['notes'] else '⬜'} Notes  "
            f"{'✅' if lp['exercise'] else '⬜'} Exercise",
            f"⚡ +{xp_result['xp_earned']} XP",
        ]

        if lp["video"] and lp["notes"] and lp["exercise"]:
            lesson_xp = xp_module.award_xp(user.id, "lesson_complete")
            msg_lines.append(f"\n🎓 Lesson complete! +{lesson_xp['xp_earned']} bonus XP")

            week_lessons = lessons_module.get_lessons_for_week(current_week)
            all_week_done = all(
                lessons_module.is_lesson_complete(user.id, l["id"])
                for l in week_lessons
            )
            if all_week_done:
                msg_lines.append(
                    f"\n🔒 Week {current_week} complete!\n"
                    "Submit your Friday project to unlock next week:\n"
                    "/project submit https://github.com/your/repo"
                )

        await update.message.reply_text("\n".join(msg_lines))
        return

    # Default: show current lesson
    week_lessons = lessons_module.get_lessons_for_week(current_week)
    current_lesson = next(
        (l for l in week_lessons if not lessons_module.is_lesson_complete(user.id, l["id"])),
        None
    )

    if not current_lesson:
        await update.message.reply_text(
            f"All week {current_week} lessons done! 🎉\n\n"
            "Submit your weekly project:\n"
            "/project submit https://github.com/your/repo"
        )
        return

    lp = lessons_module.get_user_lesson_progress(user.id, current_lesson["id"])
    lines = [
        f"📖 Current Lesson — Week {current_week}",
        "",
        f"{current_lesson['title']}",
        f"ID: {current_lesson['id']}",
        "",
        f"{'✅' if lp['video'] else '⬜'} Video     → /lesson done video",
        f"{'✅' if lp['notes'] else '⬜'} Notes     → /lesson done notes",
        f"{'✅' if lp['exercise'] else '⬜'} Exercise  → /lesson done exercise",
        "",
        "See all this week's lessons: /lesson list",
    ]
    await update.message.reply_text("\n".join(lines))


# ─── PHASE 3: Weekly project ──────────────────────────────────────────────────

async def project_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /project submit https://github.com/user/repo
    /project status
    /project compare
    """
    user = update.effective_user
    if not _is_member(user.id):
        return

    args = context.args or []
    name = _get_name(user.id)
    current_week = lessons_module.get_current_week_for_user(user.id)
    u1, u2 = _user1(), _user2()

    if not args:
        await update.message.reply_text(
            "📦 Project commands:\n\n"
            "/project submit https://github.com/user/repo\n"
            "/project status\n"
            "/project compare"
        )
        return

    # /project status
    if args[0] == "status":
        proj1 = lessons_module.get_weekly_project(current_week, u1)
        proj2 = lessons_module.get_weekly_project(current_week, u2)
        name1 = _get_name(u1)
        name2 = _get_name(u2)
        lines = [f"📦 Week {current_week} Project Status\n"]
        for nm, proj in [(name1, proj1), (name2, proj2)]:
            if proj:
                lines.append(f"✅ {nm} — Score: {proj['score']}/10")
                lines.append(f"   {proj['repo']}")
            else:
                lines.append(f"⏳ {nm} — not submitted yet")
        await update.message.reply_text("\n".join(lines))
        return

    # /project compare
    if args[0] == "compare":
        proj1 = lessons_module.get_weekly_project(current_week, u1)
        proj2 = lessons_module.get_weekly_project(current_week, u2)
        if not proj1 or not proj2:
            await update.message.reply_text(
                "Both users need to submit before comparison is available.\n"
                "Use /project status to see who's missing."
            )
            return

        await update.message.reply_text("Comparing repos — takes about 20 seconds...")

        week_topics = _get_week_topics(current_week)
        my_repo = proj1["repo"] if user.id == u1 else proj2["repo"]
        partner_proj = proj2 if user.id == u1 else proj1

        review = lessons_module.review_github_repo(
            repo_url=my_repo,
            week_topics=week_topics,
            name=name,
            partner_code=partner_proj.get("review", ""),
        )
        msg = lessons_module.format_repo_review_message(name, current_week, my_repo, review)
        await context.bot.send_message(chat_id=_group(), text=msg)
        return

    # /project submit [url]
    if args[0] == "submit":
        if len(args) < 2:
            await update.message.reply_text(
                "Include your GitHub URL:\n"
                "/project submit https://github.com/your/repo"
            )
            return

        repo_url = args[1]
        if "github.com" not in repo_url:
            await update.message.reply_text(
                "Please submit a valid GitHub URL.\n"
                "Example: /project submit https://github.com/muaz/week3-project"
            )
            return

        # Check if already submitted
        existing = lessons_module.get_weekly_project(current_week, user.id)
        if existing:
            await update.message.reply_text(
                f"You already submitted week {current_week}.\n"
                f"Repo: {existing['repo']}\n"
                f"Score: {existing['score']}/10\n\n"
                "Use /project compare to see the side-by-side review."
            )
            return

        await update.message.reply_text(
            "Reviewing your repo — takes about 20 seconds..."
        )

        partner_proj = lessons_module.get_weekly_project(current_week, _partner_id(user.id))
        partner_code = partner_proj.get("review", "") if partner_proj else None

        week_topics = _get_week_topics(current_week)
        review = lessons_module.review_github_repo(
            repo_url=repo_url,
            week_topics=week_topics,
            name=name,
            partner_code=partner_code,
        )

        score = review.get("score", 0)

        lessons_module.submit_weekly_project(
            user.id, current_week, repo_url, score,
            review.get("topic_match", "") + " " + review.get("quality", ""),
        )

        xp_result = xp_module.award_xp(user.id, "weekly_project")
        bonus_action = xp_module.project_xp_bonus(score)
        bonus_xp = xp_module.award_xp(user.id, bonus_action) if bonus_action else None
        total_xp = xp_result["xp_earned"] + (bonus_xp["xp_earned"] if bonus_xp else 0)

        msg = lessons_module.format_repo_review_message(name, current_week, repo_url, review)
        msg += f"\n\n⚡ +{total_xp} XP earned!"
        await context.bot.send_message(chat_id=_group(), text=msg)

        if lessons_module.both_submitted_project(current_week, u1, u2):
            await context.bot.send_message(
                chat_id=_group(),
                text=(
                    f"🎉 Both submitted week {current_week} projects!\n"
                    "Use /project compare to see the side-by-side review."
                ),
            )

        if update.effective_chat.id != _group():
            await update.message.reply_text(
                f"Project submitted! Score: {score}/10\n"
                "Review posted to the group."
            )

        if xp_result.get("leveled_up"):
            await context.bot.send_message(
                chat_id=_group(),
                text=(
                    f"🎉 {name} leveled up to "
                    f"Level {xp_result['level_after']} — "
                    f"{xp_result['new_level_title']}!"
                ),
            )
        return

    await update.message.reply_text(
        "Unknown project command.\n"
        "Use: /project submit [url] | /project status | /project compare"
    )


# ─── PHASE 4: XP commands ─────────────────────────────────────────────────────

async def xp_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/xp — show your XP and level"""
    user = update.effective_user
    if not _is_member(user.id):
        return

    xp = xp_module.get_user_xp(user.id)
    level = xp_module.get_level(xp)
    next_xp = xp_module.get_xp_to_next_level(xp)

    # Progress bar within current level
    bar_filled = 0
    if next_xp is not None:
        current_needed = level["xp_needed"]
        progress_in_level = xp - current_needed
        total_for_level = progress_in_level + next_xp
        bar_filled = min(10, int(progress_in_level / total_for_level * 10)) if total_for_level else 0
    bar = "█" * bar_filled + "░" * (10 - bar_filled)

    lines = [
        f"⚡ XP — {_get_name(user.id)}",
        "",
        f"Total XP: {xp}",
        f"Level {level['level']} — {level['title']}",
        f"Progress: {bar}",
        f"{'Next level in: ' + str(next_xp) + ' XP' if next_xp is not None else '🏆 MAX LEVEL reached!'}",
    ]
    await update.message.reply_text("\n".join(lines))


async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/leaderboard — XP ranking between both users"""
    data = storage.load()
    u1, u2 = _user1(), _user2()
    name1 = storage.get_user_name(u1, data)
    name2 = storage.get_user_name(u2, data)
    text = xp_module.get_leaderboard(u1, u2, name1, name2)
    await update.message.reply_text(text, parse_mode="HTML")


# ─── FEATURE 1: Spaced Repetition ────────────────────────────────────────────

# Conversation state for review answers
REVIEW_ANSWER = 50

async def reviews_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/reviews — show all due reviews or full schedule"""
    user = update.effective_user
    if not _is_member(user.id):
        return

    name = _get_name(user.id)
    args = context.args or []

    if args and args[0] == "all":
        # Show full schedule
        all_items = sr.get_all_scheduled(user.id)
        if not all_items:
            await update.message.reply_text(
                "📭 <b>No reviews scheduled yet.</b>\n\n"
                "Topics get scheduled automatically after each /report.",
                parse_mode="HTML",
            )
            return
        mastered = [i for i in all_items if i.get("mastered")]
        pending = [i for i in all_items if not i.get("mastered")]
        lines = [
            f"🔁 <b>Review Schedule — {name}</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            "",
            f"📌 Pending: {len(pending)}  ✅ Mastered: {len(mastered)}",
            "",
        ]
        for item in pending[:10]:
            interval = {0: "3d", 1: "7d", 2: "14d"}.get(item["interval_index"], "done")
            lines.append(f"⏳ {item['topic']}  [{interval} review]  due: {item['next_review']}")
        for item in mastered[:5]:
            lines.append(f"✅ {item['topic']}  mastered")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        return

    # Show due reviews
    due = sr.get_due_reviews(user.id)
    if not due:
        mastered = sr.count_mastered(user.id)
        await update.message.reply_text(
            f"✅ <b>No reviews due today, {name}!</b>\n\n"
            f"Topics mastered so far: <b>{mastered}</b>\n\n"
            f"<i>Use /reviews all to see your full schedule.</i>",
            parse_mode="HTML",
        )
        return

    # Start the first due review
    item = due[0]
    from datetime import date
    days_ago = (date.today() - date.fromisoformat(item["studied_date"])).days
    question = sr.generate_review_question(
        item["topic"], item["learned"], name, days_ago
    )

    context.user_data["review_item"] = item
    context.user_data["review_question"] = question
    context.user_data["review_due_list"] = due
    context.user_data["review_index"] = 0

    await update.message.reply_text(
        sr.format_review_prompt(item, question, name),
        parse_mode="HTML",
    )
    return REVIEW_ANSWER


async def review_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle a spaced review answer."""
    user = update.effective_user
    answer = update.message.text.strip()
    name = _get_name(user.id)

    item = context.user_data.get("review_item")
    question = context.user_data.get("review_question", "")
    due_list = context.user_data.get("review_due_list", [])
    idx = context.user_data.get("review_index", 0)

    if not item:
        return

    await update.message.reply_text("⏳ <i>Grading...</i>", parse_mode="HTML")

    grade = sr.grade_review_answer(item["topic"], item["learned"], answer, name)

    if grade["remembered"]:
        sr.advance_review(user.id, item["topic"], item["studied_date"])
        xp_result = xp_module.award_xp(user.id, "review_remembered")
        # Check if mastered (all intervals done)
        updated = sr.get_all_scheduled(user.id)
        for u_item in updated:
            if u_item["topic"] == item["topic"] and u_item.get("mastered"):
                xp_module.award_xp(user.id, "review_mastered")
                break
    else:
        sr.dismiss_review(user.id, item["topic"], item["studied_date"])
        xp_result = {"xp_earned": 0}

    result_text = sr.format_review_result(item, grade, name)
    if xp_result["xp_earned"] > 0:
        result_text += f"\n\n⚡ +{xp_result['xp_earned']} XP"

    await update.message.reply_text(result_text, parse_mode="HTML")

    # Move to next due review if any
    next_idx = idx + 1
    if next_idx < len(due_list):
        context.user_data["review_index"] = next_idx
        next_item = due_list[next_idx]
        from datetime import date
        days_ago = (date.today() - date.fromisoformat(next_item["studied_date"])).days
        next_q = sr.generate_review_question(
            next_item["topic"], next_item["learned"], name, days_ago
        )
        context.user_data["review_item"] = next_item
        context.user_data["review_question"] = next_q

        await update.message.reply_text(
            f"<i>Next review ({next_idx + 1}/{len(due_list)})...</i>",
            parse_mode="HTML",
        )
        await update.message.reply_text(
            sr.format_review_prompt(next_item, next_q, name),
            parse_mode="HTML",
        )
        return REVIEW_ANSWER
    else:
        context.user_data.pop("review_item", None)
        context.user_data.pop("review_due_list", None)
        await update.message.reply_text(
            f"✅ <b>All reviews done for today!</b>\n\n"
            f"Mastered so far: <b>{sr.count_mastered(user.id)}</b> topics",
            parse_mode="HTML",
        )
        return -1  # ConversationHandler.END


async def skip_review_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/skipreview — skip current review."""
    user = update.effective_user
    item = context.user_data.get("review_item")
    if item:
        sr.dismiss_review(user.id, item["topic"], item["studied_date"])
    context.user_data.pop("review_item", None)
    context.user_data.pop("review_due_list", None)
    await update.message.reply_text(
        "⏭ <i>Review skipped. It'll come back around. 👀</i>",
        parse_mode="HTML",
    )
    return -1


# ─── FEATURE 2: Accountability Score ─────────────────────────────────────────

async def score_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/score — show your accountability score"""
    user = update.effective_user
    if not _is_member(user.id):
        return

    name = _get_name(user.id)
    await update.message.reply_text(
        "📊 <i>Calculating your accountability score...</i>",
        parse_mode="HTML",
    )

    score_data = acc.calculate_score(user.id)
    card = acc.format_score_card(user.id, name, score_data)
    await update.message.reply_text(card, parse_mode="HTML")

    # Award XP if score hits 80+
    if score_data["total"] >= 80:
        xp_result = xp_module.award_xp(user.id, "score_80_plus")
        if xp_result["xp_earned"] > 0:
            await update.message.reply_text(
                f"⚡ +{xp_result['xp_earned']} XP — Elite accountability!",
                parse_mode="HTML",
            )


async def compare_scores_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/comparescores — compare accountability scores side by side"""
    user = update.effective_user
    if not _is_member(user.id):
        return

    u1, u2 = _user1(), _user2()
    name1 = storage.get_user_name(u1)
    name2 = storage.get_user_name(u2)

    await update.message.reply_text(
        "📊 <i>Calculating both scores...</i>", parse_mode="HTML"
    )

    score1 = acc.calculate_score(u1)
    score2 = acc.calculate_score(u2)

    # Individual cards
    await update.message.reply_text(
        acc.format_score_card(u1, name1, score1), parse_mode="HTML"
    )
    await update.message.reply_text(
        acc.format_score_card(u2, name2, score2), parse_mode="HTML"
    )

    # Comparison
    comparison = acc.format_comparison(u1, u2, name1, name2, score1, score2)
    await update.message.reply_text(comparison, parse_mode="HTML")


# ─── FEATURE 3: Struggle Tracker ─────────────────────────────────────────────

async def struggles_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/struggles — show your current struggle topics"""
    user = update.effective_user
    if not _is_member(user.id):
        return

    name = _get_name(user.id)
    args = context.args or []

    # /struggles resolve [topic]
    if args and args[0] == "resolve":
        if len(args) < 2:
            await update.message.reply_text(
                "Usage: <code>/struggles resolve React hooks</code>",
                parse_mode="HTML",
            )
            return
        topic = " ".join(args[1:])
        storage.resolve_struggle(user.id, topic)
        xp_result = xp_module.award_xp(user.id, "struggle_resolved")
        await update.message.reply_text(
            f"✅ <b>Struggle resolved!</b>\n\n"
            f"<i>{escape(topic)}</i> marked as conquered.\n"
            f"⚡ +{xp_result['xp_earned']} XP",
            parse_mode="HTML",
        )
        return

    struggles = storage.get_struggles(user.id, unresolved_only=True)

    if not struggles:
        await update.message.reply_text(
            f"✅ <b>No active struggles, {name}!</b>\n\n"
            "<i>Topics get added automatically when you mark difficulty as 'hard' "
            "or score low on quizzes.</i>",
            parse_mode="HTML",
        )
        return

    lines = [
        f"⚠️ <b>Struggle Topics — {name}</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"<i>{len(struggles)} topic(s) need more practice:</i>",
        "",
    ]

    reason_labels = {
        "hard_difficulty": "marked hard",
        "low_quiz": "low quiz score",
        "low_voice": "low voice score",
        "manual": "added manually",
    }

    for s in struggles:
        reason = reason_labels.get(s.get("reason", ""), s.get("reason", ""))
        lines.append(f"⚠️ <b>{escape(s['topic'])}</b>  <i>({reason}, {s['date']})</i>")

    lines += [
        "",
        "<i>Use /struggles resolve [topic] when you've mastered it.</i>",
        "<i>These topics will appear in your weekly project reminder.</i>",
    ]

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# ─── FEATURE 4: Interview Prep ────────────────────────────────────────────────

# Conversation state
INTERVIEW_ANSWER = 60

async def interview_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/interview — start an interview prep session"""
    user = update.effective_user
    if not _is_member(user.id):
        return

    name = _get_name(user.id)
    args = context.args or []

    # /interview weekly — use this week's topics
    if args and args[0] == "weekly":
        u1, u2 = _user1(), _user2()
        topics = interview_module.get_weekly_topics(u1, u2)
    else:
        # Use recent reports
        data = storage.load()
        reports = storage.get_reports_for_days(7)
        topics = []
        for entry in reports:
            rep = entry.get(str(user.id), {})
            if isinstance(rep, dict) and rep.get("learned"):
                topics.append(rep["learned"])
        if not topics:
            topics = ["full stack web development"]

    if not topics:
        await update.message.reply_text(
            "📭 <b>No topics found.</b>\n\n"
            "Submit a few daily reports first, then try /interview.",
            parse_mode="HTML",
        )
        return

    await update.message.reply_text(
        "💼 <i>Generating interview questions from your recent topics...</i>",
        parse_mode="HTML",
    )

    questions = interview_module.generate_interview_questions(topics, name)

    context.user_data["interview_questions"] = questions
    context.user_data["interview_index"] = 0
    context.user_data["interview_scores"] = []

    await update.message.reply_text(
        interview_module.format_question_card(questions[0], 1, len(questions)),
        parse_mode="HTML",
    )
    return INTERVIEW_ANSWER


async def interview_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle an interview answer."""
    user = update.effective_user
    answer = update.message.text.strip()
    name = _get_name(user.id)

    questions = context.user_data.get("interview_questions", [])
    idx = context.user_data.get("interview_index", 0)
    scores = context.user_data.get("interview_scores", [])

    if not questions or idx >= len(questions):
        return -1

    q = questions[idx]

    await update.message.reply_text(
        "⏳ <i>Interviewer is reviewing your answer...</i>",
        parse_mode="HTML",
    )

    grade = interview_module.grade_interview_answer(
        q["question"], q["wants"], answer, name
    )

    await update.message.reply_text(
        interview_module.format_grade_card(q, grade, name),
        parse_mode="HTML",
    )

    scores.append(grade["score"])
    context.user_data["interview_scores"] = scores
    context.user_data["interview_index"] = idx + 1

    if idx + 1 >= len(questions):
        # Session complete
        pct = round(sum(scores) / (len(scores) * 5) * 100) if scores else 0
        summary = interview_module.format_session_summary(name, scores, questions)

        xp_result = xp_module.award_xp(user.id, "interview_completed")
        if pct >= 80:
            bonus = xp_module.award_xp(user.id, "interview_strong")
            xp_total = xp_result["xp_earned"] + bonus["xp_earned"]
        else:
            xp_total = xp_result["xp_earned"]

        summary += f"\n\n⚡ +{xp_total} XP earned!"

        # Record quiz score for accountability
        acc.record_quiz_score(user.id, pct)

        await update.message.reply_text(summary, parse_mode="HTML")

        context.user_data.pop("interview_questions", None)
        context.user_data.pop("interview_index", None)
        context.user_data.pop("interview_scores", None)
        return -1

    # Next question
    next_q = questions[idx + 1]
    await update.message.reply_text(
        interview_module.format_question_card(next_q, idx + 2, len(questions)),
        parse_mode="HTML",
    )
    return INTERVIEW_ANSWER


async def skip_interview_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/skipinterview — skip current interview question."""
    questions = context.user_data.get("interview_questions", [])
    idx = context.user_data.get("interview_index", 0)
    scores = context.user_data.get("interview_scores", [])

    scores.append(0)
    context.user_data["interview_scores"] = scores
    context.user_data["interview_index"] = idx + 1

    await update.message.reply_text(
        "⏭ <i>Skipped. A real interviewer would notice that. 😏</i>",
        parse_mode="HTML",
    )

    if idx + 1 >= len(questions):
        pct = round(sum(scores) / (len(scores) * 5) * 100) if scores else 0
        name = storage.get_user_name(update.effective_user.id)
        summary = interview_module.format_session_summary(name, scores, questions)
        await update.message.reply_text(summary, parse_mode="HTML")
        context.user_data.pop("interview_questions", None)
        context.user_data.pop("interview_index", None)
        context.user_data.pop("interview_scores", None)
        return -1

    next_q = questions[idx + 1]
    await update.message.reply_text(
        interview_module.format_question_card(next_q, idx + 2, len(questions)),
        parse_mode="HTML",
    )
    return INTERVIEW_ANSWER


async def cancel_interview_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/cancelinterview — cancel interview session."""
    context.user_data.pop("interview_questions", None)
    context.user_data.pop("interview_index", None)
    context.user_data.pop("interview_scores", None)
    await update.message.reply_text(
        "❌ Interview cancelled.\n\n<i>Running from the hard questions? 😏</i>",
        parse_mode="HTML",
    )
    return -1


# ─── FEATURE 5: Live Session Logger ──────────────────────────────────────────

SESSION_RATE = 70  # conversation state

async def session_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/session start | end | rate [1-5] [takeaway] | log"""
    user = update.effective_user
    if not _is_member(user.id):
        return

    args = context.args or []
    name = _get_name(user.id)
    u1, u2 = _user1(), _user2()

    if not args:
        active = session_module.get_active_session()
        if active:
            start = active["start_time"][:16].replace("T", " ")
            await update.message.reply_text(
                f"🎥 <b>Session in progress</b>\n\n"
                f"Started at: {start}\n\n"
                f"Use /session end when you're done.",
                parse_mode="HTML",
            )
        else:
            await update.message.reply_text(
                "🎥 <b>Session commands:</b>\n\n"
                "/session start — begin a live code review\n"
                "/session end — end the session\n"
                "/session rate 5 I learned how to structure routes — rate it\n"
                "/session log — see session history",
                parse_mode="HTML",
            )
        return

    if args[0] == "start":
        active = session_module.get_active_session()
        if active:
            await update.message.reply_text(
                "⚠️ A session is already active.\n"
                "Use /session end to close it first.",
                parse_mode="HTML",
            )
            return
        session = session_module.start_session(user.id)
        msg = session_module.format_session_started(session, name)
        await context.bot.send_message(chat_id=_group(), text=msg, parse_mode="HTML")
        if update.effective_chat.id != _group():
            await update.message.reply_text(msg, parse_mode="HTML")
        return

    if args[0] == "end":
        session = session_module.end_session()
        if not session:
            await update.message.reply_text(
                "No active session to end.\nUse /session start first.",
                parse_mode="HTML",
            )
            return
        msg = session_module.format_session_ended(session)
        await context.bot.send_message(chat_id=_group(), text=msg, parse_mode="HTML")
        if update.effective_chat.id != _group():
            await update.message.reply_text(msg, parse_mode="HTML")
        return

    if args[0] == "rate":
        if len(args) < 3:
            await update.message.reply_text(
                "Usage: <code>/session rate [1-5] [what you learned from partner]</code>\n\n"
                "Example: <code>/session rate 4 I learned how to use async/await properly</code>",
                parse_mode="HTML",
            )
            return
        try:
            rating = int(args[1])
            if not 1 <= rating <= 5:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Rating must be 1-5.")
            return

        takeaway = " ".join(args[2:])
        session_module.add_rating(user.id, rating, takeaway)

        stars = "⭐" * rating
        await update.message.reply_text(
            f"✅ <b>Session rated!</b>\n\n"
            f"{stars} {rating}/5\n"
            f"💡 <i>{escape(takeaway)}</i>",
            parse_mode="HTML",
        )
        # Post takeaway to group
        await context.bot.send_message(
            chat_id=_group(),
            text=f"💡 <b>{name}</b> learned from today's session:\n<i>{escape(takeaway)}</i>",
            parse_mode="HTML",
        )
        return

    if args[0] == "log":
        sessions = session_module.get_sessions(10)
        name1 = _get_name(u1)
        name2 = _get_name(u2)
        msg = session_module.format_session_log(sessions, name1, name2, u1, u2)
        await update.message.reply_text(msg, parse_mode="HTML")
        return

    await update.message.reply_text(
        "Unknown session command. Use: start | end | rate | log"
    )


# ─── FEATURE 6: Partner Voice Comparison ─────────────────────────────────────

VOICE_COMPARE_WAIT = 80  # conversation state

async def voicecompare_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/voicecompare — start a partner voice comparison session"""
    user = update.effective_user
    if not _is_member(user.id):
        return

    name = _get_name(user.id)
    data = storage.load()
    topic = data.get("next_topics", {}).get(str(user.id), "today's topic")

    context.user_data["vc_topic"] = topic
    context.user_data["vc_user_id"] = user.id
    context.user_data["vc_transcript1"] = None
    context.user_data["vc_transcript2"] = None
    context.user_data["vc_name1"] = name
    context.user_data["vc_name2"] = _get_name(_partner_id(user.id))

    await update.message.reply_text(
        f"🎙 <b>Voice Comparison Mode</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Topic: <b>{escape(topic)}</b>\n\n"
        f"<b>Step 1:</b> Send your voice explanation now.\n"
        f"<i>Then your partner sends theirs. AI compares both.</i>\n\n"
        f"<i>Use /cancelcompare to exit.</i>",
        parse_mode="HTML",
    )
    return VOICE_COMPARE_WAIT


async def voicecompare_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive voice notes for comparison."""
    user = update.effective_user
    voice = update.message.voice
    if not voice:
        return VOICE_COMPARE_WAIT

    name = _get_name(user.id)
    await update.message.reply_text(
        f"🎙 Got {name}'s voice ({voice.duration}s). Transcribing...",
        parse_mode="HTML",
    )

    voice_file = await context.bot.get_file(voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name
    await voice_file.download_to_drive(tmp_path)

    try:
        transcript = await voice_module.transcribe_voice(tmp_path)
    finally:
        import os as _os
        _os.unlink(tmp_path)

    if not transcript:
        await update.message.reply_text("Couldn't transcribe. Try again.")
        return VOICE_COMPARE_WAIT

    # Store transcript for the right user
    vc_user = context.user_data.get("vc_user_id")
    if user.id == vc_user:
        context.user_data["vc_transcript1"] = transcript
        await update.message.reply_text(
            f"✅ Got your explanation, {name}!\n\n"
            f"Now waiting for your partner's voice note...",
            parse_mode="HTML",
        )
    else:
        context.user_data["vc_transcript2"] = transcript
        await update.message.reply_text(
            f"✅ Got {name}'s explanation too!",
            parse_mode="HTML",
        )

    # If both transcripts are in, run comparison
    t1 = context.user_data.get("vc_transcript1")
    t2 = context.user_data.get("vc_transcript2")
    if t1 and t2:
        topic = context.user_data.get("vc_topic", "today's topic")
        name1 = context.user_data.get("vc_name1", "User 1")
        name2 = context.user_data.get("vc_name2", "User 2")

        await update.message.reply_text(
            "🤖 <i>Comparing both explanations...</i>", parse_mode="HTML"
        )
        comparison = voice_module.compare_explanations(t1, name1, t2, name2, topic)
        await context.bot.send_message(
            chat_id=_group(), text=comparison, parse_mode="HTML"
        )
        if update.effective_chat.id != _group():
            await update.message.reply_text(comparison, parse_mode="HTML")

        # Clean up
        for key in ["vc_topic", "vc_user_id", "vc_transcript1",
                    "vc_transcript2", "vc_name1", "vc_name2"]:
            context.user_data.pop(key, None)
        return -1

    return VOICE_COMPARE_WAIT


async def cancel_compare_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for key in ["vc_topic", "vc_user_id", "vc_transcript1",
                "vc_transcript2", "vc_name1", "vc_name2"]:
        context.user_data.pop(key, None)
    await update.message.reply_text("❌ Voice comparison cancelled.")
    return -1


# ─── FEATURE 7: Progress Report ──────────────────────────────────────────────

async def progressreport_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/progressreport [week] — generate a progress report"""
    user = update.effective_user
    if not _is_member(user.id):
        return

    args = context.args or []
    period = "week" if args and args[0] == "week" else "month"
    name = _get_name(user.id)

    await update.message.reply_text(
        f"📋 <i>Generating your {period}ly report...</i>",
        parse_mode="HTML",
    )

    report = report_module.generate_report(user.id, name, period)
    await update.message.reply_text(report, parse_mode="HTML")


# ─── FEATURE 8: Lesson Quick-Pick ────────────────────────────────────────────

async def lesson_pick_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/lessonpick — pick a lesson from an interactive list"""
    user = update.effective_user
    if not _is_member(user.id):
        return

    current_week = lessons_module.get_current_week_for_user(user.id)
    rows, week, phase_label = lessons_module.get_lesson_inline_keyboard(user.id, current_week)

    await update.message.reply_text(
        f"📚 <b>Pick a lesson</b>\n"
        f"<i>{phase_label} — Week {week}</i>\n\n"
        f"Tap a lesson to mark steps, or use ◀ ▶ to navigate weeks.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def lesson_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle lesson pick inline button presses."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    if data == "lesson_cancel":
        await query.edit_message_text("❌ Cancelled.")
        return

    if data.startswith("lesson_week:"):
        week = int(data.split(":")[1])
        rows, week, phase_label = lessons_module.get_lesson_inline_keyboard(user.id, week)
        await query.edit_message_text(
            f"📚 <b>Pick a lesson</b>\n"
            f"<i>{phase_label} — Week {week}</i>\n\n"
            f"Tap a lesson to mark steps, or use ◀ ▶ to navigate weeks.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return

    if data.startswith("lesson_pick:"):
        lesson_id = data.split(":")[1]
        lesson = lessons_module.get_lesson_by_id(lesson_id)
        if not lesson:
            await query.edit_message_text("Lesson not found.")
            return

        lp = lessons_module.get_user_lesson_progress(user.id, lesson_id)
        v = "✅" if lp["video"] else "⬜"
        n = "✅" if lp["notes"] else "⬜"
        e = "✅" if lp["exercise"] else "⬜"

        step_buttons = []
        if not lp["video"]:
            step_buttons.append(
                InlineKeyboardButton("📹 Mark Video", callback_data=f"lesson_step:{lesson_id}:video")
            )
        if not lp["notes"]:
            step_buttons.append(
                InlineKeyboardButton("📝 Mark Notes", callback_data=f"lesson_step:{lesson_id}:notes")
            )
        if not lp["exercise"]:
            step_buttons.append(
                InlineKeyboardButton("💻 Mark Exercise", callback_data=f"lesson_step:{lesson_id}:exercise")
            )

        rows = []
        if step_buttons:
            rows.append(step_buttons)
        rows.append([InlineKeyboardButton("◀ Back", callback_data=f"lesson_week:{lesson['week']}")])

        await query.edit_message_text(
            f"📖 <b>{lesson['title']}</b>\n"
            f"{lessons_module.PHASE_LABELS.get(lesson.get('phase', 1), '')} — Week {lesson['week']}\n\n"
            f"{v} Video  {n} Notes  {e} Exercise\n\n"
            f"{'✅ All done!' if lp['done_date'] else 'Tap to mark steps:'}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return

    if data.startswith("lesson_step:"):
        _, lesson_id, step = data.split(":")
        lesson = lessons_module.get_lesson_by_id(lesson_id)
        if not lesson:
            await query.edit_message_text("Lesson not found.")
            return

        lp = lessons_module.mark_lesson_step(user.id, lesson_id, step)
        xp_result = xp_module.award_xp(user.id, "lesson_step")

        step_labels = {"video": "📹 Video", "notes": "📝 Notes", "exercise": "💻 Exercise"}
        v = "✅" if lp["video"] else "⬜"
        n = "✅" if lp["notes"] else "⬜"
        e = "✅" if lp["exercise"] else "⬜"

        all_done = lp["video"] and lp["notes"] and lp["exercise"]
        if all_done:
            xp_module.award_xp(user.id, "lesson_complete")

        rows = []
        if not lp["video"]:
            rows.append([InlineKeyboardButton("📹 Mark Video", callback_data=f"lesson_step:{lesson_id}:video")])
        if not lp["notes"]:
            rows.append([InlineKeyboardButton("📝 Mark Notes", callback_data=f"lesson_step:{lesson_id}:notes")])
        if not lp["exercise"]:
            rows.append([InlineKeyboardButton("💻 Mark Exercise", callback_data=f"lesson_step:{lesson_id}:exercise")])
        rows.append([InlineKeyboardButton("◀ Back", callback_data=f"lesson_week:{lesson['week']}")])

        status = "🎓 Lesson complete!" if all_done else f"✅ {step_labels[step]} marked!"
        await query.edit_message_text(
            f"📖 <b>{lesson['title']}</b>\n\n"
            f"{v} Video  {n} Notes  {e} Exercise\n\n"
            f"{status}  ⚡ +{xp_result['xp_earned']} XP",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(rows) if not all_done else None,
        )


# ─── Register all handlers ────────────────────────────────────────────────────

def register_advanced_handlers(app):
    """Call this in bot.py main() before app.run_polling()."""
    from telegram.ext import ConversationHandler

    # Phase 1 — voice
    app.add_handler(MessageHandler(filters.VOICE, voice_handler))

    # Phase 2 — lessons
    app.add_handler(CommandHandler("lesson", lesson_cmd))

    # Phase 3 — weekly project
    app.add_handler(CommandHandler("project", project_cmd))

    # Phase 4 — XP
    app.add_handler(CommandHandler("xp", xp_cmd))
    app.add_handler(CommandHandler("leaderboard", leaderboard_cmd))

    # Feature 1 — Spaced Repetition
    review_handler = ConversationHandler(
        entry_points=[CommandHandler("reviews", reviews_cmd)],
        states={
            REVIEW_ANSWER: [
                CommandHandler("skipreview", skip_review_cmd),
                MessageHandler(filters.TEXT & ~filters.COMMAND, review_answer_handler),
            ],
        },
        fallbacks=[CommandHandler("skipreview", skip_review_cmd)],
        per_user=True,
        per_chat=True,
        allow_reentry=True,
    )
    app.add_handler(review_handler)

    # Feature 2 — Accountability Score
    app.add_handler(CommandHandler("score", score_cmd))
    app.add_handler(CommandHandler("comparescores", compare_scores_cmd))

    # Feature 3 — Struggle Tracker
    app.add_handler(CommandHandler("struggles", struggles_cmd))

    # Feature 4 — Interview Prep
    interview_handler = ConversationHandler(
        entry_points=[CommandHandler("interview", interview_cmd)],
        states={
            INTERVIEW_ANSWER: [
                CommandHandler("skipinterview", skip_interview_cmd),
                CommandHandler("cancelinterview", cancel_interview_cmd),
                MessageHandler(filters.TEXT & ~filters.COMMAND, interview_answer_handler),
            ],
        },
        fallbacks=[CommandHandler("cancelinterview", cancel_interview_cmd)],
        per_user=True,
        per_chat=True,
        allow_reentry=True,
    )
    app.add_handler(interview_handler)

    # Feature 5 — Live Session Logger
    app.add_handler(CommandHandler("session", session_cmd))

    # Feature 6 — Partner Voice Comparison
    voice_compare_handler = ConversationHandler(
        entry_points=[CommandHandler("voicecompare", voicecompare_cmd)],
        states={
            VOICE_COMPARE_WAIT: [
                CommandHandler("cancelcompare", cancel_compare_cmd),
                MessageHandler(filters.VOICE, voicecompare_receive),
            ],
        },
        fallbacks=[CommandHandler("cancelcompare", cancel_compare_cmd)],
        per_chat=True,   # shared between both users in same chat
        per_user=False,
        allow_reentry=True,
    )
    app.add_handler(voice_compare_handler)

    # Feature 7 — Progress Report
    app.add_handler(CommandHandler("progressreport", progressreport_cmd))

    # Feature 8 — Lesson Quick-Pick
    app.add_handler(CommandHandler("lessonpick", lesson_pick_cmd))
    app.add_handler(CallbackQueryHandler(lesson_pick_callback, pattern="^lesson_"))

    log.info("All handlers registered: voice, lessons, project, xp, reviews, score, struggles, interview, session, voicecompare, progressreport, lessonpick")