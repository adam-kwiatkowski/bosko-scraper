import os
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

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")

# Initialize BoskoAPI client and login
api = BoskoAPI()
api.login(EMAIL, PASSWORD)

# Conversation states
(
    CHOOSING_FAVORITE_TYPE,
    SEARCHING_FLAVOR,
    SELECTING_FLAVORS,
    SEARCHING_SHOP,
    SELECTING_SHOP,
    CHOOSING_CITY,
    SELECTING_SHOP_FROM_CITY,
) = range(7)


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
        "/search <flavor> - Search for a flavor across all shops\n"
        "/add_favorite - Add favorite flavors or shops\n"
        "/favorites - Show your favorite flavors and shops\n"
        "/remove_favorite - Remove favorite flavors or shops"
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
    results = cached_flavor_search(query)

    if not results:
        await update.effective_message.reply_text(f"No matches found for '{query}'.")
        return

    reply = f"🔍 Search results for *{query}*:\n"
    for shop_name, product_name in results:
        reply += f"- {product_name} at *{shop_name}*\n"

    await update.effective_message.reply_text(reply, parse_mode="Markdown")


# Favorites functionality
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
    """Search for flavors based on user input"""
    query = update.message.text.strip()
    results = cached_flavor_search(query)

    if not results:
        await update.message.reply_text(
            f"No flavors found matching '{query}'. Please try another search term:"
        )
        return SEARCHING_FLAVOR

    # Store search results and create keyboard
    context.user_data["flavor_search_results"] = results
    unique_flavors = list(set([product_name for _, product_name in results]))

    # Create keyboard with max 2 items per row
    keyboard = []
    for i in range(0, len(unique_flavors), 2):
        row = unique_flavors[i : i + 2]
        keyboard.append(row)
    keyboard.append(["✅ Done selecting", "❌ Cancel"])

    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False)
    await update.message.reply_text(
        f"Found {len(unique_flavors)} flavors matching '{query}':\n"
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

        # Save to favorites
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
        # Add flavor to selection
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

        # Create keyboard with cities
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

    # Create keyboard with shops
    keyboard = []
    for i in range(0, len(shops), 2):
        row = [shop.name for shop in shops[i : i + 2]]
        keyboard.append(row)
    keyboard.append(["❌ Cancel"])

    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text(f"Pick a shop from {city}:", reply_markup=markup)
    context.user_data["city_shops"] = {shop.name: shop for shop in shops}
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

    city_shops = context.user_data.get("city_shops", {})
    if shop_name not in city_shops:
        await update.message.reply_text("Please select a shop from the list.")
        return SELECTING_SHOP_FROM_CITY

    shop = city_shops[shop_name]

    # Add to favorites
    if "favorite_shops" not in context.user_data:
        context.user_data["favorite_shops"] = []

    shop_info = {"name": shop.name, "id": shop.id}
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

    # Search for shops
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
        # Add to favorites
        if "favorite_shops" not in context.user_data:
            context.user_data["favorite_shops"] = []

        shop_info = {"name": shop.name, "id": shop.id}
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

    # Multiple matches - let user choose
    keyboard = []
    for i in range(0, len(matching_shops), 2):
        row = [shop.name for shop in matching_shops[i : i + 2]]
        keyboard.append(row)
    keyboard.append(["❌ Cancel"])

    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text(
        f"Found {len(matching_shops)} shops matching '{query}'. Select one:",
        reply_markup=markup,
    )
    context.user_data["search_shops"] = {shop.name: shop for shop in matching_shops}
    return SELECTING_SHOP_FROM_CITY  # Reuse the same handler


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
            reply += f"- {shop['name']}\n"

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
        BotCommand(
            "search", "Search for a flavor across all shops (e.g., /search mascarpone)"
        ),
        BotCommand("add_favorite", "Add favorite flavors or shops"),
        BotCommand("favorites", "Show your favorite flavors and shops"),
        BotCommand("remove_favorite", "Remove favorite flavors or shops"),
    ]

    await application.bot.set_my_commands(commands_en)


def main():
    # Create persistence
    persistence = PicklePersistence(filepath="ice_cream_bot_data")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .persistence(persistence)
        .post_init(post_init)
        .build()
    )

    # Add conversation handler for favorites
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

    # Add handlers
    app.add_handler(favorites_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("products", products))
    app.add_handler(CommandHandler("shops", shops_command))
    app.add_handler(CommandHandler("search", search_flavor))
    app.add_handler(CommandHandler("favorites", show_favorites))
    app.add_handler(CommandHandler("remove_favorite", remove_favorite))

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
