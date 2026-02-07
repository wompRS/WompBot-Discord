"""
Admin Utilities for WompBot

Provides centralized admin checking functionality with per-server configuration.

Admin hierarchy:
1. Super Admins (SUPER_ADMIN_IDS env) - Can manage admins in any server
2. Server Admins (per-server database) - Bot admin for specific servers
3. Discord Admins (guild permissions) - Optional fallback for some commands
"""

import os
from typing import Optional, List, Set
import discord


# Cache super admin IDs at module load
def _load_super_admins() -> Set[int]:
    """Load super admin IDs from environment"""
    ids_str = os.getenv('SUPER_ADMIN_IDS', '')
    # Also check legacy WOMPIE_USER_ID for backwards compatibility
    legacy_id = os.getenv('WOMPIE_USER_ID', '')

    ids = set()

    # Parse SUPER_ADMIN_IDS (comma-separated)
    for id_str in ids_str.split(','):
        id_str = id_str.strip()
        if id_str.isdigit():
            ids.add(int(id_str))

    # Add legacy Wompie ID if set
    if legacy_id.strip().isdigit():
        ids.add(int(legacy_id))

    return ids


SUPER_ADMIN_IDS: Set[int] = _load_super_admins()


def is_super_admin(user_id: int) -> bool:
    """
    Check if user is a super admin (can manage any server).

    Super admins are defined in SUPER_ADMIN_IDS or WOMPIE_USER_ID env vars.
    """
    return user_id in SUPER_ADMIN_IDS


def is_bot_admin(db, guild_id: int, user_id: int, include_discord_admin: bool = False) -> bool:
    """
    Check if user is a bot admin for a specific server.

    Args:
        db: Database instance
        guild_id: Discord guild/server ID
        user_id: Discord user ID to check
        include_discord_admin: If True, Discord server admins also count as bot admins

    Returns:
        True if user is a bot admin for this server
    """
    # Super admins are admins everywhere
    if is_super_admin(user_id):
        return True

    # Check server-specific admin status
    if db.is_server_admin(guild_id, user_id):
        return True

    return False


def is_bot_admin_interaction(db, interaction: discord.Interaction, include_discord_admin: bool = False) -> bool:
    """
    Check if the user in an interaction is a bot admin.

    Convenience wrapper for slash commands.
    """
    if not interaction.guild:
        # In DMs, only super admins have admin powers
        return is_super_admin(interaction.user.id)

    # Check bot admin status
    if is_bot_admin(db, interaction.guild.id, interaction.user.id):
        return True

    # Optional: also accept Discord server admins
    if include_discord_admin and interaction.user.guild_permissions.administrator:
        return True

    return False


def get_admin_ids_for_guild(db, guild_id: int) -> List[int]:
    """
    Get all bot admin user IDs for a guild.

    Returns list of user IDs including super admins and server-specific admins.
    """
    ids = list(SUPER_ADMIN_IDS)

    server_admins = db.get_server_admins(guild_id)
    for admin in server_admins:
        if admin['user_id'] not in ids:
            ids.append(admin['user_id'])

    return ids


async def admin_check_response(interaction: discord.Interaction, db) -> bool:
    """
    Standard admin check with automatic error response.

    Returns True if user is admin, False otherwise (and sends error message).
    """
    if is_bot_admin_interaction(db, interaction):
        return True

    await interaction.response.send_message(
        "You don't have permission to use this command. "
        "Only bot admins can use this.",
        ephemeral=True
    )
    return False


def format_admin_check_error(include_how_to: bool = True) -> str:
    """Format a standard admin check error message."""
    msg = "You don't have permission to use this command."
    if include_how_to:
        msg += "\n\nBot admins can be set by:\n"
        msg += "- Super admins (set in bot config)\n"
        msg += "- Existing server admins using `/setadmin`"
    return msg
