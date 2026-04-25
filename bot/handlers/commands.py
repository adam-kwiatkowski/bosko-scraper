"""Simple one-shot command handlers (no conversation state)."""

from telegram import Update
from telegram.ext import ContextTypes

from bot.constants import DAILY_JOB_PREFIX
from bot.services import (
    cached_api_search,
    cached_flavor_search,
    find_shop_by_name,
    get_cached_shops,
    normalize,
    get_api,
)
from bot.formatting import format_flavor_name


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """``/start`` — welcome message with command overview."""
    await update.effective_message.reply_text(
        "Welcome to the Ice Cream Bot! 🍦\n"
        "Commands:\n"
        "/shops [query] - List all shops or search by name\n"
        "/products <shop name> - Show products at a shop\n"
        "/search <flavor> - Search for flavors using API\n"
        "/search_available <flavor> - Search for flavors currently available at shops\n"
        "/add_favorite - Add favorite flavors or shops\n"
        "/favorites - Show your favorite flavors and shops\n"
        "/remove_favorite - Remove favorite flavors or shops\n"
        "/daily_updates - Set up daily availability notifications\n"
        "/stop_daily_updates - Stop daily notifications"
    )


async def products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """``/products <shop name>`` — list products at a shop."""
    if not context.args:
        await update.effective_message.reply_text(
            "Please provide a shop name, e.g., /products Ursynów"
        )
        return

    shop_name = " ".join(context.args)
    shop = find_shop_by_name(shop_name)

    if not shop:
        await update.effective_message.reply_text(f"Shop '{shop_name}' not found.")
        return

    shop_products = get_api().products.get_at_shop(shop.id)
    if not shop_products:
        await update.effective_message.reply_text(f"No products found at {shop.name}.")
        return

    reply = f"🍨 *{shop.name}*:\n"
    reply += "\n".join([f"- {format_flavor_name(p.name)}" for p in shop_products])
    await update.effective_message.reply_text(reply, parse_mode="Markdown")


async def shops_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """``/shops [query]`` — list all shops or filter by name."""
    if context.args:
        query_norm = normalize(" ".join(context.args))
        filtered = [
            shop for shop in get_cached_shops() if query_norm in normalize(shop.name)
        ]
    else:
        filtered = get_cached_shops()

    if not filtered:
        await update.effective_message.reply_text("No shops found matching your query.")
        return

    reply = "🏪 Shops:\n" + "\n".join([f"- {shop.name}" for shop in filtered])
    await update.effective_message.reply_text(reply)


async def search_flavor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """``/search <flavor>`` — search flavors via the API."""
    if not context.args:
        await update.effective_message.reply_text(
            "Please provide a flavor to search, e.g., /search mascarpone"
        )
        return

    query = " ".join(context.args)
    results = cached_api_search(query)

    if not results:
        await update.effective_message.reply_text(f"No matches found for '{query}'.")
        return

    reply = f"🔍 Search results for *{query}*:\n"
    for product in results:
        reply += f"- {format_flavor_name(product.name)}\n"

    await update.effective_message.reply_text(reply, parse_mode="Markdown")


async def search_available(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """``/search_available <flavor>`` — search currently stocked flavors across shops."""
    if not context.args:
        await update.effective_message.reply_text(
            "Please provide a flavor to search, e.g., /search_available mascarpone"
        )
        return

    query = " ".join(context.args)
    results = cached_flavor_search(query)

    if not results:
        await update.effective_message.reply_text(f"No matches found for '{query}'.")
        return

    reply = f"🔍 Search results for *{query}*:\n"
    for shop_name, product_name in results:
        reply += f"- {product_name} at *{shop_name}*\n"

    await update.effective_message.reply_text(reply, parse_mode="Markdown")


async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """``/favorites`` — display the user's saved flavors and shops."""
    favorite_flavors = context.user_data.get("favorite_flavors", [])
    favorite_shops = context.user_data.get("favorite_shops", [])

    if not favorite_flavors and not favorite_shops:
        await update.message.reply_text(
            "You don't have any favorites yet! Use /add_favorite to add some."
        )
        return

    reply = "⭐ Your Favorites:\n\n"

    if favorite_flavors:
        reply += "🍦 Favorite Flavors:\n"
        for flavor in favorite_flavors:
            reply += f"- {format_flavor_name(flavor)}\n"
        reply += "\n"

    if favorite_shops:
        reply += "🏪 Favorite Shops:\n"
        for shop in favorite_shops:
            reply += f"- {shop.name}\n"

    await update.message.reply_text(reply)


async def remove_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """``/remove_favorite`` — show removal options for saved favorites."""
    from telegram import ReplyKeyboardMarkup

    favorite_flavors = context.user_data.get("favorite_flavors", [])
    favorite_shops = context.user_data.get("favorite_shops", [])

    if not favorite_flavors and not favorite_shops:
        await update.message.reply_text("You don't have any favorites to remove.")
        return

    keyboard: list[list[str]] = []
    if favorite_flavors:
        keyboard.append(["🍦 Remove Flavors"])
    if favorite_shops:
        keyboard.append(["🏪 Remove Shops"])
    keyboard.append(["❌ Cancel"])

    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text(
        "What would you like to remove from your favorites?", reply_markup=markup
    )


async def stop_daily_updates(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """``/stop_daily_updates`` — cancel all scheduled daily update jobs."""
    job_name = f"{DAILY_JOB_PREFIX}{update.effective_chat.id}"
    existing_jobs = context.job_queue.get_jobs_by_name(job_name)
    if existing_jobs:
        for job in existing_jobs:
            job.schedule_removal()
        context.user_data["daily_updates_config"] = None
        await update.message.reply_text("✅ Daily updates have been stopped.")
    else:
        await update.message.reply_text("❌ No active daily updates to stop.")
