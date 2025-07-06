import logging
import os

import pytz
from dotenv import load_dotenv
from telegram import Update, BotCommand, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    Application,
    ConversationHandler,
    MessageHandler,
    PicklePersistence,
    filters,
)
from api.client import BoskoAPI
from unidecode import unidecode

from bot.utils import ttl_cache
from datetime import time, datetime
import re

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")

api = BoskoAPI()
api.login(EMAIL, PASSWORD)

(
    CHOOSING_FAVORITE_TYPE,
    SEARCHING_FLAVOR,
    SELECTING_FLAVORS,
    SEARCHING_SHOP,
    SELECTING_SHOP,
    CHOOSING_CITY,
    SELECTING_SHOP_FROM_CITY,
) = range(7)
SETUP_DAILY_UPDATES, SELECTING_TIME, SELECTING_DAYS = range(7, 10)
DEFAULT_TIMEZONE = "Europe/Warsaw"

@ttl_cache(max_age=21600)
def get_cached_shops():
    return api.shops.get_all(limit=999)


@ttl_cache(max_age=21600)
def get_products_at_shop(shop_id: int):
    return api.products.get_at_shop(shop_id)


@ttl_cache(max_age=21600)
def cached_flavor_search(query: str):
    query_norm = normalize(query)
    results = []

    for shop in get_cached_shops():
        try:
            search_results = get_products_at_shop(shop.id)
            for product in search_results:
                if query_norm in normalize(product.name):
                    results.append((shop.name, product.name))
        except Exception as e:
            print(f"Error fetching products for {shop.name}: {e}")

    return results


@ttl_cache(max_age=21600)
def cached_api_search(query: str):
    """Search using the API search endpoint"""
    try:
        search_results = api.products.search(query)
        return search_results
    except Exception as e:
        print(f"Error searching via API: {e}")
        return []


async def check_favorites_availability(context: ContextTypes.DEFAULT_TYPE):
    """Check availability of favorite flavors at favorite shops and send updates"""
    job_data = context.job.data
    chat_id = context.job.chat_id

    favorite_flavors = job_data.get("favorite_flavors", [])
    favorite_shops = job_data.get("favorite_shops", [])

    print(
        f"Checking favorites for chat {chat_id}: {len(favorite_flavors)} flavors, {len(favorite_shops)} shops"
    )

    if not favorite_flavors or not favorite_shops:
        print("No favorites configured")
        return

    found_items = []

    for shop in favorite_shops:
        try:
            product_results = get_products_at_shop(shop.id)
            for product in product_results:
                for flavor in favorite_flavors:
                    if normalize(flavor) in normalize(product.name):
                        found_items.append(f"🍦 {product.name} at *{shop.name}*")
        except Exception as e:
            print(f"Error checking {shop.name}: {e}")

    if found_items:
        message = "📅 *Daily Favorites Update*\n\n"
        message += "\n".join(found_items)
        await context.bot.send_message(
            chat_id=chat_id, text=message, parse_mode="Markdown"
        )
        print(f"Sent update to chat {chat_id}: {len(found_items)} items found")
    else:
        print(f"No matching items found for chat {chat_id}")


def normalize(text: str) -> str:
    return unidecode(text.strip().lower())


def find_shop_by_name(name: str):
    name_norm = normalize(name)
    for shop in get_cached_shops():
        if name_norm in normalize(shop.name):
            return shop
    return None


def get_unique_cities():
    """Get unique cities from all shops"""
    cities = set()
    for shop in get_cached_shops():
        if hasattr(shop, "city") and hasattr(shop.city, "name"):
            cities.add(shop.city.name)
    return sorted(list(cities))


def get_shops_in_city(city_name: str):
    """Get all shops in a specific city"""
    city_norm = normalize(city_name)
    shops = []
    for shop in get_cached_shops():
        if hasattr(shop, "city") and hasattr(shop.city, "name"):
            if normalize(shop.city.name) == city_norm:
                shops.append(shop)
    return shops


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


