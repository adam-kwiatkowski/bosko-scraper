"""Bot-wide constants — conversation states, day names, environment-driven settings."""

import os

# ── Conversation States ─────────────────────────────────────────────
# Favorites conversation
CHOOSING_FAVORITE_TYPE, SEARCHING_FLAVOR, SELECTING_FLAVORS = range(3)
SEARCHING_SHOP, SELECTING_SHOP, CHOOSING_CITY, SELECTING_SHOP_FROM_CITY = range(3, 7)

# Daily-updates conversation
SETUP_DAILY_UPDATES, SELECTING_TIME, SELECTING_DAYS = range(7, 10)

# ── Environment-driven settings (with sensible defaults) ────────────
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "21600"))  # default: 6 hours
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Europe/Warsaw")

# ── API defaults ────────────────────────────────────────────────────
ALL_SHOPS_LIMIT = 999

# ── Day helpers ─────────────────────────────────────────────────────
DAY_NAMES = (
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
)
ALL_DAYS = tuple(range(7))  # (0, 1, 2, 3, 4, 5, 6)
WEEKDAYS = (1, 2, 3, 4, 5)  # Monday–Friday

# ── Job naming ──────────────────────────────────────────────────────
DAILY_JOB_PREFIX = "daily_updates_"
