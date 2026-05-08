"""
Discord Bridge Bot
------------------
Prefix-command bot for administering a Discord guild from chat.

Run:
    python bot.py

All commands use COMMAND_PREFIX from .env, defaulting to "!". Only users listed
in AUTHORIZED_USER_IDS can run commands. If that list is empty, only the guild
owner is allowed.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Iterable

import discord
from discord.ext import commands
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")

_raw_authed = os.getenv("AUTHORIZED_USER_IDS", "").strip()
AUTHORIZED_USER_IDS = {
    int(item) for item in _raw_authed.split(",") if item.strip().isdigit()
}

if not TOKEN:
    raise SystemExit(
        "DISCORD_TOKEN is missing. Copy .env.example to .env and fill it in."
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("bridge")

# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(
    command_prefix=COMMAND_PREFIX,
    intents=intents,
    help_command=commands.DefaultHelpCommand(no_category="Commands"),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def is_authorized():
    """Allow only listed user IDs, or the guild owner when no list is set."""

    async def predicate(ctx: commands.Context) -> bool:
        if ctx.guild is None:
            return False
        if AUTHORIZED_USER_IDS:
            return ctx.author.id in AUTHORIZED_USER_IDS
        return ctx.author.id == ctx.guild.owner_id

    return commands.check(predicate)


def _normalize(value: str) -> str:
    return value.strip().lower()


def _clean_mention(value: str) -> str:
    return re.sub(r"[<@#!&>]", "", value.strip())


def _by_id_or_name(items: Iterable, value: str):
    cleaned = _clean_mention(value)
    if cleaned.isdigit():
        item_id = int(cleaned)
        for item in items:
            if getattr(item, "id", None) == item_id:
                return item

    wanted = _normalize(value)
    for item in items:
        if _normalize(getattr(item, "name", "")) == wanted:
            return item
    for item in items:
        if wanted in _normalize(getattr(item, "name", "")):
            return item
    return None


def find_channel(guild: discord.Guild, value: str):
    return _by_id_or_name(guild.channels, value)


def find_category(guild: discord.Guild, value: str | None):
    if not value:
        return None
    return _by_id_or_name(guild.categories, value)


def find_role(guild: discord.Guild, value: str):
    return _by_id_or_name(guild.roles, value)


def parse_color(value: str) -> discord.Color:
    cleaned = value.strip().removeprefix("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", cleaned):
        raise commands.BadArgument("Color must be a hex value like #5865F2.")
    return discord.Color(int(cleaned, 16))


def format_bool(value: bool) -> str:
    return "yes" if value else "no"


async def send_long(ctx: commands.Context, text: str):
    """Send text in Discord-sized chunks."""
    if not text:
        await ctx.send("No data.")
        return

    chunks: list[str] = []
    current = ""
    for line in text.splitlines():
        if len(current) + len(line) + 1 > 1900:
            chunks.append(current)
            current = ""
        current += line + "\n"
    if current:
        chunks.append(current)

    for chunk in chunks:
        await ctx.send(chunk)


async def require_guild(ctx: commands.Context) -> discord.Guild:
    if ctx.guild is None:
        raise commands.NoPrivateMessage("This command only works in a server.")
    return ctx.guild


def permissions_text(perms: discord.Permissions) -> str:
    enabled = [name for name, enabled in perms if enabled]
    return ", ".join(enabled) if enabled else "none"


async def get_current_members(guild: discord.Guild) -> list[discord.Member]:
    """Prefer a fresh member fetch; fall back to cache if Discord denies it."""
    try:
        return [member async for member in guild.fetch_members(limit=None)]
    except (discord.Forbidden, discord.HTTPException) as exc:
        log.warning("Could not fetch all members for %s: %s", guild.id, exc)
        return list(guild.members)


def count_members_by_role(members: Iterable[discord.Member]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for member in members:
        for role in member.roles:
            counts[role.id] = counts.get(role.id, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
@bot.event
async def on_ready():
    log.info("Logged in as %s (id=%s)", bot.user, bot.user.id)
    log.info("Connected to %d guild(s)", len(bot.guilds))


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    original = getattr(error, "original", error)

    if isinstance(error, commands.CheckFailure):
        await ctx.send("Not authorized to run this command.")
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send(str(error))
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"Missing argument: `{error.param.name}`. Try "
            f"`{COMMAND_PREFIX}help {ctx.command}`."
        )
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"Bad argument: {error}")
    elif isinstance(original, discord.Forbidden):
        await ctx.send("Discord denied that action. Check the bot role permissions.")
    else:
        log.exception("Command error", exc_info=original)
        await ctx.send(f"Error: `{original}`")


# ---------------------------------------------------------------------------
# Diagnostics and inventory
# ---------------------------------------------------------------------------
@bot.command(name="ping")
@is_authorized()
async def ping(ctx: commands.Context):
    """Check that the bot is online."""
    await ctx.send(f"Pong. Latency: {round(bot.latency * 1000)} ms")


@bot.command(name="server-info", aliases=["guild-info"])
@is_authorized()
async def server_info(ctx: commands.Context):
    """Show server counts and basic metadata."""
    guild = await require_guild(ctx)
    owner = guild.get_member(guild.owner_id)
    if owner is None:
        try:
            owner = await guild.fetch_member(guild.owner_id)
        except (discord.Forbidden, discord.HTTPException):
            owner = None
    lines = [
        f"Server: {guild.name} ({guild.id})",
        f"Owner: {owner or 'unknown'} ({guild.owner_id})",
        f"Members: {guild.member_count}",
        f"Channels: {len(guild.channels)}",
        f"Categories: {len(guild.categories)}",
        f"Roles: {len(guild.roles)}",
        f"Created: {guild.created_at:%Y-%m-%d %H:%M UTC}",
    ]
    await send_long(ctx, "\n".join(lines))


@bot.command(name="bot-permissions", aliases=["bot-perms"])
@is_authorized()
async def bot_permissions(ctx: commands.Context):
    """Show important permissions the bot has or lacks in this channel."""
    guild = await require_guild(ctx)
    me = guild.me or guild.get_member(bot.user.id)
    if me is None:
        await ctx.send("Could not resolve the bot member in this server.")
        return

    required = [
        "view_channel",
        "send_messages",
        "embed_links",
        "read_message_history",
        "manage_channels",
        "manage_roles",
        "manage_messages",
        "kick_members",
        "ban_members",
        "moderate_members",
    ]
    channel_perms = ctx.channel.permissions_for(me)
    missing = [name for name in required if not getattr(channel_perms, name)]
    lines = [
        f"Bot role top position: {me.top_role.name} ({me.top_role.position})",
        f"Missing important permissions here: {', '.join(missing) if missing else 'none'}",
        f"All enabled permissions here: {permissions_text(channel_perms)}",
    ]
    await send_long(ctx, "\n".join(lines))


@bot.command(name="list-channels", aliases=["channels", "ls"])
@is_authorized()
async def list_channels(ctx: commands.Context):
    """List channels grouped by category, including IDs."""
    guild = await require_guild(ctx)
    lines: list[str] = []

    for category in guild.categories:
        lines.append(f"[category] {category.name} ({category.id})")
        for channel in category.channels:
            lines.append(f"  [{channel.type}] {channel.name} ({channel.id})")

    uncategorized = [
        channel
        for channel in guild.channels
        if channel.category is None and not isinstance(channel, discord.CategoryChannel)
    ]
    if uncategorized:
        lines.append("[no category]")
        for channel in uncategorized:
            lines.append(f"  [{channel.type}] {channel.name} ({channel.id})")

    await send_long(ctx, "\n".join(lines) or "No channels found.")


@bot.command(name="channel-info")
@is_authorized()
async def channel_info(ctx: commands.Context, *, channel_ref: str):
    """Show details for a channel. Usage: !channel-info #general"""
    guild = await require_guild(ctx)
    channel = find_channel(guild, channel_ref)
    if channel is None:
        raise commands.BadArgument("Channel not found.")

    lines = [
        f"Name: {channel.name}",
        f"ID: {channel.id}",
        f"Type: {channel.type}",
        f"Category: {channel.category.name if channel.category else 'none'}",
        f"Position: {channel.position}",
        f"Created: {channel.created_at:%Y-%m-%d %H:%M UTC}",
    ]
    if isinstance(channel, discord.TextChannel):
        lines.extend(
            [
                f"Topic: {channel.topic or 'none'}",
                f"Slowmode: {channel.slowmode_delay}s",
                f"NSFW: {format_bool(channel.is_nsfw())}",
            ]
        )
    await send_long(ctx, "\n".join(lines))


