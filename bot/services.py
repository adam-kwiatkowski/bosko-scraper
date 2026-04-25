"""Data-access layer — cached API calls, normalization, and shop/flavor lookups."""

import logging
import os

from dotenv import load_dotenv
from unidecode import unidecode

from api.client import BoskoAPI
from bot.constants import CACHE_TTL_SECONDS, ALL_SHOPS_LIMIT
from bot.formatting import format_flavor_name
from bot.utils import ttl_cache

load_dotenv()

logger = logging.getLogger(__name__)

# ── API singleton ───────────────────────────────────────────────────
_api: BoskoAPI | None = None


def get_api() -> BoskoAPI:
    """Return the shared API client, creating & authenticating on first call."""
    global _api
    if _api is None:
        _api = BoskoAPI()
        _api.login(os.getenv("EMAIL"), os.getenv("PASSWORD"))
    return _api


# ── Text helpers ────────────────────────────────────────────────────


def normalize(text: str) -> str:
    """Lowercase, strip, and transliterate to ASCII for fuzzy matching."""
    return unidecode(text.strip().lower())


# ── Cached data access ──────────────────────────────────────────────


@ttl_cache(max_age=CACHE_TTL_SECONDS)
def get_cached_shops():
    """Fetch all shops (cached for ``CACHE_TTL_SECONDS``)."""
    return get_api().shops.get_all(limit=ALL_SHOPS_LIMIT)


@ttl_cache(max_age=CACHE_TTL_SECONDS)
def get_products_at_shop(shop_id: int):
    """Fetch products at a specific shop (cached)."""
    return get_api().products.get_at_shop(shop_id)


@ttl_cache(max_age=CACHE_TTL_SECONDS)
def cached_flavor_search(query: str):
    """Search for a flavor across *all* shops by scanning their current product lists."""
    query_norm = normalize(query)
    results = []

    for shop in get_cached_shops():
        try:
            for product in get_products_at_shop(shop.id):
                if query_norm in normalize(product.name):
                    results.append((shop.name, format_flavor_name(product.name)))
        except Exception:
            logger.warning("Error fetching products for %s", shop.name, exc_info=True)

    return results


@ttl_cache(max_age=CACHE_TTL_SECONDS)
def cached_api_search(query: str):
    """Search using the API search endpoint (cached)."""
    try:
        return get_api().products.search(query)
    except Exception:
        logger.warning("Error searching via API for '%s'", query, exc_info=True)
        return []


# ── Lookup helpers ──────────────────────────────────────────────────


def find_shop_by_name(name: str):
    """Return the first shop whose name contains *name* (fuzzy, accent-insensitive)."""
    name_norm = normalize(name)
    for shop in get_cached_shops():
        if name_norm in normalize(shop.name):
            return shop
    return None


def get_unique_cities() -> list[str]:
    """Return sorted unique city names from all known shops."""
    cities = {
        shop.city.name
        for shop in get_cached_shops()
        if hasattr(shop, "city") and hasattr(shop.city, "name")
    }
    return sorted(cities)


def get_shops_in_city(city_name: str):
    """Return all shops located in *city_name*."""
    city_norm = normalize(city_name)
    return [
        shop
        for shop in get_cached_shops()
        if hasattr(shop, "city")
        and hasattr(shop.city, "name")
        and normalize(shop.city.name) == city_norm
    ]
