import os
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes, Application,
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "Welcome to the Ice Cream Bot! 🍦\n"
        "Commands:\n"
        "/shops [query] - List all shops or search by name\n"
        "/products <shop name> - Show products at a shop"
    )


async def products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("Please provide a shop name, e.g., /products Ursynów")
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
        filtered = [shop for shop in get_cached_shops() if query_norm in normalize(shop.name)]
    else:
        filtered = get_cached_shops()

    if not filtered:
        await update.effective_message.reply_text("No shops found matching your query.")
        return

    reply = "🏪 Shops:\n" + "\n".join([f"- {shop.name}" for shop in filtered])
    await update.effective_message.reply_text(reply)

async def search_flavor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("Please provide a flavor to search, e.g., /search mascarpone")
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

async def post_init(application: Application) -> None:
    commands_en = [
        BotCommand("start", "Welcome message"),
        BotCommand("shops", "List all shops or search by name"),
        BotCommand("products", "Show products at a shop (e.g., /products Ursynów)"),
        BotCommand("search", "Search for a flavor across all shops (e.g., /search mascarpone)")
    ]

    await application.bot.set_my_commands(commands_en)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("products", products))
    app.add_handler(CommandHandler("shops", shops_command))
    app.add_handler(CommandHandler("search", search_flavor))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
