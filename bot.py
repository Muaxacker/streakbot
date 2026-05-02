"""
StreakBot - Telegram bot for two learning partners tracking their
full stack development journey together.

Usage:
    python bot.py

Requires .env file with:
    BOT_TOKEN, GROQ_API_KEY, GROUP_CHAT_ID, USER1_ID, USER2_ID, REMINDER_TIME
"""

import logging
import logging.handlers
import os
import tempfile
from datetime import datetime
from html import escape

from dotenv import load_dotenv
from telegram import (
    Bot,
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonCommands,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

load_dotenv()

import ai
import storage
import xp as xp_module
import spaced_repetition as sr
import accountability as acc
import progress_report as report_module
import voice as voice_module
from handlers import register_advanced_handlers
from health import start_health_server

# ─── Config ───────────────────────────────────────────────────────────────────

BOT_TOKEN     = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))
USER1_ID      = int(os.getenv("USER1_ID", "0"))
USER2_ID      = int(os.getenv("USER2_ID", "0"))
REMINDER_TIME = os.getenv("REMINDER_TIME", "20:00")

# ─── Logging — file + console ─────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            "streakbot.log",
            maxBytes=2 * 1024 * 1024,  # 2 MB
            backupCount=3,
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger(__name__)

# ─── Startup validation ───────────────────────────────────────────────────────

def _validate_config():
    """Warn loudly if required env vars are missing."""
    required = {
        "BOT_TOKEN": BOT_TOKEN,
        "GROUP_CHAT_ID": os.getenv("GROUP_CHAT_ID"),
        "USER1_ID": os.getenv("USER1_ID"),
        "USER2_ID": os.getenv("USER2_ID"),
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        log.critical(f"MISSING REQUIRED ENV VARS: {', '.join(missing)}")
        log.critical("Copy .env.example to .env and fill in all values.")
        raise SystemExit(1)
    if GROUP_CHAT_ID == 0 or USER1_ID == 0 or USER2_ID == 0:
        log.critical("GROUP_CHAT_ID, USER1_ID, USER2_ID must be non-zero integers.")
        raise SystemExit(1)
    log.info("Config validated — all required env vars present.")


# ─── Conversation states ──────────────────────────────────────────────────────

# Report conversation states
REPORT_WAITING_INPUT = 0
REPORT_CONFIRM       = 1
REPORT_EDIT          = 2

# Quiz conversation states
QUIZ_ANSWER = 10

# Voice transcript test state
VOICE_TRANSCRIPT_WAIT = 20

MILESTONES = [7, 14, 30, 60, 100]

MAIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("/report"), KeyboardButton("/streak")],
        [KeyboardButton("/quiz"), KeyboardButton("/interview")],
        [KeyboardButton("/reviews"), KeyboardButton("/struggles")],
        [KeyboardButton("/score"), KeyboardButton("/comparescores")],
        [KeyboardButton("/lessonpick"), KeyboardButton("/project status")],
        [KeyboardButton("/session start"), KeyboardButton("/voicecompare")],
        [KeyboardButton("/progressreport"), KeyboardButton("/leaderboard")],
        [KeyboardButton("/weekly"), KeyboardButton("/stats")],
    ],
    resize_keyboard=True,
    is_persistent=True,
    one_time_keyboard=False,
    input_field_placeholder="Choose a StreakBot command",
)


def safe(value: str | None) -> str:
    return escape(value or "")


def short_text(value: str | None, limit: int = 60, fallback: str = "Not set") -> str:
    text = (value or "").strip()
    if not text:
        return fallback
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def is_member(user_id: int) -> bool:
    return user_id in (USER1_ID, USER2_ID)


def get_name(user_id: int, update: Update = None) -> str:
    data = storage.load()
    saved = data["user_names"].get(str(user_id))
    if saved:
        return saved
    if update and update.effective_user:
        name = update.effective_user.first_name
        storage.set_user_name(user_id, name)
        return name
    return f"User {user_id}"


async def send_group(bot: Bot, text: str) -> int | None:
    try:
        msg = await bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return msg.message_id
    except TelegramError as e:
        log.error(f"send_group error: {e}")
        return None


async def pin_message(bot: Bot, message_id: int):
    try:
        await bot.pin_chat_message(
            chat_id=GROUP_CHAT_ID,
            message_id=message_id,
            disable_notification=True,
        )
    except TelegramError as e:
        log.error(f"pin_message error: {e}")


async def unpin_old_and_pin_new(bot: Bot, new_msg_id: int):
    old_id = storage.get_pinned_msg_id()
    if old_id:
        try:
            await bot.unpin_chat_message(chat_id=GROUP_CHAT_ID, message_id=old_id)
        except TelegramError:
            pass
    await pin_message(bot, new_msg_id)
    storage.set_pinned_msg_id(new_msg_id)


def _streak_fire(streak: int) -> str:
    if streak >= 100: return "🔥🔥🔥🔥🔥"
    if streak >= 60:  return "🔥🔥🔥🔥"
    if streak >= 30:  return "🔥🔥🔥"
    if streak >= 14:  return "🔥🔥"
    if streak >= 7:   return "🔥"
    if streak >= 3:   return "✨"
    return "🌱"


def _streak_bar(streak: int, longest: int) -> str:
    if longest == 0:
        return "░░░░░░░░░░"
    filled = min(10, round(streak / longest * 10))
    return "█" * filled + "░" * (10 - filled)


def build_streak_message(data: dict) -> str:
    streak = data.get("streak", 0)
    longest = data.get("longest_streak", 0)
    today_reps = storage.get_today_reports(data)
    topics = data.get("next_topics", {})

    def status_line(uid: int) -> str:
        if str(uid) in today_reps:
            return "✅ Done for today"
        return "⏳ Not reported yet"

    def next_topic(uid: int) -> str:
        t = topics.get(str(uid), "")
        return short_text(t, 40, "not set")

    name1 = safe(storage.get_user_name(USER1_ID, data))
    name2 = safe(storage.get_user_name(USER2_ID, data))
    fire = _streak_fire(streak)
    bar = _streak_bar(streak, longest)

    both_done = str(USER1_ID) in today_reps and str(USER2_ID) in today_reps
    footer_line = "🎯 Both reported — streak secured!" if both_done else "👀 Waiting for both reports to lock in the streak."

    lines = [
        f"╔══ 🚀 <b>StreakBot Dashboard</b> ══╗",
        "",
        f"  {fire} <b>Current streak:</b> {streak} day{'s' if streak != 1 else ''}",
        f"  🏆 <b>Best ever:</b> {longest} day{'s' if longest != 1 else ''}",
        f"  {bar}",
        "",
        f"  👤 <b>{name1}</b>",
        f"  {status_line(USER1_ID)}",
        f"  📌 Next: <i>{safe(next_topic(USER1_ID))}</i>",
        "",
        f"  👤 <b>{name2}</b>",
        f"  {status_line(USER2_ID)}",
        f"  📌 Next: <i>{safe(next_topic(USER2_ID))}</i>",
        "",
        f"  {footer_line}",
        f"  <i>🕐 {datetime.now().strftime('%b %d at %H:%M')}</i>",
        "╚══════════════════════╝",
    ]
    return "\n".join(lines)