@bot.command(name="list-roles", aliases=["roles"])
@is_authorized()
async def list_roles(ctx: commands.Context):
    """List roles from highest to lowest, including IDs."""
    guild = await require_guild(ctx)
    members = await get_current_members(guild)
    role_counts = count_members_by_role(members)
    roles = sorted(guild.roles, key=lambda role: role.position, reverse=True)
    lines = [
        (
            f"{role.position:>2} | {role.name} ({role.id}) | "
            f"members={role_counts.get(role.id, 0)} | color={role.color}"
        )
        for role in roles
    ]
    await send_long(ctx, "\n".join(lines))


@bot.command(name="role-info")
@is_authorized()
async def role_info(ctx: commands.Context, *, role_ref: str):
    """Show details for a role. Usage: !role-info Moderator"""
    guild = await require_guild(ctx)
    role = find_role(guild, role_ref)
    if role is None:
        raise commands.BadArgument("Role not found.")

    members = await get_current_members(guild)
    member_count = sum(1 for member in members if role in member.roles)
    lines = [
        f"Name: {role.name}",
        f"ID: {role.id}",
        f"Position: {role.position}",
        f"Members: {member_count}",
        f"Color: {role.color}",
        f"Mentionable: {format_bool(role.mentionable)}",
        f"Hoisted: {format_bool(role.hoist)}",
        f"Managed: {format_bool(role.managed)}",
        f"Permissions: {permissions_text(role.permissions)}",
    ]
    await send_long(ctx, "\n".join(lines))