async def products(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    products = api.products.get_at_shop(shop.id)
    if not products:
        await update.effective_message.reply_text(f"No products found at {shop.name}.")
        return

    reply = f"🍨 Products at *{shop.name}*:\n"
    reply += "\n".join([f"- {p.name} (ID: {p.id})" for p in products])
    await update.effective_message.reply_text(reply, parse_mode="Markdown")


async def shops_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        query = " ".join(context.args)
        query_norm = normalize(query)
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


async def search_flavor(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        reply += f"- {product.name}\n"

    await update.effective_message.reply_text(reply, parse_mode="Markdown")


async def search_available(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


async def add_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the add favorite conversation"""
    reply_keyboard = [["🍦 Flavors", "🏪 Shops"], ["❌ Cancel"]]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    await update.message.reply_text(
        "What would you like to add to your favorites?", reply_markup=markup
    )
    return CHOOSING_FAVORITE_TYPE


async def choose_favorite_type(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle the choice between flavors and shops"""
    text = update.message.text.lower()

    if "flavor" in text:
        await update.message.reply_text(
            "🔍 Please type a flavor name to search for (e.g., 'vanilla', 'chocolate'):",
            reply_markup=ReplyKeyboardRemove(),
        )
        return SEARCHING_FLAVOR
    elif "shop" in text:
        reply_keyboard = [["🏪 Search by shop name", "🏙️ Browse by city"], ["❌ Cancel"]]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        await update.message.reply_text(
            "How would you like to find shops?", reply_markup=markup
        )
        return SEARCHING_SHOP
    else:
        return ConversationHandler.END


async def search_flavor_for_favorite(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Search for flavors based on user input using API search"""
    query = update.message.text.strip()
    results = cached_api_search(query)

    if not results:
        await update.message.reply_text(
            f"No flavors found matching '{query}'. Please try another search term:"
        )
        return SEARCHING_FLAVOR

    context.user_data["flavor_search_results"] = results
    flavor_names = [product.name for product in results]

    keyboard = []
    for i in range(0, len(flavor_names), 2):
        row = flavor_names[i : i + 2]
        keyboard.append(row)
    keyboard.append(["✅ Done selecting", "❌ Cancel"])

    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False)
    await update.message.reply_text(
        f"Found {len(flavor_names)} flavors matching '{query}':\n"
        "Select the flavors you want to add to favorites (you can select multiple):",
        reply_markup=markup,
    )
    context.user_data["selected_flavors"] = []
    return SELECTING_FLAVORS


async def select_flavors(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle flavor selection"""
    text = update.message.text.strip()

    if text == "✅ Done selecting":
        selected = context.user_data.get("selected_flavors", [])
        if not selected:
            await update.message.reply_text(
                "No flavors selected. Please select at least one flavor."
            )
            return SELECTING_FLAVORS

        if "favorite_flavors" not in context.user_data:
            context.user_data["favorite_flavors"] = []

        for flavor in selected:
            if flavor not in context.user_data["favorite_flavors"]:
                context.user_data["favorite_flavors"].append(flavor)

        await update.message.reply_text(
            f"Added {len(selected)} flavors to your favorites! 🍦\n"
            f"Selected: {', '.join(selected)}",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    elif text == "❌ Cancel":
        await update.message.reply_text(
            "Cancelled adding flavors.", reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    else:

        selected = context.user_data.get("selected_flavors", [])
        if text not in selected:
            selected.append(text)
            context.user_data["selected_flavors"] = selected
            await update.message.reply_text(
                f"Added '{text}' to selection. Current selection: {', '.join(selected)}"
            )
        else:
            await update.message.reply_text(f"'{text}' is already selected.")

        return SELECTING_FLAVORS


async def search_shop_method(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle shop search method choice"""
    text = update.message.text.lower()

    if "shop name" in text:
        await update.message.reply_text(
            "🏪 Please type a shop name to search for:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return SELECTING_SHOP
    elif "city" in text:
        cities = get_unique_cities()
        if not cities:
            await update.message.reply_text(
                "No cities found in the database.", reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END

        keyboard = []
        for i in range(0, len(cities), 2):
            row = cities[i : i + 2]
            keyboard.append(row)
        keyboard.append(["❌ Cancel"])

        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await update.message.reply_text(
            "Select a city to browse shops:", reply_markup=markup
        )
        return CHOOSING_CITY
    else:
        return ConversationHandler.END


async def choose_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle city selection"""
    city = update.message.text.strip()

    if city == "❌ Cancel":
        await update.message.reply_text(
            "Cancelled.", reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    shops = get_shops_in_city(city)
    if not shops:
        await update.message.reply_text(
            f"No shops found in {city}. Please select another city."
        )
        return CHOOSING_CITY

    keyboard = []
    for i in range(0, len(shops), 2):
        row = [shop.name for shop in shops[i : i + 2]]
        keyboard.append(row)
    keyboard.append(["✅ Done selecting", "❌ Cancel"])

    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False)
    await update.message.reply_text(
        f"Select shops from {city} (you can select multiple):", reply_markup=markup
    )
    context.user_data["city_shops"] = {shop.name: shop for shop in shops}
    context.user_data["selected_shops"] = []
    return SELECTING_SHOP_FROM_CITY


async def select_shop_from_city(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle shop selection from city"""
    shop_name = update.message.text.strip()

    if shop_name == "❌ Cancel":
        await update.message.reply_text(
            "Cancelled.", reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    if shop_name == "✅ Done selecting":
        selected = context.user_data.get("selected_shops", [])
        if not selected:
            await update.message.reply_text(
                "No shops selected. Please select at least one shop."
            )
            return SELECTING_SHOP_FROM_CITY

        if "favorite_shops" not in context.user_data:
            context.user_data["favorite_shops"] = []

        added_count = 0
        for shop_info in selected:
            if shop_info not in context.user_data["favorite_shops"]:
                context.user_data["favorite_shops"].append(shop_info)
                added_count += 1

        await update.message.reply_text(
            f"Added {added_count} shops to your favorites! 🏪\n"
            f"Selected: {', '.join([shop.name for shop in selected])}",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    city_shops = context.user_data.get("city_shops", {})
    search_shops = context.user_data.get("search_shops", {})
    all_shops = {**city_shops, **search_shops}

    if shop_name not in all_shops:
        await update.message.reply_text("Please select a shop from the list.")
        return SELECTING_SHOP_FROM_CITY

    shop = all_shops[shop_name]

    selected = context.user_data.get("selected_shops", [])
    shop_info = shop

    if shop_info not in selected:
        selected.append(shop_info)
        context.user_data["selected_shops"] = selected
        await update.message.reply_text(
            f"Added '{shop.name}' to selection. Current selection: {', '.join([s.name for s in selected])}"
        )
    else:
        await update.message.reply_text(f"'{shop.name}' is already selected.")

    return SELECTING_SHOP_FROM_CITY


async def select_shop_by_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle shop selection by name search"""
    query = update.message.text.strip()

    if query.lower() == "cancel":
        await update.message.reply_text(
            "Cancelled.", reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    query_norm = normalize(query)
    matching_shops = [
        shop for shop in get_cached_shops() if query_norm in normalize(shop.name)
    ]

    if not matching_shops:
        await update.message.reply_text(
            f"No shops found matching '{query}'. Please try another search term:"
        )
        return SELECTING_SHOP

    if len(matching_shops) == 1:
        shop = matching_shops[0]

        if "favorite_shops" not in context.user_data:
            context.user_data["favorite_shops"] = []

        shop_info = shop
        if shop_info not in context.user_data["favorite_shops"]:
            context.user_data["favorite_shops"].append(shop_info)
            await update.message.reply_text(
                f"Added '{shop.name}' to your favorite shops! 🏪",
                reply_markup=ReplyKeyboardRemove(),
            )
        else:
            await update.message.reply_text(
                f"'{shop.name}' is already in your favorites.",
                reply_markup=ReplyKeyboardRemove(),
            )
        return ConversationHandler.END

    keyboard = []
    for i in range(0, len(matching_shops), 2):
        row = [shop.name for shop in matching_shops[i : i + 2]]
        keyboard.append(row)
    keyboard.append(["✅ Done selecting", "❌ Cancel"])

    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False)
    await update.message.reply_text(
        f"Found {len(matching_shops)} shops matching '{query}'. Select shops (you can select multiple):",
        reply_markup=markup,
    )
    context.user_data["search_shops"] = {shop.name: shop for shop in matching_shops}
    context.user_data["selected_shops"] = []
    return SELECTING_SHOP_FROM_CITY


async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's favorite flavors and shops"""
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
            reply += f"- {flavor}\n"
        reply += "\n"

    if favorite_shops:
        reply += "🏪 Favorite Shops:\n"
        for shop in favorite_shops:
            reply += f"- {shop.name}\n"

    await update.message.reply_text(reply)


async def remove_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove favorites"""
    favorite_flavors = context.user_data.get("favorite_flavors", [])
    favorite_shops = context.user_data.get("favorite_shops", [])

    if not favorite_flavors and not favorite_shops:
        await update.message.reply_text("You don't have any favorites to remove.")
        return

    keyboard = []
    if favorite_flavors:
        keyboard.append(["🍦 Remove Flavors"])
    if favorite_shops:
        keyboard.append(["🏪 Remove Shops"])
    keyboard.append(["❌ Cancel"])

    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text(
        "What would you like to remove from your favorites?", reply_markup=markup
    )


async def setup_daily_updates(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Start the daily updates setup conversation"""
    favorite_flavors = context.user_data.get("favorite_flavors", [])
    favorite_shops = context.user_data.get("favorite_shops", [])

    if not favorite_flavors or not favorite_shops:
        await update.message.reply_text(
            "You need to have both favorite flavors and favorite shops set up first!\n"
            "Use /add_favorite to add some favorites, then try again."
        )
        return ConversationHandler.END

    reply_keyboard = [
        ["⏰ Set Daily Updates", "📋 View Current Settings"],
        ["❌ Cancel"],
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

    current_job = context.user_data.get("daily_updates_job")
    status = "✅ Active" if current_job and current_job.enabled else "❌ Inactive"

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


async def handle_daily_updates_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle daily updates setup choices"""
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
    elif "view current settings" in text:

        current_job = context.user_data.get("daily_updates_job")
        config = context.user_data.get("daily_updates_config")

        if current_job and config:
            update_time = config.get("update_time", "Not set")
            timezone = config.get("timezone", DEFAULT_TIMEZONE)
            days = config.get("days", ())

            day_names = [
                "Sunday",
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
            ]
            selected_days = [day_names[d] for d in days]

            await update.message.reply_text(
                f"📋 *Current Daily Updates Settings*\n\n"
                f"⏰ Time: {update_time} ({timezone})\n"
                f"📅 Days: {', '.join(selected_days)}\n"
                f"📊 Status: ✅ Active\n"
                f"🍦 Monitoring: {len(config.get('favorite_flavors', []))} flavors\n"
                f"🏪 Checking: {len(config.get('favorite_shops', []))} shops",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "📋 *Current Daily Updates Settings*\n\n"
                "📊 Status: ❌ Not configured",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="Markdown",
            )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "Cancelled.", reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END


async def select_update_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle time selection for daily updates"""
    time_text = update.message.text.strip()

    time_pattern = re.compile(r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$")
    if not time_pattern.match(time_text):
        await update.message.reply_text(
            "❌ Invalid time format. Please use HH:MM format (24-hour).\n"
            "Example: 09:00 or 18:30"
        )
        return SELECTING_TIME

    context.user_data["update_time"] = time_text
    context.user_data["timezone"] = DEFAULT_TIMEZONE

    day_names = [
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    ]
    keyboard = []
    for i in range(0, len(day_names), 2):
        row = day_names[i : i + 2]
        keyboard.append(row)
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
    """Handle day selection for daily updates"""
    text = update.message.text.strip()

    if text == "❌ Cancel":
        await update.message.reply_text(
            "Cancelled.", reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    if text == "✅ Done selecting":
        selected_days = context.user_data.get("selected_days", [])
        if not selected_days:
            await update.message.reply_text("Please select at least one day.")
            return SELECTING_DAYS

        return await finalize_daily_updates(update, context)

    if text == "🗓️ All days":
        context.user_data["selected_days"] = [0, 1, 2, 3, 4, 5, 6]
        return await finalize_daily_updates(update, context)

    if text == "💼 Weekdays only":
        context.user_data["selected_days"] = [1, 2, 3, 4, 5]
        return await finalize_daily_updates(update, context)

    day_names = [
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    ]
    if text in day_names:
        day_index = day_names.index(text)
        selected_days = context.user_data.get("selected_days", [])

        if day_index not in selected_days:
            selected_days.append(day_index)
            context.user_data["selected_days"] = selected_days
            selected_names = [day_names[d] for d in sorted(selected_days)]
            await update.message.reply_text(
                f"Added {text}. Selected days: {', '.join(selected_names)}"
            )
        else:
            await update.message.reply_text(f"{text} is already selected.")

    return SELECTING_DAYS


async def finalize_daily_updates(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Finalize the daily updates setup"""
    update_time = context.user_data.get("update_time")
    selected_days = context.user_data.get("selected_days", [])
    timezone = context.user_data.get("timezone", DEFAULT_TIMEZONE)

    hour, minute = map(int, update_time.split(":"))

    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    update_time_obj = time(hour, minute, tzinfo=tz)

    existing_job = context.user_data.get("daily_updates_job")
    if existing_job:
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

    job = context.job_queue.run_daily(
        callback=check_favorites_availability,
        time=update_time_obj,
        days=tuple(selected_days),
        data=job_data,
        chat_id=update.effective_chat.id,
        name=f"daily_updates_{update.effective_chat.id}",
    )

    context.user_data["daily_updates_job"] = job
    context.user_data["daily_updates_config"] = job_data

    day_names = [
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    ]
    selected_day_names = [day_names[d] for d in sorted(selected_days)]

    await update.message.reply_text(
        f"✅ *Daily Updates Configured!*\n\n"
        f"⏰ Time: {update_time} ({timezone})\n"
        f"📅 Days: {', '.join(selected_day_names)}\n"
        f"🍦 Monitoring {len(context.user_data.get('favorite_flavors', []))} flavors\n"
        f"🏪 Checking {len(context.user_data.get('favorite_shops', []))} shops\n\n"
        f"You'll receive daily notifications when your favorite flavors are available at your favorite shops!",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )

    return ConversationHandler.END


async def stop_daily_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop daily updates"""
    existing_job = context.user_data.get("daily_updates_job")
    if existing_job:
        existing_job.schedule_removal()
        context.user_data["daily_updates_job"] = None
        context.user_data["daily_updates_config"] = None
        await update.message.reply_text("✅ Daily updates have been stopped.")
    else:
        await update.message.reply_text("❌ No active daily updates to stop.")


async def cancel_conversation(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Cancel the conversation"""
    await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


async def post_init(application: Application) -> None:
    commands_en = [
        BotCommand("start", "Welcome message"),
        BotCommand("shops", "List all shops or search by name"),
        BotCommand("products", "Show products at a shop (e.g., /products Ursynów)"),
        BotCommand("search", "Search for flavors using API (e.g., /search mascarpone)"),
        BotCommand(
            "search_available", "Search for flavors currently available at shops"
        ),
        BotCommand("add_favorite", "Add favorite flavors or shops"),
        BotCommand("favorites", "Show your favorite flavors and shops"),
        BotCommand("remove_favorite", "Remove favorite flavors or shops"),
        BotCommand("daily_updates", "Set up daily availability notifications"),
        BotCommand("stop_daily_updates", "Stop daily notifications"),
    ]
    await application.bot.set_my_commands(commands_en)


def main():
    data_file_path = os.getenv("DATA_FILE_PATH", "./data/bot_data")
    persistence = PicklePersistence(filepath=data_file_path)

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .persistence(persistence)
        .post_init(post_init)
        .build()
    )

    favorites_handler = ConversationHandler(
        entry_points=[CommandHandler("add_favorite", add_favorite)],
        states={
            CHOOSING_FAVORITE_TYPE: [
                MessageHandler(filters.Regex("^🍦 Flavors$"), choose_favorite_type),
                MessageHandler(filters.Regex("^🏪 Shops$"), choose_favorite_type),
            ],
            SEARCHING_FLAVOR: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, search_flavor_for_favorite
                )
            ],
            SELECTING_FLAVORS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_flavors)
            ],
            SEARCHING_SHOP: [
                MessageHandler(
                    filters.Regex("^🏪 Search by shop name$"), search_shop_method
                ),
                MessageHandler(filters.Regex("^🏙️ Browse by city$"), search_shop_method),
            ],
            CHOOSING_CITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, choose_city)
            ],
            SELECTING_SHOP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_shop_by_name)
            ],
            SELECTING_SHOP_FROM_CITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_shop_from_city)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^❌ Cancel$"), cancel_conversation),
            CommandHandler("cancel", cancel_conversation),
        ],
        name="favorites_conversation",
        persistent=True,
    )

    daily_updates_handler = ConversationHandler(
        entry_points=[CommandHandler("daily_updates", setup_daily_updates)],
        states={
            SETUP_DAILY_UPDATES: [
                MessageHandler(
                    filters.Regex("^⏰ Set Daily Updates$"), handle_daily_updates_choice
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

    app.add_handler(favorites_handler)
    app.add_handler(daily_updates_handler)
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