async def refresh_dashboard(bot: Bot):
    data = storage.load()
    text = build_streak_message(data)
    msg_id = await send_group(bot, text)
    if msg_id:
        await unpin_old_and_pin_new(bot, msg_id)


async def process_both_reports(bot: Bot, data: dict):
    data = storage.update_streak(USER1_ID, USER2_ID)
    streak = data["streak"]

    await refresh_dashboard(bot)

    today_reps = storage.get_today_reports(data)
    r1 = today_reps.get(str(USER1_ID), {})
    r2 = today_reps.get(str(USER2_ID), {})
    name1 = storage.get_user_name(USER1_ID, data)
    name2 = storage.get_user_name(USER2_ID, data)

    fire = _streak_fire(streak)
    await send_group(
        bot,
        f"🎉 <b>Both reported!</b> {fire}\n\n"
        f"<b>{safe(name1)}</b> and <b>{safe(name2)}</b> locked in day {streak}.\n"
        f"Generating today's summary..."
    )

    summary = ai.summarize_reports(r1, r2, name1, name2)
    await send_group(
        bot,
        f"📚 <b>Today's Learning Summary</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{safe(summary)}"
    )

    milestone = storage.check_milestone(streak)
    if milestone:
        msg = ai.milestone_message(milestone, name1, name2)
        next_m = next((m for m in MILESTONES if m > milestone), None)
        next_text = f"\n\n🎯 <b>Next target:</b> {next_m} days" if next_m else "\n\n🏆 You've hit the top milestone!"
        await send_group(
            bot,
            f"🏅 <b>{milestone}-Day Milestone!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{safe(msg)}{next_text}",
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    storage.set_user_name(user.id, user.first_name)
    await update.message.reply_text(
        f"🚀 <b>StreakBot — Full System</b>\n\n"
        f"Hey <b>{safe(user.first_name)}</b> 👋\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>Daily</b>\n"
        f"  /report — log today's learning (text or voice)\n"
        f"  /streak — dashboard\n"
        f"  /summary — AI summary\n\n"
        f"🧠 <b>Learning Tools</b>\n"
        f"  /quiz — interactive quiz, AI grades answers\n"
        f"  /interview — real interview questions\n"
        f"  /reviews — spaced repetition (3/7/14 day reviews)\n"
        f"  /voicecompare — compare explanations with partner\n\n"
        f"📊 <b>Accountability</b>\n"
        f"  /score — your 0-100 accountability score\n"
        f"  /comparescores — side-by-side comparison\n"
        f"  /struggles — topics you need to revisit\n"
        f"  /progressreport — monthly or weekly report\n"
        f"  /progressreport week — this week only\n\n"
        f"🎥 <b>Live Sessions</b>\n"
        f"  /session start — begin a code review session\n"
        f"  /session end — end it and log duration\n"
        f"  /session rate 5 [takeaway] — rate the session\n"
        f"  /session log — session history\n\n"
        f"📚 <b>Course Tracker</b>\n"
        f"  /lessonpick — pick lesson from interactive list\n"
        f"  /lesson done video/notes/exercise\n"
        f"  /lesson progress — full course %\n\n"
        f"📦 <b>Weekly Project (Fridays)</b>\n"
        f"  /project submit [github url]\n"
        f"  /project compare\n\n"
        f"⚡ <b>XP &amp; Levels</b>\n"
        f"  /xp — your level\n"
        f"  /leaderboard — who's winning\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>No excuses. No skipping. Let's build.</i> 💪",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_MENU,
    )


def _report_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm & Save", callback_data="report_confirm"),
            InlineKeyboardButton("✏️ Edit", callback_data="report_edit"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="report_cancel")],
    ])


def _build_confirm_card(fields: dict) -> str:
    diff_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(
        fields.get("difficulty", ""), "⚪"
    )
    return (
        f"📋 <b>Report Preview</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📖 <b>Learned:</b>\n{safe(fields.get('learned', '—'))}\n\n"
        f"⏱ <b>Time spent:</b> {safe(fields.get('time_spent', '—'))}\n"
        f"{diff_emoji} <b>Difficulty:</b> {safe(fields.get('difficulty', '—'))}\n"
        f"🎯 <b>Next topic:</b> {safe(fields.get('next_topic', '—'))}\n\n"
        f"<i>Looks right? Hit Confirm. Need to fix something? Hit Edit.</i>"
    )


async def report_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_member(user.id):
        await update.message.reply_text("🚫 You're not registered in this bot.")
        return ConversationHandler.END

    storage.set_user_name(user.id, user.first_name)

    today_reps = storage.get_today_reports()
    if str(user.id) in today_reps:
        await update.message.reply_text(
            f"✅ <b>Already done for today, {safe(user.first_name)}!</b>\n\n"
            f"Your report is in. Now go check on your partner 👀\n"
            f"Use /streak to see the dashboard.",
            parse_mode=ParseMode.HTML,
            reply_markup=MAIN_MENU,
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"📝 <b>Daily Report</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Choose how you want to report today:\n\n"
        f"✍️ <b>Write</b> — type one message describing what you learned\n"
        f"🎙 <b>Voice</b> — send a voice note, bot transcribes it\n\n"
        f"<i>Either way, just talk naturally. The bot will extract everything.\n"
        f"Include: what you learned, how long, how hard, what's next.</i>\n\n"
        f"<b>Example text:</b>\n"
        f"<code>Today I studied React hooks — useState and useEffect. "
        f"Spent about 2 hours, it was medium difficulty. "
        f"Next I want to do custom hooks.</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_MENU,
    )
    return REPORT_WAITING_INPUT


