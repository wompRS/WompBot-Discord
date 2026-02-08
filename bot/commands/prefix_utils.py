"""Shared utilities for prefix commands."""

from features.admin_utils import is_bot_admin, is_super_admin


def is_bot_admin_ctx(db, ctx):
    """Check if a prefix command user is a bot admin."""
    if not ctx.guild:
        return is_super_admin(ctx.author.id)
    return is_bot_admin(db, ctx.guild.id, ctx.author.id)


def parse_choice(value, valid_choices, default=None):
    """Parse a text argument against a list of valid choices."""
    if value is None:
        return default
    value_lower = value.lower().strip()
    for choice in valid_choices:
        if value_lower == choice.lower():
            return choice
    return None