@bot.command(name="list-members", aliases=["members"])
@is_authorized()
async def list_members(ctx: commands.Context, limit: int = 50, *, query: str = ""):
    """List members. Usage: !list-members [limit] [optional search text]"""
    guild = await require_guild(ctx)
    limit = max(1, min(limit, 200))
    query_lower = _normalize(query)

    members = await get_current_members(guild)
    if query_lower:
        members = [
            member
            for member in members
            if query_lower in _normalize(member.name)
            or query_lower in _normalize(member.display_name)
        ]

    lines = [
        (
            f"{member.display_name} ({member.id}) | user={member.name} | "
            f"bot={format_bool(member.bot)} | top_role={member.top_role.name}"
        )
        for member in members[:limit]
    ]
    total_note = f"Showing {len(lines)} of {len(members)} matching member(s)."
    await send_long(ctx, total_note + "\n" + "\n".join(lines))


@bot.command(name="member-info", aliases=["user-info"])
@is_authorized()
async def member_info(ctx: commands.Context, member: discord.Member):
    """Show details for a member. Usage: !member-info @user"""
    roles = [role.name for role in member.roles if role.name != "@everyone"]
    lines = [
        f"Display name: {member.display_name}",
        f"Username: {member.name}",
        f"ID: {member.id}",
        f"Bot: {format_bool(member.bot)}",
        f"Joined: {member.joined_at:%Y-%m-%d %H:%M UTC}" if member.joined_at else "Joined: unknown",
        f"Created: {member.created_at:%Y-%m-%d %H:%M UTC}",
        f"Top role: {member.top_role.name}",
        f"Roles: {', '.join(roles) if roles else 'none'}",
    ]
    await send_long(ctx, "\n".join(lines))


@bot.command(name="server-snapshot", aliases=["snapshot"])
@is_authorized()
async def server_snapshot(ctx: commands.Context):
    """Show a compact snapshot of channels, roles, and member counts."""
    guild = await require_guild(ctx)
    members = await get_current_members(guild)
    role_counts = count_members_by_role(members)
    bots = sum(1 for member in members if member.bot)
    humans = len(members) - bots
    lines = [
        f"Server: {guild.name} ({guild.id})",
        f"Members: {guild.member_count} total, {humans} humans, {bots} bots",
        "",
        "Channels:",
    ]
    lines.extend(f"- {channel.name} ({channel.type}, {channel.id})" for channel in guild.channels)
    lines.extend(["", "Roles:"])
    roles = sorted(guild.roles, key=lambda role: role.position, reverse=True)
    lines.extend(f"- {role.name} ({role.id}) members={role_counts.get(role.id, 0)}" for role in roles)
    await send_long(ctx, "\n".join(lines))


# ---------------------------------------------------------------------------
# Channel and category management
# ---------------------------------------------------------------------------
@bot.command(name="create-channel", aliases=["cc"])
@is_authorized()
async def create_channel(ctx: commands.Context, name: str, *, category: str = None):
    """Create a text channel. Usage: !create-channel name [category]"""
    guild = await require_guild(ctx)
    cat = find_category(guild, category)
    if category and cat is None:
        raise commands.BadArgument("Category not found.")
    channel = await guild.create_text_channel(name, category=cat)
    await ctx.send(f"Created text channel {channel.mention} ({channel.id})")