async def report_receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free-text report input."""
    user = update.effective_user
    text = update.message.text.strip()
    name = storage.get_user_name(user.id)

    await update.message.reply_text(
        "🤖 <i>Parsing your report...</i>",
        parse_mode=ParseMode.HTML,
    )

    fields = ai.parse_report_text(text, name)
    context.user_data["report_fields"] = fields
    context.user_data["report_source"] = "text"

    await update.message.reply_text(
        _build_confirm_card(fields),
        parse_mode=ParseMode.HTML,
        reply_markup=_report_confirm_keyboard(),
    )
    return REPORT_CONFIRM


async def report_receive_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice note report input."""
    user = update.effective_user
    voice = update.message.voice
    name = storage.get_user_name(user.id)

    await update.message.reply_text(
        f"🎙 <i>Got your voice note ({voice.duration}s). Transcribing...</i>",
        parse_mode=ParseMode.HTML,
    )

    # Download and transcribe
    voice_file = await context.bot.get_file(voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name
    await voice_file.download_to_drive(tmp_path)

    try:
        transcript = await voice_module.transcribe_voice(tmp_path)
    finally:
        os.unlink(tmp_path)

    if not transcript:
        await update.message.reply_text(
            "😕 Couldn't transcribe that. Try again or type your report instead.",
            reply_markup=MAIN_MENU,
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"🤖 <i>Parsing your report from voice...</i>",
        parse_mode=ParseMode.HTML,
    )

    fields = ai.parse_report_text(transcript, name)
    fields["transcript"] = transcript  # save for voice scoring later
    context.user_data["report_fields"] = fields
    context.user_data["report_source"] = "voice"

    await update.message.reply_text(
        _build_confirm_card(fields),
        parse_mode=ParseMode.HTML,
        reply_markup=_report_confirm_keyboard(),
    )
    return REPORT_CONFIRM


async def report_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button presses on the confirmation card."""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    action = query.data

    if action == "report_confirm":
        fields = context.user_data.get("report_fields", {})
        source = context.user_data.get("report_source", "text")

        data = storage.add_report(
            user_id=user.id,
            learned=fields.get("learned", ""),
            topic=fields.get("next_topic", ""),
            time_spent=fields.get("time_spent", ""),
            difficulty=fields.get("difficulty", ""),
        )

        # ── Feature 1: Schedule for spaced repetition ──────────────────────
        learned_text = fields.get("learned", "")
        if learned_text and learned_text != "not specified":
            sr.schedule_topic(user.id, learned_text, learned_text)

        # ── Feature 3: Auto-detect struggles ───────────────────────────────
        if fields.get("difficulty") == "hard":
            storage.add_struggle(
                user.id,
                fields.get("learned", "today's topic"),
                reason="hard_difficulty",
            )
        # Burnout detection
        trend = storage.get_study_time_trend(user.id)
        if trend:
            burnout_msg = ai.generate_burnout_message(
                storage.get_user_name(user.id),
                trend["drop_pct"],
                trend["recent_avg"],
                trend["previous_avg"],
            )
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"⚠️ <b>Heads up</b>\n\n{escape(burnout_msg)}",
                parse_mode=ParseMode.HTML,
            )

        diff_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(
            fields.get("difficulty", ""), "⚪"
        )
        source_icon = "🎙" if source == "voice" else "✍️"

        await query.edit_message_text(
            f"✅ <b>Report saved!</b> {source_icon}\n\n"
            f"📖 <b>Learned:</b> {safe(short_text(fields.get('learned', ''), 80, '—'))}\n"
            f"⏱ <b>Time:</b> {safe(fields.get('time_spent', '—'))}\n"
            f"{diff_emoji} <b>Difficulty:</b> {safe(fields.get('difficulty', '—'))}\n"
            f"🎯 <b>Next:</b> {safe(short_text(fields.get('next_topic', ''), 80, '—'))}\n\n"
            f"<i>Waiting for your partner's report... 👀</i>",
            parse_mode=ParseMode.HTML,
        )

        # Award XP
        xp_result = xp_module.award_xp(user.id, "daily_report")
        if xp_result["xp_earned"] > 0:
            xp_line = f"⚡ <b>+{xp_result['xp_earned']} XP</b> for showing up today!"
            if xp_result.get("leveled_up"):
                xp_line += (
                    f"\n🎉 <b>LEVEL UP!</b> You're now <b>Level {xp_result['level_after']}"
                    f" — {xp_result['new_level_title']}</b> 🚀"
                )
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=xp_line,
                parse_mode=ParseMode.HTML,
            )

        context.user_data.clear()

        if storage.both_reported_today(USER1_ID, USER2_ID, data):
            await process_both_reports(context.bot, data)

        return ConversationHandler.END

    elif action == "report_edit":
        await query.edit_message_text(
            f"✏️ <b>Edit your report</b>\n\n"
            f"Send a new message with the corrected info.\n"
            f"Just write naturally — same as before.\n\n"
            f"<i>Or send a new voice note.</i>",
            parse_mode=ParseMode.HTML,
        )
        return REPORT_EDIT

    elif action == "report_cancel":
        context.user_data.clear()
        await query.edit_message_text(
            "❌ Report cancelled.\n\nDon't ghost the streak — use /report when you're ready."
        )
        return ConversationHandler.END


async def report_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle edited text after user chose to edit."""
    user = update.effective_user
    text = update.message.text.strip()
    name = storage.get_user_name(user.id)

    await update.message.reply_text("🤖 <i>Re-parsing...</i>", parse_mode=ParseMode.HTML)

    fields = ai.parse_report_text(text, name)
    context.user_data["report_fields"] = fields
    context.user_data["report_source"] = "text"

    await update.message.reply_text(
        _build_confirm_card(fields),
        parse_mode=ParseMode.HTML,
        reply_markup=_report_confirm_keyboard(),
    )
    return REPORT_CONFIRM


async def report_edit_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle edited voice note after user chose to edit."""
    return await report_receive_voice(update, context)


async def report_cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Report cancelled.\n\nDon't ghost the streak — use /report when you're ready.",
        reply_markup=MAIN_MENU,
    )
    return ConversationHandler.END


async def streak_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = storage.load()
    text = build_streak_message(data)
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = storage.load()
    all_reports = data.get("reports", {})

    def count_for(uid: int) -> int:
        return sum(1 for day_reps in all_reports.values() if str(uid) in day_reps)

    name1 = storage.get_user_name(USER1_ID, data)
    name2 = storage.get_user_name(USER2_ID, data)
    c1 = count_for(USER1_ID)
    c2 = count_for(USER2_ID)
    total_days = len(all_reports)
    pct1 = round(c1 / total_days * 100) if total_days else 0
    pct2 = round(c2 / total_days * 100) if total_days else 0

    def bar(pct):
        filled = round(pct / 10)
        return "█" * filled + "░" * (10 - filled)

    # Troll line based on who's behind
    troll = ""
    if c1 < c2:
        troll = f"\n💀 <i>{safe(name1)}, you're {c2 - c1} day(s) behind. Your partner is watching.</i>"
    elif c2 < c1:
        troll = f"\n💀 <i>{safe(name2)}, you're {c1 - c2} day(s) behind. Catch up.</i>"
    else:
        troll = f"\n🤝 <i>Perfectly tied. One of you needs to pull ahead.</i>"

    lines = [
        "📊 <b>Learning Stats</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"👤 <b>{safe(name1)}</b>",
        f"  Days reported: {c1}/{total_days}",
        f"  {bar(pct1)} {pct1}%",
        "",
        f"👤 <b>{safe(name2)}</b>",
        f"  Days reported: {c2}/{total_days}",
        f"  {bar(pct2)} {pct2}%",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🔥 Current streak: <b>{data['streak']} days</b>",
        f"🏆 Best streak: <b>{data['longest_streak']} days</b>",
        f"📅 Total tracked days: <b>{total_days}</b>",
        troll,
    ]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    n = 7
    if context.args:
        try:
            n = max(1, min(int(context.args[0]), 30))
        except ValueError:
            pass

    data = storage.load()
    reports = storage.get_reports_for_days(n)

    if not reports:
        await update.message.reply_text(
            "📭 <b>No history yet.</b>\n\n"
            "Nothing to show — the journey starts with /report 🚀",
            parse_mode=ParseMode.HTML,
        )
        return

    name1 = storage.get_user_name(USER1_ID, data)
    name2 = storage.get_user_name(USER2_ID, data)
    lines = [f"📅 <b>Last {n} day{'s' if n != 1 else ''}</b>", "━━━━━━━━━━━━━━━━━━━━", ""]

    for entry in reports:
        day = entry["date"]
        both = str(USER1_ID) in entry and str(USER2_ID) in entry
        day_icon = "✅" if both else "⚠️"
        lines.append(f"{day_icon} <b>{day}</b>")
        for uid, name in [(USER1_ID, name1), (USER2_ID, name2)]:
            rep = entry.get(str(uid))
            if rep:
                diff = rep.get("difficulty", "")
                diff_icon = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(diff, "")
                lines.append(
                    f"  👤 {safe(name)} {diff_icon}\n"
                    f"     {safe(short_text(rep.get('learned', ''), 60, 'Reported'))}"
                )
            else:
                lines.append(f"  👤 {safe(name)} — 💤 skipped")
        lines.append("")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = storage.load()
    today_reps = storage.get_today_reports(data)

    if len(today_reps) < 2:
        reported, not_reported = storage.who_reported_today(USER1_ID, USER2_ID, data)
        missing = [storage.get_user_name(uid, data) for uid in not_reported]
        await update.message.reply_text(
            f"⏳ <b>Summary not ready yet.</b>\n\n"
            f"Still waiting on: <b>{safe(', '.join(missing))}</b>\n\n"
            f"<i>No report = no summary. Simple as that. 😤</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    await update.message.reply_text("🤖 <i>Cooking up today's summary...</i>", parse_mode=ParseMode.HTML)

    r1 = today_reps.get(str(USER1_ID), {})
    r2 = today_reps.get(str(USER2_ID), {})
    name1 = storage.get_user_name(USER1_ID, data)
    name2 = storage.get_user_name(USER2_ID, data)

    summary = ai.summarize_reports(r1, r2, name1, name2)
    await update.message.reply_text(
        f"📚 <b>Today's Learning Summary</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{safe(summary)}",
        parse_mode=ParseMode.HTML,
    )


async def quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start an interactive quiz session — questions one at a time, AI grades each answer."""
    user = update.effective_user
    if not is_member(user.id):
        await update.message.reply_text("🚫 You're not registered in this bot.")
        return ConversationHandler.END

    data = storage.load()
    today_reps = storage.get_today_reports(data)

    if len(today_reps) < 2:
        await update.message.reply_text(
            "🚫 <b>Quiz locked.</b>\n\n"
            "Both of you need to report first.\n"
            "<i>No shortcuts. Do the work, then test yourself.</i>",
            parse_mode=ParseMode.HTML,
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "🧠 <i>Generating your quiz... no peeking at Google.</i>",
        parse_mode=ParseMode.HTML,
    )

    r1 = today_reps.get(str(USER1_ID), {})
    r2 = today_reps.get(str(USER2_ID), {})
    name1 = storage.get_user_name(USER1_ID, data)
    name2 = storage.get_user_name(USER2_ID, data)

    questions = ai.generate_quiz_questions(r1, r2, name1, name2)

    # Store quiz state in user_data
    context.user_data["quiz_questions"] = questions
    context.user_data["quiz_index"] = 0
    context.user_data["quiz_scores"] = []

    # Send first question
    await _send_quiz_question(update, context)
    return QUIZ_ANSWER


async def _send_quiz_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the current quiz question."""
    questions = context.user_data["quiz_questions"]
    idx = context.user_data["quiz_index"]
    q = questions[idx]
    total = len(questions)

    await update.message.reply_text(
        f"🎯 <b>Question {idx + 1} of {total}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{safe(q['question'])}\n\n"
        f"<i>Type your answer below. Be specific — vague answers get low scores. 😏</i>\n"
        f"<i>Type /skipquiz to skip this question.</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_MENU,
    )


async def quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle a quiz answer, grade it, then move to next question or finish."""
    user = update.effective_user
    user_answer = update.message.text.strip()
    questions = context.user_data.get("quiz_questions", [])
    idx = context.user_data.get("quiz_index", 0)
    scores = context.user_data.get("quiz_scores", [])
    name = storage.get_user_name(user.id)

    q = questions[idx]

    await update.message.reply_text(
        "⏳ <i>Grading your answer...</i>",
        parse_mode=ParseMode.HTML,
    )

    grade = ai.grade_answer(q["question"], q["ideal_answer"], user_answer, name)
    score = grade["score"]
    feedback = grade["feedback"]
    correct = grade["correct"]

    score_icons = {5: "🏆", 4: "⭐", 3: "👍", 2: "📖", 1: "💀"}
    icon = score_icons.get(score, "❓")

    result_lines = [
        f"{icon} <b>Score: {score}/5</b>",
        "",
        f"💬 {safe(feedback)}",
        "",
        f"📝 <b>Ideal answer:</b>\n<i>{safe(q['ideal_answer'])}</i>",
    ]
    await update.message.reply_text(
        "\n".join(result_lines),
        parse_mode=ParseMode.HTML,
    )

    scores.append(score)
    context.user_data["quiz_scores"] = scores
    context.user_data["quiz_index"] = idx + 1

    # Check if quiz is done
    if idx + 1 >= len(questions):
        await _finish_quiz(update, context, user)
        return ConversationHandler.END

    # Next question
    await _send_quiz_question(update, context)
    return QUIZ_ANSWER


async def quiz_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip the current question."""
    questions = context.user_data.get("quiz_questions", [])
    idx = context.user_data.get("quiz_index", 0)
    scores = context.user_data.get("quiz_scores", [])

    scores.append(0)
    context.user_data["quiz_scores"] = scores
    context.user_data["quiz_index"] = idx + 1

    await update.message.reply_text(
        "⏭ <i>Skipped. That one will haunt you. 👀</i>",
        parse_mode=ParseMode.HTML,
    )

    if idx + 1 >= len(questions):
        await _finish_quiz(update, context, update.effective_user)
        return ConversationHandler.END

    await _send_quiz_question(update, context)
    return QUIZ_ANSWER


async def quiz_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the quiz mid-way."""
    context.user_data.pop("quiz_questions", None)
    context.user_data.pop("quiz_index", None)
    context.user_data.pop("quiz_scores", None)
    await update.message.reply_text(
        "❌ Quiz cancelled.\n\n<i>Running away from the questions? 😏</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_MENU,
    )
    return ConversationHandler.END


async def _finish_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    """Show the final quiz results and award XP."""
    scores = context.user_data.get("quiz_scores", [])
    questions = context.user_data.get("quiz_questions", [])
    name = storage.get_user_name(user.id)

    total = sum(scores)
    max_score = len(questions) * 5
    pct = round(total / max_score * 100) if max_score else 0

    bar_filled = round(pct / 10)
    bar = "█" * bar_filled + "░" * (10 - bar_filled)

    if pct >= 80:
        verdict = "🏆 Excellent! You actually know this stuff."
        xp_bonus = 20
    elif pct >= 60:
        verdict = "⭐ Solid. A few gaps but you're getting there."
        xp_bonus = 10
    elif pct >= 40:
        verdict = "📖 Decent start. Go back and review the weak spots."
        xp_bonus = 5
    else:
        verdict = "💀 Rough. The topics are not sticking yet — review and try again."
        xp_bonus = 2

    # Award XP
    xp_result = xp_module.award_xp(user.id, "daily_report", bonus=xp_bonus)

    # Record quiz score for accountability
    acc.record_quiz_score(user.id, pct)

    result_lines = [
        f"🎯 <b>Quiz Complete — {name}</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"Score: <b>{total}/{max_score}</b>  ({pct}%)",
        f"{bar}",
        "",
    ]

    for i, (q, s) in enumerate(zip(questions, scores), 1):
        icon = {5: "🏆", 4: "⭐", 3: "👍", 2: "📖", 1: "💀", 0: "⏭"}.get(s, "❓")
        result_lines.append(f"{icon} Q{i}: {safe(short_text(q['question'], 50))} — {s}/5")

    result_lines += [
        "",
        verdict,
        f"⚡ +{xp_bonus} XP earned!",
    ]

    if xp_result.get("leveled_up"):
        result_lines.append(
            f"🎉 <b>LEVEL UP!</b> Now Level {xp_result['level_after']} — {xp_result['new_level_title']} 🚀"
        )

    await update.message.reply_text(
        "\n".join(result_lines),
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_MENU,
    )

    # Post result to group so partner sees it
    group_lines = [
        f"🎯 <b>{safe(name)} just finished the quiz!</b>",
        f"Score: <b>{total}/{max_score}</b> ({pct}%)",
        verdict,
    ]
    await send_group(context.bot, "\n".join(group_lines))

    # Clean up
    context.user_data.pop("quiz_questions", None)
    context.user_data.pop("quiz_index", None)
    context.user_data.pop("quiz_scores", None)


async def weekly_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = storage.load()
    reports = storage.get_reports_for_days(7)

    if not reports:
        await update.message.reply_text(
            "📭 <b>No reports this week yet.</b>\n\n"
            "The weekly review builds from your daily reports.\n"
            "Start with /report and come back Friday. 💪",
            parse_mode=ParseMode.HTML,
        )
        return

    await update.message.reply_text("📊 <i>Reviewing your week... this takes a moment.</i>", parse_mode=ParseMode.HTML)

    name1 = storage.get_user_name(USER1_ID, data)
    name2 = storage.get_user_name(USER2_ID, data)
    summary = ai.weekly_summary(reports, name1, name2)
    await update.message.reply_text(
        f"📅 <b>Weekly Learning Review</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{safe(summary)}",
        parse_mode=ParseMode.HTML,
    )


async def nexttopic_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_member(user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "📌 <b>Set your next topic</b>\n\n"
            "Usage: <code>/nexttopic React hooks and useEffect</code>\n\n"
            "<i>This shows on the group dashboard so your partner knows what you're working on.</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    topic = " ".join(context.args)
    storage.set_next_topic(user.id, topic)
    storage.set_user_name(user.id, user.first_name)

    await update.message.reply_text(
        f"📌 <b>Next topic set!</b>\n\n"
        f"<b>{safe(user.first_name)}</b> is coming for: <i>{safe(topic)}</i>\n\n"
        f"Dashboard updated. 👀",
        parse_mode=ParseMode.HTML,
    )
    await refresh_dashboard(context.bot)


async def plan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = storage.load()
    topics = storage.get_next_topics(data)
    name1 = storage.get_user_name(USER1_ID, data)
    name2 = storage.get_user_name(USER2_ID, data)
    t1 = topics.get(str(USER1_ID), "not set")
    t2 = topics.get(str(USER2_ID), "not set")

    lines = [
        "🗺 <b>Next Topics</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"👤 <b>{safe(name1)}</b>",
        f"  📌 {safe(t1)}",
        "",
        f"👤 <b>{safe(name2)}</b>",
        f"  📌 {safe(t2)}",
    ]

    if t1 != "not set" and t2 != "not set":
        lines.append("\n<i>🤖 Asking AI for advice on your plan...</i>")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

        recent = storage.get_reports_for_days(7)
        history_topics = []
        for entry in recent:
            for uid in [str(USER1_ID), str(USER2_ID)]:
                rep = entry.get(uid, {})
                if isinstance(rep, dict) and rep.get("topic"):
                    history_topics.append(rep["topic"])
        history = ", ".join(history_topics[:6])

        advice = ai.suggest_next_topic(t1, t2, name1, name2, history)
        await update.message.reply_text(
            f"🤖 <b>AI Study Advice</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{safe(advice)}",
            parse_mode=ParseMode.HTML,
        )
    else:
        lines.append("\n<i>Set your next topic with /nexttopic to unlock AI advice.</i>")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def setreminder_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        current = storage.get_reminder_time()
        await update.message.reply_text(
            f"<b>Current reminder time:</b> {safe(current)}\n\n"
            "Usage: <code>/setreminder HH:MM</code>\n"
            "Example: <code>/setreminder 21:00</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    time_str = context.args[0]
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await update.message.reply_text(
            "Invalid format. Use <code>HH:MM</code> - for example: <code>/setreminder 21:00</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    storage.set_reminder_time(time_str)
    await update.message.reply_text(
        f"<b>Reminder updated</b>\n\n"
        f"New time: <b>{safe(time_str)}</b> every day.\n"
        "Restart the bot for the change to take effect.",
        parse_mode=ParseMode.HTML,
    )


async def resetstreak_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in (USER1_ID, USER2_ID):
        return
    storage.reset_streak()
    storage.reset_milestones()
    await update.message.reply_text(
        "💀 <b>Streak reset.</b>\n\n"
        "Back to zero. The grind starts over.\n"
        "<i>Don't waste it this time.</i>",
        parse_mode=ParseMode.HTML,
    )
    await refresh_dashboard(context.bot)


async def send_reminder(bot: Bot):
    reported, not_reported = storage.who_reported_today(USER1_ID, USER2_ID)

    if not not_reported:
        return

    data = storage.load()
    streak = data.get("streak", 0)
    all_reports = data.get("reports", {})
    total_days = len(all_reports)

    for uid in not_reported:
        name = storage.get_user_name(uid, data)
        days_reported = sum(1 for day_reps in all_reports.values() if str(uid) in day_reps)
        acc_score_data = acc.calculate_score(uid)
        acc_score = acc_score_data["total"]
        missing_partner = len(not_reported) == 2  # both missing

        # Personalized message using real data
        personal_msg = ai.generate_personalized_reminder(
            name=name,
            streak=streak,
            days_reported=days_reported,
            total_days=total_days,
            acc_score=acc_score,
            missing_partner=missing_partner,
        )

        lines = [
            f"⏰ <b>Daily Reminder</b>",
            f"━━━━━━━━━━━━━━━━━━━━",
            "",
            f"👤 <b>{safe(name)}</b>",
            "",
            personal_msg,
        ]
        if streak > 0:
            lines.append(
                f"\n🔥 Streak: <b>{streak} day{'s' if streak != 1 else ''}</b> — don't break it."
            )
        lines.append("\n/report ← tap here")

        await bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text="\n".join(lines),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )


async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 <b>StreakBot Menu</b>\n\n"
        "📅 /report  /streak  /summary\n"
        "🧠 /quiz  /interview  /reviews\n"
        "📊 /score  /comparescores  /struggles\n"
        "🎙 /voicecompare\n"
        "🎥 /session start  /session log\n"
        "📋 /progressreport  /progressreport week\n"
        "📚 /lessonpick  /lesson progress\n"
        "📦 /project submit  /project compare\n"
        "⚡ /xp  /leaderboard\n"
        "📅 /weekly  /plan  /stats  /history",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_MENU,
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/help [category] — detailed help per category"""
    args = context.args or []
    cat = args[0].lower() if args else ""

    if cat == "daily":
        text = (
            "📅 <b>Daily Commands</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>/report</b>\n"
            "Submit today's learning. Type naturally or send a voice note.\n"
            "AI extracts: what you learned, time spent, difficulty, next topic.\n"
            "You confirm before saving. Use /cancel to exit.\n\n"
            "<b>/streak</b>\n"
            "Shows the shared dashboard — streak, best streak, both users' status.\n\n"
            "<b>/summary</b>\n"
            "AI summary of today's learning. Both must report first.\n\n"
            "<b>/weekly</b>\n"
            "AI review of the past 7 days with topic list and motivation.\n\n"
            "<b>/history [N]</b>\n"
            "Last N days of reports (default 7, max 30).\n"
            "Example: /history 14"
        )
    elif cat == "learning":
        text = (
            "🧠 <b>Learning Tools</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>/quiz</b>\n"
            "3 questions from today's topics. AI grades each answer 1-5.\n"
            "Use /skipquiz to skip, /cancelquiz to exit.\n\n"
            "<b>/interview</b>\n"
            "Real interview questions from your recent topics.\n"
            "Graded like an actual interviewer — hire/no-hire signal.\n"
            "/interview weekly — uses this week's topics.\n"
            "Use /skipinterview or /cancelinterview.\n\n"
            "<b>/reviews</b>\n"
            "Spaced repetition — topics due for review today (3/7/14 days after studying).\n"
            "/reviews all — see your full schedule.\n"
            "Use /skipreview to skip.\n\n"
            "<b>/voicecompare</b>\n"
            "Both explain the same topic via voice. AI compares clarity, depth, examples.\n"
            "Use /cancelcompare to exit."
        )
    elif cat == "accountability":
        text = (
            "📊 <b>Accountability</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>/score</b>\n"
            "Your accountability score (0-100) across 5 dimensions:\n"
            "Consistency (40) + Voice (20) + Quiz (20) + Study time (10) + Course (10)\n\n"
            "<b>/comparescores</b>\n"
            "Side-by-side comparison with your partner.\n\n"
            "<b>/struggles</b>\n"
            "Topics auto-added when you mark difficulty as hard or score low.\n"
            "/struggles resolve [topic] — mark one as conquered.\n\n"
            "<b>/progressreport</b>\n"
            "Monthly progress report with AI narrative.\n"
            "/progressreport week — this week only."
        )
    elif cat == "course":
        text = (
            "📚 <b>Course Tracker</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>/lessonpick</b>\n"
            "Tap-to-select lesson list with inline buttons. Easiest way to mark lessons.\n\n"
            "<b>/lesson</b> — current lesson status\n"
            "<b>/lesson list</b> — all lessons this week\n"
            "<b>/lesson done video</b> — mark video watched\n"
            "<b>/lesson done notes</b> — mark notes read\n"
            "<b>/lesson done exercise</b> — mark exercise done\n"
            "<b>/lesson progress</b> — full course % bar\n\n"
            "Each lesson needs all 3 steps to count as complete.\n"
            "Next week locks until Friday's project is submitted."
        )
    elif cat == "project":
        text = (
            "📦 <b>Weekly Project</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>/project submit [github url]</b>\n"
            "Submit your GitHub repo. AI reviews code quality, topic match, best practices.\n"
            "Example: /project submit https://github.com/you/week3\n\n"
            "<b>/project status</b>\n"
            "See who submitted this week.\n\n"
            "<b>/project compare</b>\n"
            "Side-by-side AI comparison of both repos.\n\n"
            "Projects are due every Friday.\n"
            "Next week's lessons are locked until you submit."
        )
    elif cat == "session":
        text = (
            "🎥 <b>Live Sessions</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>/session start</b> — begin a live code review session\n"
            "<b>/session end</b> — end it and log the duration\n"
            "<b>/session rate 5 [takeaway]</b> — rate 1-5 and share what you learned\n"
            "Example: /session rate 4 I learned how to structure Express routes\n\n"
            "<b>/session log</b> — session history with stats"
        )
    elif cat == "xp":
        text = (
            "⚡ <b>XP &amp; Levels</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "<b>/xp</b> — your total XP, level, and progress bar\n"
            "<b>/leaderboard</b> — ranking between you and your partner\n\n"
            "<b>How to earn XP:</b>\n"
            "Daily report: +10\n"
            "Voice note (score 6-7): +20\n"
            "Voice note (score 8-9): +30\n"
            "Voice note (score 10): +50\n"
            "Lesson step: +5\n"
            "Lesson complete: +15\n"
            "Weekly project: +50\n"
            "Project score 7-8: +20 bonus\n"
            "Project score 9-10: +40 bonus\n"
            "Review remembered: +15\n"
            "Topic mastered: +30\n"
            "Interview completed: +20\n"
            "Streak milestones: +25 to +500\n\n"
            "<b>10 levels:</b> Beginner → Explorer → Builder → Developer\n"
            "→ Engineer → Senior Dev → Architect → Full Stack Pro\n"
            "→ Tech Lead → Elite Coder"
        )
    else:
        text = (
            "❓ <b>StreakBot Help</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Get detailed help for any category:\n\n"
            "/help daily — report, streak, summary, history\n"
            "/help learning — quiz, interview, reviews, voice compare\n"
            "/help accountability — score, struggles, progress report\n"
            "/help course — lesson tracker, quick-pick\n"
            "/help project — weekly GitHub project\n"
            "/help session — live code review sessions\n"
            "/help xp — XP system, levels, leaderboard\n\n"
            "Or use /about to learn what StreakBot is."
        )

    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=MAIN_MENU)


async def voicetranscript_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/voicetranscript — speaking coach: transcribe + full English analysis."""
    await update.message.reply_text(
        "🎙 <b>Speaking Coach</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Send a voice note and you'll get:\n\n"
        "📝 Full transcription of what you said\n"
        "📊 Fluency score (1-10)\n"
        "✏️ Grammar mistakes with corrections\n"
        "💬 Vocabulary improvements\n"
        "🔇 Filler words detected (um, uh, like...)\n"
        "🔍 Clarity and sentence structure\n"
        "⚡ Speaking pace (words/minute)\n"
        "💼 Interview readiness rating\n"
        "🎯 One daily drill to fix your biggest weakness\n\n"
        "<i>Speak naturally — pretend you're explaining something to a colleague.\n"
        "Use /canceltranscript to exit.</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_MENU,
    )
    return VOICE_TRANSCRIPT_WAIT


async def voicetranscript_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive the voice note, transcribe it, then run full speaking analysis."""
    voice = update.message.voice
    if not voice:
        await update.message.reply_text(
            "That's not a voice note. Send a voice message or use /canceltranscript.",
            parse_mode=ParseMode.HTML,
        )
        return VOICE_TRANSCRIPT_WAIT

    duration = voice.duration
    await update.message.reply_text(
        f"⏳ <i>Transcribing your {duration}s voice note...</i>",
        parse_mode=ParseMode.HTML,
    )

    voice_file = await context.bot.get_file(voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp_path = tmp.name
    await voice_file.download_to_drive(tmp_path)

    try:
        transcript = await voice_module.transcribe_voice(tmp_path)
    finally:
        os.unlink(tmp_path)

    if not transcript:
        await update.message.reply_text(
            "❌ <b>Transcription failed.</b>\n\n"
            "Possible reasons:\n"
            "• GROQ_API_KEY is missing or invalid\n"
            "• Voice was too quiet or unclear\n"
            "• Groq API is temporarily down\n\n"
            "Check your .env file and try again.",
            parse_mode=ParseMode.HTML,
            reply_markup=MAIN_MENU,
        )
        return ConversationHandler.END

    word_count = len(transcript.split())

    # Send the raw transcript first so they can read it immediately
    await update.message.reply_text(
        f"✅ <b>Transcription done!</b>\n\n"
        f"⏱ {duration}s  |  📝 {word_count} words\n\n"
        f"<b>What you said:</b>\n<i>{safe(transcript)}</i>\n\n"
        f"🤖 <i>Analysing your English speaking...</i>",
        parse_mode=ParseMode.HTML,
    )

    # Run full speaking analysis
    analysis = ai.analyze_speaking(transcript, storage.get_user_name(update.effective_user.id), duration)
    report = ai.format_speaking_analysis(
        storage.get_user_name(update.effective_user.id),
        transcript,
        duration,
        analysis,
    )

    await update.message.reply_text(
        report,
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_MENU,
    )

    log.info(f"Voice transcript+analysis by user {update.effective_user.id}: {word_count} words")
    return ConversationHandler.END


async def voicetranscript_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Transcript test cancelled.",
        reply_markup=MAIN_MENU,
    )
    return ConversationHandler.END


async def about_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/about — what StreakBot is and who built it"""
    data = storage.load()
    streak = data.get("streak", 0)
    longest = data.get("longest_streak", 0)
    total_days = len(data.get("reports", {}))
    name1 = storage.get_user_name(USER1_ID, data)
    name2 = storage.get_user_name(USER2_ID, data)

    await update.message.reply_text(
        "🤖 <b>About StreakBot</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "StreakBot is a personal accountability system built for two learning partners "
        "going through the Evangadi Tech full stack bootcamp together.\n\n"
        "<b>What it tracks:</b>\n"
        "Daily learning reports • Streak consistency\n"
        "Voice explanations • Quiz performance\n"
        "Interview readiness • Spaced repetition\n"
        "Course progress • Weekly projects\n"
        "Live sessions • Accountability score\n\n"
        "<b>Powered by:</b>\n"
        "🤖 Groq (llama-3.3-70b + Whisper)\n"
        "📱 python-telegram-bot\n"
        "🐍 Python 3.11\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>This bot's stats:</b>\n"
        f"👥 Partners: {safe(name1)} &amp; {safe(name2)}\n"
        f"🔥 Current streak: {streak} days\n"
        f"🏆 Best streak: {longest} days\n"
        f"📅 Total days tracked: {total_days}\n\n"
        "GitHub: github.com/Muaxacker/streakbot",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_MENU,
    )


async def backup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/backup — send data files to admin (private chat only)"""
    user = update.effective_user
    if user.id not in (USER1_ID, USER2_ID):
        await update.message.reply_text("🚫 Not authorized.")
        return

    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "⚠️ Use /backup in a private chat with the bot for security.",
            parse_mode=ParseMode.HTML,
        )
        return

    import json
    files_to_backup = {
        "data.json": "data.json",
        "xp.json": "xp.json",
        "lessons.json": "lessons.json",
        "sessions.json": "sessions.json",
    }

    sent = 0
    for filename, filepath in files_to_backup.items():
        if os.path.exists(filepath):
            try:
                await context.bot.send_document(
                    chat_id=user.id,
                    document=open(filepath, "rb"),
                    filename=filename,
                    caption=f"📦 Backup: {filename}",
                )
                sent += 1
            except Exception as e:
                log.error(f"Backup send error for {filename}: {e}")

    await update.message.reply_text(
        f"✅ <b>Backup sent!</b>\n\n"
        f"Sent {sent} file(s) to your private chat.\n"
        f"<i>Save these somewhere safe.</i>",
        parse_mode=ParseMode.HTML,
    )
    log.info(f"Backup sent to user {user.id} ({user.first_name})")


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin — admin panel (both users are admins)"""
    user = update.effective_user
    if user.id not in (USER1_ID, USER2_ID):
        await update.message.reply_text("🚫 Not authorized.")
        return

    args = context.args or []

    if not args:
        data = storage.load()
        xp1 = xp_module.get_user_xp(USER1_ID)
        xp2 = xp_module.get_user_xp(USER2_ID)
        name1 = storage.get_user_name(USER1_ID, data)
        name2 = storage.get_user_name(USER2_ID, data)

        # Log file size
        log_size = "—"
        if os.path.exists("streakbot.log"):
            log_size = f"{round(os.path.getsize('streakbot.log') / 1024, 1)} KB"

        lines = [
            "🛠 <b>Admin Panel</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            "",
            f"👤 {safe(name1)}: {xp1} XP",
            f"👤 {safe(name2)}: {xp2} XP",
            f"🔥 Streak: {data['streak']} days",
            f"📅 Total reports: {sum(len(v) for v in data.get('reports', {}).values())}",
            f"📋 Log size: {log_size}",
            "",
            "<b>Admin commands:</b>",
            "/admin broadcast [message] — send to group",
            "/admin resetxp [user_id] — reset XP for a user",
            "/admin logs — get the log file",
            "/backup — download all data files",
            "/resetstreak — reset the streak",
        ]
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
        return

    # /admin broadcast [message]
    if args[0] == "broadcast" and len(args) > 1:
        msg = " ".join(args[1:])
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=f"📢 <b>Admin Message</b>\n\n{escape(msg)}",
            parse_mode=ParseMode.HTML,
        )
        await update.message.reply_text("✅ Broadcast sent to group.")
        log.info(f"Admin broadcast by {user.id}: {msg}")
        return

    # /admin logs
    if args[0] == "logs":
        if os.path.exists("streakbot.log"):
            await context.bot.send_document(
                chat_id=user.id,
                document=open("streakbot.log", "rb"),
                filename="streakbot.log",
                caption="📋 StreakBot log file",
            )
        else:
            await update.message.reply_text("No log file found yet.")
        return

    # /admin resetxp [user_id]
    if args[0] == "resetxp" and len(args) > 1:
        try:
            target_id = int(args[1])
        except ValueError:
            await update.message.reply_text("Usage: /admin resetxp [user_id]")
            return
        import xp as xp_mod
        xp_data = xp_mod.load_xp()
        if str(target_id) in xp_data["users"]:
            xp_data["users"][str(target_id)] = {"total": 0, "history": []}
            xp_mod.save_xp(xp_data)
            await update.message.reply_text(f"✅ XP reset for user {target_id}.")
            log.info(f"XP reset for {target_id} by admin {user.id}")
        else:
            await update.message.reply_text(f"User {target_id} not found in XP data.")
        return

    await update.message.reply_text("Unknown admin command. Use /admin to see options.")


async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Detailed help — /help [daily/learning/course/xp]"),
        BotCommand("about", "What StreakBot is and live stats"),
        BotCommand("report", "Submit today's learning"),
        BotCommand("streak", "View the shared dashboard"),
        BotCommand("summary", "AI summary of today"),
        BotCommand("quiz", "Interactive quiz — AI grades your answers"),
        BotCommand("interview", "Real interview questions from your topics"),
        BotCommand("reviews", "Spaced repetition — review past topics"),
        BotCommand("score", "Your accountability score (0-100)"),
        BotCommand("comparescores", "Compare both accountability scores"),
        BotCommand("struggles", "Your struggle topics"),
        BotCommand("voicecompare", "Compare voice explanations with partner"),
        BotCommand("voicetranscript", "Speaking coach — transcribe + grammar + fluency analysis"),
        BotCommand("session", "Log a live code review session"),
        BotCommand("progressreport", "Monthly or weekly progress report"),
        BotCommand("lessonpick", "Pick a lesson from an interactive list"),
        BotCommand("lesson", "Track Evangadi course lessons"),
        BotCommand("project", "Submit weekly project repo"),
        BotCommand("xp", "View your XP and level"),
        BotCommand("leaderboard", "XP ranking between you two"),
        BotCommand("plan", "Next topics + AI advice"),
        BotCommand("weekly", "Week in review"),
        BotCommand("stats", "Learning stats"),
        BotCommand("history", "Show last N days"),
        BotCommand("backup", "Download your data files (private chat)"),
        BotCommand("admin", "Admin panel"),
        BotCommand("setreminder", "Change reminder time"),
        BotCommand("resetstreak", "Reset the streak"),
    ]
    await bot.set_my_commands(commands)
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())


