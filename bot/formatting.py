"""Reusable UI helpers — keyboard builders and common reply shortcuts."""

from telegram import Update, ReplyKeyboardRemove


def build_keyboard(
    items: list[str],
    columns: int = 2,
    footer: list[str] | None = None,
) -> list[list[str]]:
    """Build a reply-keyboard grid from a flat list of labels.

    Args:
        items: Button labels.
        columns: Number of buttons per row (default 2).
        footer: Optional extra row appended at the bottom (e.g. ``["✅ Done", "❌ Cancel"]``).

    Returns:
        A list-of-lists suitable for ``ReplyKeyboardMarkup``.
    """
    keyboard = [items[i : i + columns] for i in range(0, len(items), columns)]
    if footer:
        keyboard.append(footer)
    return keyboard


def format_flavor_name(name: str) -> str:
    """Format an ice cream flavor name for display (e.g., capitalize first letter)."""
    if not name:
        return name
    # Using capitalize() converts the first char to uppercase and the rest to lowercase.
    return name.capitalize()


async def reply_cancelled(update: Update) -> None:
    """Send the standard "Cancelled." reply and remove the custom keyboard."""
    await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