@bot.command(name="create-voice", aliases=["cv"])
@is_authorized()
async def create_voice(ctx: commands.Context, name: str, *, category: str = None):
    """Create a voice channel. Usage: !create-voice name [category]"""
    guild = await require_guild(ctx)
    cat = find_category(guild, category)
    if category and cat is None:
        raise commands.BadArgument("Category not found.")
    channel = await guild.create_voice_channel(name, category=cat)
    await ctx.send(f"Created voice channel {channel.name} ({channel.id})")


@bot.command(name="create-category", aliases=["ccat"])
@is_authorized()
async def create_category(ctx: commands.Context, *, name: str):
    """Create a category. Usage: !create-category Project X"""
    guild = await require_guild(ctx)
    category = await guild.create_category(name)
    await ctx.send(f"Created category {category.name} ({category.id})")


@bot.command(name="rename-channel")
@is_authorized()
async def rename_channel(ctx: commands.Context, channel_ref: str, *, new_name: str):
    """Rename any guild channel. Usage: !rename-channel #old new-name"""
    guild = await require_guild(ctx)
    channel = find_channel(guild, channel_ref)
    if channel is None:
        raise commands.BadArgument("Channel not found.")
    old = channel.name
    await channel.edit(name=new_name, reason=f"Renamed via bridge by {ctx.author}")
    await ctx.send(f"Renamed {old} -> {new_name}")


@bot.command(name="delete-channel")
@is_authorized()
async def delete_channel(ctx: commands.Context, *, channel_ref: str):
    """Delete any guild channel. Usage: !delete-channel #channel"""
    guild = await require_guild(ctx)
    channel = find_channel(guild, channel_ref)
    if channel is None:
        raise commands.BadArgument("Channel not found.")
    name = channel.name
    await channel.delete(reason=f"Deleted via bridge by {ctx.author}")
    await ctx.send(f"Deleted channel {name}")


@bot.command(name="move-channel")
@is_authorized()
async def move_channel(ctx: commands.Context, channel_ref: str, *, category_ref: str):
    """Move a channel to a category, or none. Usage: !move-channel #chat Category"""
    guild = await require_guild(ctx)
    channel = find_channel(guild, channel_ref)
    if channel is None or isinstance(channel, discord.CategoryChannel):
        raise commands.BadArgument("Non-category channel not found.")

    category = None if _normalize(category_ref) in {"none", "null", "uncategorized"} else find_category(guild, category_ref)
    if category_ref and category is None and _normalize(category_ref) not in {"none", "null", "uncategorized"}:
        raise commands.BadArgument("Category not found.")

    await channel.edit(category=category, reason=f"Moved via bridge by {ctx.author}")
    await ctx.send(f"Moved {channel.name} to {category.name if category else 'no category'}")


@bot.command(name="set-topic")
@is_authorized()
async def set_topic(ctx: commands.Context, channel: discord.TextChannel, *, topic: str = ""):
    """Set a text channel topic. Usage: !set-topic #channel topic text"""
    await channel.edit(topic=topic or None, reason=f"Topic changed via bridge by {ctx.author}")
    await ctx.send(f"Updated topic for {channel.mention}")


@bot.command(name="set-slowmode")
@is_authorized()
async def set_slowmode(ctx: commands.Context, channel: discord.TextChannel, seconds: int):
    """Set text channel slowmode, 0-21600 seconds."""
    if seconds < 0 or seconds > 21600:
        raise commands.BadArgument("Slowmode must be between 0 and 21600 seconds.")
    await channel.edit(slowmode_delay=seconds, reason=f"Slowmode changed via bridge by {ctx.author}")
    await ctx.send(f"Set slowmode for {channel.mention} to {seconds}s")


@bot.command(name="lock-channel")
@is_authorized()
async def lock_channel(ctx: commands.Context, channel: discord.TextChannel, *, role_ref: str = "@everyone"):
    """Disable Send Messages for a role in a text channel."""
    guild = await require_guild(ctx)
    role = guild.default_role if role_ref == "@everyone" else find_role(guild, role_ref)
    if role is None:
        raise commands.BadArgument("Role not found.")
    await channel.set_permissions(role, send_messages=False, reason=f"Locked via bridge by {ctx.author}")
    await ctx.send(f"Locked {channel.mention} for {role.name}")


