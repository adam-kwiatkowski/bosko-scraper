"""Add-favorite ConversationHandler — flavor and shop selection flows."""

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.constants import (
    CHOOSING_FAVORITE_TYPE,
    CHOOSING_CITY,
    SEARCHING_FLAVOR,
    SEARCHING_SHOP,
    SELECTING_FLAVORS,
    SELECTING_SHOP,
    SELECTING_SHOP_FROM_CITY,
)
from bot.formatting import build_keyboard, reply_cancelled
from bot.services import (
    cached_api_search,
    get_cached_shops,
    get_shops_in_city,
    get_unique_cities,
    normalize,
)


# ── Entry point ─────────────────────────────────────────────────────


async def add_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the add-favorite conversation."""
    keyboard = [["🍦 Flavors", "🏪 Shops"], ["❌ Cancel"]]
    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

    await update.message.reply_text(
        "What would you like to add to your favorites?", reply_markup=markup
    )
    return CHOOSING_FAVORITE_TYPE


# ── Type choice ─────────────────────────────────────────────────────


async def choose_favorite_type(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle the choice between flavors and shops."""
    text = update.message.text.lower()

    if "flavor" in text:
        await update.message.reply_text(
            "🔍 Please type a flavor name to search for (e.g., 'vanilla', 'chocolate'):",
            reply_markup=ReplyKeyboardRemove(),
        )
        return SEARCHING_FLAVOR

    if "shop" in text:
        keyboard = [["🏪 Search by shop name", "🏙️ Browse by city"], ["❌ Cancel"]]
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await update.message.reply_text(
            "How would you like to find shops?", reply_markup=markup
        )
        return SEARCHING_SHOP

    return ConversationHandler.END


# ── Flavor flow ─────────────────────────────────────────────────────


async def search_flavor_for_favorite(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Search for flavors based on user input using the API."""
    query = update.message.text.strip()
    results = cached_api_search(query)

    if not results:
        await update.message.reply_text(
            f"No flavors found matching '{query}'. Please try another search term:"
        )
        return SEARCHING_FLAVOR

    context.user_data["flavor_search_results"] = results
    flavor_names = [product.name for product in results]

    keyboard = build_keyboard(flavor_names, footer=["✅ Done selecting", "❌ Cancel"])
    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False)

    await update.message.reply_text(
        f"Found {len(flavor_names)} flavors matching '{query}':\n"
        "Select the flavors you want to add to favorites (you can select multiple):",
        reply_markup=markup,
    )
    context.user_data["selected_flavors"] = []
    return SELECTING_FLAVORS


async def select_flavors(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle flavor selection (multi-select with ✅ Done)."""
    text = update.message.text.strip()

    if text == "✅ Done selecting":
        selected = context.user_data.get("selected_flavors", [])
        if not selected:
            await update.message.reply_text(
                "No flavors selected. Please select at least one flavor."
            )
            return SELECTING_FLAVORS

        favorites = context.user_data.setdefault("favorite_flavors", [])
        for flavor in selected:
            if flavor not in favorites:
                favorites.append(flavor)

        await update.message.reply_text(
            f"Added {len(selected)} flavors to your favorites! 🍦\n"
            f"Selected: {', '.join(selected)}",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    if text == "❌ Cancel":
        await reply_cancelled(update)
        return ConversationHandler.END

    # Toggle individual flavor
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


# ── Shop flow ───────────────────────────────────────────────────────


async def search_shop_method(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle shop search method choice (by name vs. by city)."""
    text = update.message.text.lower()

    if "shop name" in text:
        await update.message.reply_text(
            "🏪 Please type a shop name to search for:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return SELECTING_SHOP

    if "city" in text:
        cities = get_unique_cities()
        if not cities:
            await update.message.reply_text(
                "No cities found in the database.", reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END

        keyboard = build_keyboard(cities, footer=["❌ Cancel"])
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await update.message.reply_text(
            "Select a city to browse shops:", reply_markup=markup
        )
        return CHOOSING_CITY

    return ConversationHandler.END


async def choose_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle city selection."""
    city = update.message.text.strip()

    if city == "❌ Cancel":
        await reply_cancelled(update)
        return ConversationHandler.END

    shops = get_shops_in_city(city)
    if not shops:
        await update.message.reply_text(
            f"No shops found in {city}. Please select another city."
        )
        return CHOOSING_CITY

    shop_names = [shop.name for shop in shops]
    keyboard = build_keyboard(shop_names, footer=["✅ Done selecting", "❌ Cancel"])
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
    """Handle shop selection from a city or search result list."""
    shop_name = update.message.text.strip()

    if shop_name == "❌ Cancel":
        await reply_cancelled(update)
        return ConversationHandler.END

    if shop_name == "✅ Done selecting":
        selected = context.user_data.get("selected_shops", [])
        if not selected:
            await update.message.reply_text(
                "No shops selected. Please select at least one shop."
            )
            return SELECTING_SHOP_FROM_CITY

        favorites = context.user_data.setdefault("favorite_shops", [])
        added_count = 0
        for shop_info in selected:
            if shop_info not in favorites:
                favorites.append(shop_info)
                added_count += 1

        await update.message.reply_text(
            f"Added {added_count} shops to your favorites! 🏪\n"
            f"Selected: {', '.join([shop.name for shop in selected])}",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    # Lookup from either city browse or name search results
    city_shops = context.user_data.get("city_shops", {})
    search_shops = context.user_data.get("search_shops", {})
    all_shops = {**city_shops, **search_shops}

    if shop_name not in all_shops:
        await update.message.reply_text("Please select a shop from the list.")
        return SELECTING_SHOP_FROM_CITY

    shop = all_shops[shop_name]
    selected = context.user_data.get("selected_shops", [])

    if shop not in selected:
        selected.append(shop)
        context.user_data["selected_shops"] = selected
        await update.message.reply_text(
            f"Added '{shop.name}' to selection. "
            f"Current selection: {', '.join([s.name for s in selected])}"
        )
    else:
        await update.message.reply_text(f"'{shop.name}' is already selected.")

    return SELECTING_SHOP_FROM_CITY


async def select_shop_by_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handle shop selection by free-text name search."""
    query = update.message.text.strip()

    if query.lower() == "cancel":
        await reply_cancelled(update)
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

    # Single match → add immediately
    if len(matching_shops) == 1:
        shop = matching_shops[0]
        favorites = context.user_data.setdefault("favorite_shops", [])

        if shop not in favorites:
            favorites.append(shop)
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

    # Multiple matches → present selection keyboard
    shop_names = [shop.name for shop in matching_shops]
    keyboard = build_keyboard(shop_names, footer=["✅ Done selecting", "❌ Cancel"])
    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False)

    await update.message.reply_text(
        f"Found {len(matching_shops)} shops matching '{query}'. "
        "Select shops (you can select multiple):",
        reply_markup=markup,
    )
    context.user_data["search_shops"] = {shop.name: shop for shop in matching_shops}
    context.user_data["selected_shops"] = []
    return SELECTING_SHOP_FROM_CITY


# ── Cancel fallback ─────────────────────────────────────────────────


async def cancel_conversation(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Shared cancel fallback for any conversation."""
    await reply_cancelled(update)
    return ConversationHandler.END


# ── Handler factory ─────────────────────────────────────────────────


def build_favorites_handler() -> ConversationHandler:
    """Construct and return the add-favorite ``ConversationHandler``."""
    return ConversationHandler(
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
