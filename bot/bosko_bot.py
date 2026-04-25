"""Bosko Ice Cream Bot — application entry point and wiring."""

import logging
import os

from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    Application,
    PicklePersistence,
)

from bot.handlers.commands import (
    start,
    products,
    shops_command,
    search_flavor,
    search_available,
    show_favorites,
    remove_favorite,
    stop_daily_updates,
)
from bot.handlers.favorites import build_favorites_handler
from bot.handlers.daily_updates import build_daily_updates_handler, restore_daily_jobs

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")


# ── Bot commands shown in Telegram menu ─────────────────────────────

BOT_COMMANDS = [
    BotCommand("start", "Welcome message"),
    BotCommand("shops", "List all shops or search by name"),
    BotCommand("products", "Show products at a shop (e.g., /products Ursynów)"),
    BotCommand("search", "Search for flavors using API (e.g., /search mascarpone)"),
    BotCommand("search_available", "Search for flavors currently available at shops"),
    BotCommand("add_favorite", "Add favorite flavors or shops"),
    BotCommand("favorites", "Show your favorite flavors and shops"),
    BotCommand("remove_favorite", "Remove favorite flavors or shops"),
    BotCommand("daily_updates", "Set up daily availability notifications"),
    BotCommand("stop_daily_updates", "Stop daily notifications"),
]


# ── Post-init hook ──────────────────────────────────────────────────


async def post_init(application: Application) -> None:
    """Register bot commands and restore persisted daily-update jobs."""
    await application.bot.set_my_commands(BOT_COMMANDS)
    await restore_daily_jobs(application)


# ── Application factory ─────────────────────────────────────────────


def main() -> None:
    """Build, wire, and run the bot."""
    data_file_path = os.getenv("DATA_FILE_PATH", "./data/bot_data")
    persistence = PicklePersistence(filepath=data_file_path)

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .persistence(persistence)
        .post_init(post_init)
        .build()
    )

    # Conversation handlers (must be registered before simple command handlers)
    app.add_handler(build_favorites_handler())
    app.add_handler(build_daily_updates_handler())

    # Simple command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("products", products))
    app.add_handler(CommandHandler("shops", shops_command))
    app.add_handler(CommandHandler("search", search_flavor))
    app.add_handler(CommandHandler("search_available", search_available))
    app.add_handler(CommandHandler("favorites", show_favorites))
    app.add_handler(CommandHandler("remove_favorite", remove_favorite))
    app.add_handler(CommandHandler("stop_daily_updates", stop_daily_updates))

    logger.info("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