@bot.command(name="unlock-channel")
@is_authorized()
async def unlock_channel(ctx: commands.Context, channel: discord.TextChannel, *, role_ref: str = "@everyone"):
    """Reset Send Messages overwrite for a role in a text channel."""
    guild = await require_guild(ctx)
    role = guild.default_role if role_ref == "@everyone" else find_role(guild, role_ref)
    if role is None:
        raise commands.BadArgument("Role not found.")
    await channel.set_permissions(role, send_messages=None, reason=f"Unlocked via bridge by {ctx.author}")
    await ctx.send(f"Unlocked {channel.mention} for {role.name}")


# ---------------------------------------------------------------------------
# Messaging and moderation
# ---------------------------------------------------------------------------
@bot.command(name="say")
@is_authorized()
async def say(ctx: commands.Context, channel: discord.TextChannel, *, message: str):
    """Send a message to a channel. Usage: !say #general Hello"""
    await channel.send(message)
    await ctx.send(f"Sent to {channel.mention}")


@bot.command(name="dm")
@is_authorized()
async def dm(ctx: commands.Context, member: discord.Member, *, message: str):
    """DM a server member. Usage: !dm @user message"""
    try:
        await member.send(message)
        await ctx.send(f"DM sent to {member.display_name}")
    except discord.Forbidden:
        await ctx.send("Cannot DM that user.")


@bot.command(name="link")
@is_authorized()
async def link(ctx: commands.Context, channel: discord.TextChannel, url: str, *, description: str = ""):
    """Post a link embed. Usage: !link #channel https://example.com caption"""
    embed = discord.Embed(url=url, title=url, description=description or None)
    await channel.send(embed=embed)
    await ctx.send(f"Posted link to {channel.mention}")


@bot.command(name="announce")
@is_authorized()
async def announce(ctx: commands.Context, channel: discord.TextChannel, *, message: str):
    """Post an embed announcement. Usage: !announce #news message"""
    embed = discord.Embed(title="Announcement", description=message, color=0x5865F2)
    embed.set_footer(text=f"From {ctx.author.display_name}")
    await channel.send(embed=embed)
    await ctx.send(f"Announced in {channel.mention}")


@bot.command(name="purge", aliases=["clear"])
@is_authorized()
async def purge(ctx: commands.Context, limit: int):
    """Delete recent messages from the current channel. Usage: !purge 25"""
    if limit < 1 or limit > 100:
        raise commands.BadArgument("Limit must be between 1 and 100.")
    deleted = await ctx.channel.purge(limit=limit + 1)
    await ctx.send(f"Deleted {max(0, len(deleted) - 1)} message(s).", delete_after=5)


@bot.command(name="pin")
@is_authorized()
async def pin_message(ctx: commands.Context, message_id: int):
    """Pin a message in the current channel by ID."""
    message = await ctx.channel.fetch_message(message_id)
    await message.pin(reason=f"Pinned via bridge by {ctx.author}")
    await ctx.send(f"Pinned message {message_id}")


@bot.command(name="unpin")
@is_authorized()
async def unpin_message(ctx: commands.Context, message_id: int):
    """Unpin a message in the current channel by ID."""
    message = await ctx.channel.fetch_message(message_id)
    await message.unpin(reason=f"Unpinned via bridge by {ctx.author}")
    await ctx.send(f"Unpinned message {message_id}")


# ---------------------------------------------------------------------------
# Role management
# ---------------------------------------------------------------------------
@bot.command(name="create-role")
@is_authorized()
async def create_role(ctx: commands.Context, *, name: str):
    """Create a role. Usage: !create-role Moderator"""
    guild = await require_guild(ctx)
    role = await guild.create_role(name=name, reason=f"Created via bridge by {ctx.author}")
    await ctx.send(f"Created role {role.name} ({role.id})")


@bot.command(name="rename-role")
@is_authorized()
async def rename_role(ctx: commands.Context, role: discord.Role, *, new_name: str):
    """Rename a role. Usage: !rename-role RoleName New Name"""
    old = role.name
    await role.edit(name=new_name, reason=f"Renamed via bridge by {ctx.author}")
    await ctx.send(f"Renamed role {old} -> {new_name}")