def main():
    _validate_config()

    # Start health check server for Koyeb (runs on port 8000)
    start_health_server(port=8000)
    log.info("Health check server started on port 8000")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    report_handler = ConversationHandler(
        entry_points=[CommandHandler("report", report_start)],
        states={
            REPORT_WAITING_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, report_receive_text),
                MessageHandler(filters.VOICE, report_receive_voice),
            ],
            REPORT_CONFIRM: [
                CallbackQueryHandler(report_confirm_callback, pattern="^report_"),
            ],
            REPORT_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, report_edit_text),
                MessageHandler(filters.VOICE, report_edit_voice),
            ],
        },
        fallbacks=[CommandHandler("cancel", report_cancel_cmd)],
        per_user=True,
        per_chat=True,
        allow_reentry=True,
    )

    quiz_handler = ConversationHandler(
        entry_points=[CommandHandler("quiz", quiz_cmd)],
        states={
            QUIZ_ANSWER: [
                CommandHandler("skipquiz", quiz_skip),
                MessageHandler(filters.TEXT & ~filters.COMMAND, quiz_answer),
            ],
        },
        fallbacks=[CommandHandler("cancelquiz", quiz_cancel)],
        per_user=True,
        per_chat=True,
        allow_reentry=True,
    )

    app.add_handler(report_handler)
    app.add_handler(quiz_handler)

    transcript_handler = ConversationHandler(
        entry_points=[CommandHandler("voicetranscript", voicetranscript_cmd)],
        states={
            VOICE_TRANSCRIPT_WAIT: [
                MessageHandler(filters.VOICE, voicetranscript_receive),
                CommandHandler("canceltranscript", voicetranscript_cancel),
            ],
        },
        fallbacks=[CommandHandler("canceltranscript", voicetranscript_cancel)],
        per_user=True,
        per_chat=True,
        allow_reentry=True,
    )
    app.add_handler(transcript_handler)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("about", about_cmd))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("backup", backup_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("streak", streak_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("summary", summary_cmd))
    app.add_handler(CommandHandler("weekly", weekly_cmd))
    app.add_handler(CommandHandler("nexttopic", nexttopic_cmd))
    app.add_handler(CommandHandler("plan", plan_cmd))
    app.add_handler(CommandHandler("setreminder", setreminder_cmd))
    app.add_handler(CommandHandler("resetstreak", resetstreak_cmd))

    register_advanced_handlers(app)

    async def schedule_reminder(application):
        reminder_time = storage.get_reminder_time()

        async def reminder_callback(context):
            await send_reminder(context.bot)

        application.job_queue.stop()
        application.job_queue.scheduler.remove_all_jobs()
        application.job_queue.run_daily(
            reminder_callback,
            time=datetime.strptime(reminder_time, "%H:%M").time(),
            name="daily_reminder",
        )

    async def post_init(application):
        await set_bot_commands(application.bot)
        await schedule_reminder(application)
        log.info(f"StreakBot started. Reminder at {storage.get_reminder_time()} daily.")

        # Push the updated keyboard to both users so it refreshes immediately
        for uid in [USER1_ID, USER2_ID]:
            if uid == 0:
                continue
            try:
                name = storage.get_user_name(uid)
                await application.bot.send_message(
                    chat_id=uid,
                    text=(
                        f"🔄 <b>StreakBot restarted</b>\n\n"
                        f"Hey {safe(name)}! Menu updated with all new commands.\n\n"
                        f"New: /interview /reviews /score /voicecompare\n"
                        f"/session /progressreport /lessonpick /struggles"
                    ),
                    parse_mode=ParseMode.HTML,
                    reply_markup=MAIN_MENU,
                )
            except Exception as e:
                log.warning(f"Could not push menu to {uid}: {e}")

    app.post_init = post_init
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
