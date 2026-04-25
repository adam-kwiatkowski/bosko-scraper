"""Daily-updates ConversationHandler — scheduling, job callbacks, and persistence restoration."""

import logging
import re

from zoneinfo import ZoneInfo
from datetime import time

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.constants import (
    ALL_DAYS,
    DAILY_JOB_PREFIX,
    DAY_NAMES,
    DEFAULT_TIMEZONE,
    SELECTING_DAYS,
    SELECTING_TIME,
    SETUP_DAILY_UPDATES,
    WEEKDAYS,
)
from bot.formatting import build_keyboard, reply_cancelled
from bot.services import get_products_at_shop, normalize

logger = logging.getLogger(__name__)

TIME_PATTERN = re.compile(r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$")


# ── Job callback ────────────────────────────────────────────────────


async def check_favorites_availability(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled job callback — check favorite flavors at favorite shops and notify."""
    job_data = context.job.data
    chat_id = context.job.chat_id

    favorite_flavors = job_data.get("favorite_flavors", [])
    favorite_shops = job_data.get("favorite_shops", [])

    logger.info(
        "Checking favorites for chat %s: %d flavors, %d shops",
        chat_id,
        len(favorite_flavors),
        len(favorite_shops),
    )

    if not favorite_flavors or not favorite_shops:
        logger.info("No favorites configured for chat %s", chat_id)
        return

    found_items: list[str] = []

    for shop in favorite_shops:
        try:
            for product in get_products_at_shop(shop.id):
                for flavor in favorite_flavors:
                    if normalize(flavor) in normalize(product.name):
                        found_items.append(f"🍦 {product.name} at *{shop.name}*")
        except Exception:
            logger.warning("Error checking shop %s", shop.name, exc_info=True)

    if found_items:
        message = "📅 *Daily Favorites Update*\n\n" + "\n".join(found_items)
        await context.bot.send_message(
            chat_id=chat_id, text=message, parse_mode="Markdown"
        )
        logger.info("Sent update to chat %s: %d items found", chat_id, len(found_items))
    else:
        logger.info("No matching items found for chat %s", chat_id)


# ── Conversation entry ──────────────────────────────────────────────


async def setup_daily_updates(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """``/daily_updates`` — start the daily-updates setup conversation."""
    favorite_flavors = context.user_data.get("favorite_flavors", [])
    favorite_shops = context.user_data.get("favorite_shops", [])

    if not favorite_flavors or not favorite_shops:
        await update.message.reply_text(
            "You need to have both favorite flavors and favorite shops set up first!\n"
            "Use /add_favorite to add some favorites, then try again."
        )
        return ConversationHandler.END

    job_name = f"{DAILY_JOB_PREFIX}{update.effective_chat.id}"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    status = "✅ Active" if current_jobs else "❌ Inactive"

    keyboard = [
        ["⏰ Set Daily Updates", "📋 View Current Settings"],
        ["❌ Cancel"],
    ]
    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

    await update.message.reply_text(
        f"📅 *Daily Updates Setup*\n\n"
        f"Current status: {status}\n\n"
        f"Favorite flavors: {len(favorite_flavors)} items\n"
        f"Favorite shops: {len(favorite_shops)} shops\n\n"
        f"What would you like to do?",
        reply_markup=markup,
        parse_mode="Markdown",
    )
    return SETUP_DAILY_UPDATES


# ── Conversation states ─────────────────────────────────────────────


async def handle_daily_updates_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle the initial menu choice (set / view / cancel)."""
    text = update.message.text.lower()

    if "set daily updates" in text:
        await update.message.reply_text(
            "🕐 Please enter the time you'd like to receive daily updates.\n"
            "Format: HH:MM (24-hour format)\n"
            "Example: 09:00 or 18:30\n"
            "Time will be set for Europe/Warsaw timezone.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return SELECTING_TIME

    if "view current settings" in text:
        await _show_current_settings(update, context)
        return ConversationHandler.END

    await reply_cancelled(update)
    return ConversationHandler.END


async def _show_current_settings(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Display the user's current daily-update configuration."""
    job_name = f"{DAILY_JOB_PREFIX}{update.effective_chat.id}"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    config = context.user_data.get("daily_updates_config")

    if current_jobs and config:
        update_time = config.get("update_time", "Not set")
        timezone = config.get("timezone", DEFAULT_TIMEZONE)
        days = config.get("days", ())
        selected_days = [DAY_NAMES[d] for d in days]

        flavors_text = "\n".join(
            f"\t- {flavor}" for flavor in config.get("favorite_flavors", [])
        )
        shops_text = "\n".join(
            f"\t- {shop.name}" for shop in config.get("favorite_shops", [])
        )

        await update.message.reply_text(
            f"📋 *Current Daily Updates Settings*\n\n"
            f"⏰ Time: {update_time} ({timezone})\n"
            f"📅 Days: {', '.join(selected_days)}\n"
            f"📊 Status: ✅ Active\n"
            f"🍦 Flavors:\n{flavors_text}\n\n"
            f"🏪 Shops:\n{shops_text}",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "📋 *Current Daily Updates Settings*\n\n" "📊 Status: ❌ Not configured",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="Markdown",
        )


async def select_update_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle time input (HH:MM) for daily updates."""
    time_text = update.message.text.strip()

    if not TIME_PATTERN.match(time_text):
        await update.message.reply_text(
            "❌ Invalid time format. Please use HH:MM format (24-hour).\n"
            "Example: 09:00 or 18:30"
        )
        return SELECTING_TIME

    context.user_data["update_time"] = time_text
    context.user_data["timezone"] = DEFAULT_TIMEZONE

    day_labels = list(DAY_NAMES)
    keyboard = build_keyboard(day_labels)
    keyboard.append(["✅ Done selecting", "🗓️ All days", "💼 Weekdays only"])
    keyboard.append(["❌ Cancel"])

    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False)
    await update.message.reply_text(
        f"⏰ Time set to {time_text} (Europe/Warsaw timezone)\n\n"
        f"📅 Now select the days you want to receive updates (you can select multiple):",
        reply_markup=markup,
    )

    context.user_data["selected_days"] = []
    return SELECTING_DAYS


async def select_update_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle day selection for daily updates."""
    text = update.message.text.strip()

    if text == "❌ Cancel":
        await reply_cancelled(update)
        return ConversationHandler.END

    if text == "✅ Done selecting":
        selected_days = context.user_data.get("selected_days", [])
        if not selected_days:
            await update.message.reply_text("Please select at least one day.")
            return SELECTING_DAYS
        return await _finalize_daily_updates(update, context)

    if text == "🗓️ All days":
        context.user_data["selected_days"] = list(ALL_DAYS)
        return await _finalize_daily_updates(update, context)

    if text == "💼 Weekdays only":
        context.user_data["selected_days"] = list(WEEKDAYS)
        return await _finalize_daily_updates(update, context)

    if text in DAY_NAMES:
        day_index = DAY_NAMES.index(text)
        selected_days = context.user_data.get("selected_days", [])

        if day_index not in selected_days:
            selected_days.append(day_index)
            context.user_data["selected_days"] = selected_days
            selected_names = [DAY_NAMES[d] for d in sorted(selected_days)]
            await update.message.reply_text(
                f"Added {text}. Selected days: {', '.join(selected_names)}"
            )
        else:
            await update.message.reply_text(f"{text} is already selected.")

    return SELECTING_DAYS


# ── Finalization ────────────────────────────────────────────────────


async def _finalize_daily_updates(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Schedule the daily job and persist the configuration."""
    update_time = context.user_data.get("update_time")
    selected_days = context.user_data.get("selected_days", [])
    timezone = context.user_data.get("timezone", DEFAULT_TIMEZONE)

    hour, minute = map(int, update_time.split(":"))
    tz = ZoneInfo(timezone)
    update_time_obj = time(hour, minute, tzinfo=tz)

    # Remove any existing job for this chat
    job_name = f"{DAILY_JOB_PREFIX}{update.effective_chat.id}"
    for existing_job in context.job_queue.get_jobs_by_name(job_name):
        existing_job.schedule_removal()

    job_data = {
        "update_time": update_time,
        "days": tuple(selected_days),
        "timezone": timezone,
        "favorite_flavors": context.user_data.get("favorite_flavors", []),
        "favorite_shops": context.user_data.get("favorite_shops", []),
        "user_id": update.effective_user.id,
        "chat_id": update.effective_chat.id,
    }

    context.job_queue.run_daily(
        callback=check_favorites_availability,
        time=update_time_obj,
        days=tuple(selected_days),
        data=job_data,
        chat_id=update.effective_chat.id,
        name=job_name,
    )

    context.user_data["daily_updates_config"] = job_data

    selected_day_names = [DAY_NAMES[d] for d in sorted(selected_days)]
    num_flavors = len(context.user_data.get("favorite_flavors", []))
    num_shops = len(context.user_data.get("favorite_shops", []))

    await update.message.reply_text(
        f"✅ *Daily Updates Configured!*\n\n"
        f"⏰ Time: {update_time} ({timezone})\n"
        f"📅 Days: {', '.join(selected_day_names)}\n"
        f"🍦 Monitoring {num_flavors} flavors\n"
        f"🏪 Checking {num_shops} shops\n\n"
        f"You'll receive daily notifications when your favorite flavors "
        f"are available at your favorite shops!",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


# ── Cancel fallback ─────────────────────────────────────────────────


async def cancel_conversation(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Shared cancel fallback."""
    await reply_cancelled(update)
    return ConversationHandler.END


# ── Persistence restoration ─────────────────────────────────────────


async def restore_daily_jobs(application: Application) -> None:
    """Re-schedule daily update jobs from persisted user data (called in ``post_init``)."""
    restored = 0
    for user_id, data in application.user_data.items():
        config = data.get("daily_updates_config")
        if not config:
            continue

        try:
            update_time_str = config.get("update_time")
            days = config.get("days", ())
            timezone = config.get("timezone", DEFAULT_TIMEZONE)
            chat_id = config.get("chat_id")

            if not update_time_str or not days or not chat_id:
                continue

            hour, minute = map(int, update_time_str.split(":"))
            tz = ZoneInfo(timezone)
            update_time_obj = time(hour, minute, tzinfo=tz)

            job_data = {
                "update_time": update_time_str,
                "days": days,
                "timezone": timezone,
                "favorite_flavors": data.get("favorite_flavors", []),
                "favorite_shops": data.get("favorite_shops", []),
                "user_id": user_id,
                "chat_id": chat_id,
            }

            application.job_queue.run_daily(
                callback=check_favorites_availability,
                time=update_time_obj,
                days=tuple(days),
                data=job_data,
                chat_id=chat_id,
                name=f"{DAILY_JOB_PREFIX}{chat_id}",
            )
            restored += 1
            logger.info(
                "Restored daily updates for chat %s at %s (%s)",
                chat_id,
                update_time_str,
                timezone,
            )
        except Exception:
            logger.error(
                "Failed to restore daily updates for user %s",
                user_id,
                exc_info=True,
            )

    if restored:
        logger.info("Restored %d daily update job(s) from persistence", restored)


# ── Handler factory ─────────────────────────────────────────────────


def build_daily_updates_handler() -> ConversationHandler:
    """Construct and return the daily-updates ``ConversationHandler``."""
    return ConversationHandler(
        entry_points=[CommandHandler("daily_updates", setup_daily_updates)],
        states={
            SETUP_DAILY_UPDATES: [
                MessageHandler(
                    filters.Regex("^⏰ Set Daily Updates$"),
                    handle_daily_updates_choice,
                ),
                MessageHandler(
                    filters.Regex("^📋 View Current Settings$"),
                    handle_daily_updates_choice,
                ),
            ],
            SELECTING_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_update_time)
            ],
            SELECTING_DAYS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_update_days)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Cancel$"), cancel_conversation),
            CommandHandler("cancel", cancel_conversation),
        ],
        name="daily_updates_conversation",
        persistent=True,
    )