@bot.command(name="delete-role")
@is_authorized()
async def delete_role(ctx: commands.Context, *, role: discord.Role):
    """Delete a role. Usage: !delete-role RoleName"""
    name = role.name
    await role.delete(reason=f"Deleted via bridge by {ctx.author}")
    await ctx.send(f"Deleted role {name}")


@bot.command(name="give-role")
@is_authorized()
async def give_role(ctx: commands.Context, member: discord.Member, *, role: discord.Role):
    """Assign a role to a member. Usage: !give-role @user RoleName"""
    await member.add_roles(role, reason=f"Role assigned via bridge by {ctx.author}")
    await ctx.send(f"Gave {role.name} to {member.display_name}")


@bot.command(name="remove-role")
@is_authorized()
async def remove_role(ctx: commands.Context, member: discord.Member, *, role: discord.Role):
    """Remove a role from a member. Usage: !remove-role @user RoleName"""
    await member.remove_roles(role, reason=f"Role removed via bridge by {ctx.author}")
    await ctx.send(f"Removed {role.name} from {member.display_name}")


@bot.command(name="set-role-color")
@is_authorized()
async def set_role_color(ctx: commands.Context, role: discord.Role, color_hex: str):
    """Set a role color. Usage: !set-role-color RoleName #5865F2"""
    color = parse_color(color_hex)
    await role.edit(color=color, reason=f"Color changed via bridge by {ctx.author}")
    await ctx.send(f"Set {role.name} color to #{color.value:06X}")


@bot.command(name="set-role-mentionable")
@is_authorized()
async def set_role_mentionable(ctx: commands.Context, role: discord.Role, value: bool):
    """Set whether a role is mentionable. Usage: !set-role-mentionable RoleName true"""
    await role.edit(mentionable=value, reason=f"Mentionable changed via bridge by {ctx.author}")
    await ctx.send(f"Set {role.name} mentionable to {value}")


# ---------------------------------------------------------------------------
# Member management
# ---------------------------------------------------------------------------
@bot.command(name="set-nick")
@is_authorized()
async def set_nick(ctx: commands.Context, member: discord.Member, *, nickname: str = ""):
    """Set or clear a member nickname. Usage: !set-nick @user New Nick"""
    await member.edit(nick=nickname or None, reason=f"Nickname changed via bridge by {ctx.author}")
    await ctx.send(f"Updated nickname for {member.display_name}")


@bot.command(name="timeout")
@is_authorized()
async def timeout_member(ctx: commands.Context, member: discord.Member, minutes: int, *, reason: str = "No reason provided"):
    """Timeout a member. Usage: !timeout @user 10 reason"""
    if minutes < 1 or minutes > 40320:
        raise commands.BadArgument("Minutes must be between 1 and 40320.")
    until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    await member.timeout(until, reason=f"{reason} (via bridge by {ctx.author})")
    await ctx.send(f"Timed out {member.display_name} until {until:%Y-%m-%d %H:%M UTC}")


@bot.command(name="untimeout")
@is_authorized()
async def untimeout_member(ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
    """Remove a member timeout. Usage: !untimeout @user reason"""
    await member.timeout(None, reason=f"{reason} (via bridge by {ctx.author})")
    await ctx.send(f"Removed timeout from {member.display_name}")


@bot.command(name="kick")
@is_authorized()
async def kick_member(ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
    """Kick a member. Usage: !kick @user reason"""
    await member.kick(reason=f"{reason} (via bridge by {ctx.author})")
    await ctx.send(f"Kicked {member.display_name}")


@bot.command(name="ban")
@is_authorized()
async def ban_member(ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
    """Ban a member. Usage: !ban @user reason"""
    await member.ban(reason=f"{reason} (via bridge by {ctx.author})")
    await ctx.send(f"Banned {member.display_name}")


@bot.command(name="unban")
@is_authorized()
async def unban_user(ctx: commands.Context, user_id: int, *, reason: str = "No reason provided"):
    """Unban a user by ID. Usage: !unban 123456789 reason"""
    guild = await require_guild(ctx)
    user = discord.Object(id=user_id)
    await guild.unban(user, reason=f"{reason} (via bridge by {ctx.author})")
    await ctx.send(f"Unbanned user ID {user_id}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except discord.PrivilegedIntentsRequired:
        raise SystemExit(
            "Discord rejected the requested privileged intents. Enable "
            "Message Content Intent and Server Members Intent in the Discord "
            "Developer Portal for this bot, then run python bot.py again."
        )
