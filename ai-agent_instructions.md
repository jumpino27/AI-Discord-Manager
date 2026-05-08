# AI Agent Instructions for the Discord Bridge Bot

This repository contains a Python Discord bridge bot in `bot.py`. It is meant
to let an authorized AI agent or server owner inspect and manage a Discord
server through chat commands.

## Purpose

Use this bot to administer a Discord server from Discord itself:

- Read current server state: channels, roles, members, permissions, snapshots.
- Create, rename, move, lock, unlock, and delete channels.
- Create and manage roles.
- Send messages, announcements, links, DMs, pins, and cleanup actions.
- Run basic moderation commands such as timeout, kick, ban, and unban.

If a needed command is missing or broken, you may freely edit and enhance
`bot.py` to add the capability, then verify it before using it on the server.

## Required Setup

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Create `.env` from `.env.example`:

```powershell
copy .env.example .env
```

Required `.env` values:

```env
DISCORD_TOKEN=your-bot-token
AUTHORIZED_USER_IDS=123456789012345678
COMMAND_PREFIX=!
```

If `AUTHORIZED_USER_IDS` is empty, only the Discord server owner can run bot
commands.

## Discord Developer Portal Requirements

In the bot application settings, enable these privileged gateway intents:

- Message Content Intent
- Server Members Intent

The bot needs Message Content Intent to read prefix commands such as `!help`.
It needs Server Members Intent for reliable member and role membership reads.

Recommended bot permissions:

- View Channels
- Send Messages
- Embed Links
- Read Message History
- Add Reactions
- Manage Channels
- Manage Roles
- Manage Messages
- Manage Server, if renaming or editing server metadata
- Moderate Members
- Kick Members
- Ban Members

Discord role hierarchy still applies. The bot cannot manage roles or members
that are at or above the bot's highest role.

## Running the Bot

Start the command bot:

```powershell
python bot.py
```

If startup fails with privileged intent errors, enable the intents above in the
Discord Developer Portal and restart the bot.

## Useful Commands

Use the configured command prefix, usually `!`.

Diagnostics and reads:

- `!help`
- `!ping`
- `!server-info`
- `!bot-permissions`
- `!list-channels`
- `!channel-info #channel`
- `!list-roles`
- `!role-info RoleName`
- `!list-members [limit] [search]`
- `!member-info @user`
- `!server-snapshot`

Channel management:

- `!create-channel name [category]`
- `!create-voice name [category]`
- `!create-category name`
- `!rename-channel #channel new-name`
- `!delete-channel #channel`
- `!move-channel #channel CategoryName`
- `!move-channel #channel none`
- `!set-topic #channel topic`
- `!set-slowmode #channel seconds`
- `!lock-channel #channel [role]`
- `!unlock-channel #channel [role]`

Messaging:

- `!say #channel message`
- `!dm @user message`
- `!link #channel https://example.com description`
- `!announce #channel message`
- `!purge 25`
- `!pin message_id`
- `!unpin message_id`

Role management:

- `!create-role RoleName`
- `!rename-role RoleName New Name`
- `!delete-role RoleName`
- `!give-role @user RoleName`
- `!remove-role @user RoleName`
- `!set-role-color RoleName #5865F2`
- `!set-role-mentionable RoleName true`

Member management:

- `!set-nick @user New Nick`
- `!timeout @user 10 reason`
- `!untimeout @user reason`
- `!kick @user reason`
- `!ban @user reason`
- `!unban user_id reason`

## Safe Operating Rules for Agents

Before making destructive changes:

1. Run `!server-snapshot` or inspect the guild with a script.
2. Confirm the target server if the bot is in more than one guild.
3. Prefer creating or updating the minimum required channels/roles.
4. Avoid deleting channels unless the user explicitly asks for a reset.
5. Do not expose `.env` or the Discord bot token.
6. Keep public-facing messages future-proof. Do not mention fixed repository
   counts or claims that will become stale.

For permission work:

- Read the current roles first.
- Grant private channel access to actual admin/staff roles, not only the bot.
- Deny `@everyone` explicitly for hidden admin-only channels.
- Verify final permissions with `channel.permissions_for(guild.default_role)`.

## One-Shot Maintenance Scripts

If the full prefix bot cannot run because privileged intents are disabled, an
agent can still use short one-shot scripts with non-privileged intents for many
management tasks, such as creating channels or editing server metadata.

Use this pattern:

```python
import os
import discord
from dotenv import load_dotenv

load_dotenv(".env")
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = False
intents.members = False

class Client(discord.Client):
    async def on_ready(self):
        try:
            guild = self.guilds[0]
            # Make focused server changes here.
        finally:
            await self.close()

Client(intents=intents).run(TOKEN)
```

Always verify after running a one-shot script.

## Enhancing `bot.py`

If something is missing or not working, edit `bot.py` directly. Follow the
existing style:

- Use `@bot.command(...)`.
- Add `@is_authorized()` to every command that changes or reads server state.
- Use `require_guild(ctx)` for server-only commands.
- Use Discord's typed converters when practical, such as `discord.Member`,
  `discord.Role`, and `discord.TextChannel`.
- Catch or surface permission failures clearly.
- Keep responses concise.
- Avoid hard-coded server IDs unless the user explicitly wants one server only.

After edits, verify:

```powershell
python -m py_compile bot.py
python -c "import bot; print(len(list(bot.bot.commands)))"
```

Then run the bot:

```powershell
python bot.py
```

## Current Server Layout Notes

The server was organized for Jumpino open-source projects:

- `#rules`: read-only, reactions disabled.
- `#announcements`: read-only, reactions enabled.
- `#links`: read-only, reactions enabled.
- `#donation-link`: read-only, reactions enabled.
- `#general`: public discussion.
- `#bug-report`: public bug reports with 300-second slowmode.
- Public voice channels for general talk, project help, and focus work.
- Admin-only text and voice channels hidden from `@everyone`.

These notes describe the current intended structure, but agents should inspect
the live server before changing anything.
