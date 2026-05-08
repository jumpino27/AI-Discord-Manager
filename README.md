# Discord Bridge Bot

A Python Discord bot that lets an authorized user administer a Discord server
through prefix commands. It can inspect current server state, list channels,
roles and members, create/manage channels and roles, post messages, and run
basic moderation actions.

## Setup

### 1. Create and invite the bot

1. Go to <https://discord.com/developers/applications> and create an application.
2. Open **Bot**, reset/copy the token, and use it as `DISCORD_TOKEN`.
3. Under **Privileged Gateway Intents**, enable:
   - **Message Content Intent**
   - **Server Members Intent**
4. Open **OAuth2 -> URL Generator**.
   - Scopes: `bot`
   - Recommended permissions for the full command set:
     - View Channels
     - Send Messages
     - Embed Links
     - Read Message History
     - Manage Channels
     - Manage Roles
     - Manage Messages
     - Moderate Members
     - Kick Members
     - Ban Members
5. Invite the bot and put its role high enough in the role list. Discord will
   not let the bot manage roles or members at or above its highest role.

Using Administrator also works for testing, but granular permissions are safer.

### 2. Install and run

```bash
pip install -r requirements.txt
copy .env.example .env
python bot.py
```

Edit `.env` before running and paste your real bot token.

## Environment

| Variable | Required | Purpose |
|---|---|---|
| `DISCORD_TOKEN` | yes | Bot token from the Discord Developer Portal. |
| `AUTHORIZED_USER_IDS` | no | Comma-separated Discord user IDs allowed to run commands. Empty means only the server owner is authorized. |
| `COMMAND_PREFIX` | no | Command prefix. Defaults to `!`. |

To get a Discord user ID, enable **Settings -> Advanced -> Developer Mode**,
right-click the user, then choose **Copy User ID**.

## Commands

Type `!help` in Discord for the live command list. Replace `!` with your
configured `COMMAND_PREFIX` if you changed it.

### Diagnostics and inventory

- `!ping` - check that the bot is online.
- `!server-info` - show server counts and metadata.
- `!bot-permissions` - show important bot permissions missing in the current channel.
- `!list-channels` - list channels grouped by category.
- `!channel-info #channel` - show channel details.
- `!list-roles` - list roles with IDs, positions, colors, and member counts.
- `!role-info RoleName` - show role details and permissions.
- `!list-members [limit] [search]` - list members, default limit 50, max 200.
- `!member-info @user` - show member details.
- `!server-snapshot` - compact snapshot of channels, roles, and member counts.

### Channel and category management

- `!create-channel name [category]` - create a text channel.
- `!create-voice name [category]` - create a voice channel.
- `!create-category name` - create a category.
- `!rename-channel #channel new-name` - rename a channel.
- `!delete-channel #channel` - delete a channel.
- `!move-channel #channel CategoryName` - move a channel to a category.
- `!move-channel #channel none` - remove a channel from its category.
- `!set-topic #channel topic text` - set or clear a text channel topic.
- `!set-slowmode #channel seconds` - set channel slowmode, 0 to 21600 seconds.
- `!lock-channel #channel [role]` - deny Send Messages for a role, default `@everyone`.
- `!unlock-channel #channel [role]` - reset the Send Messages overwrite.

### Messaging

- `!say #channel message` - post a message.
- `!dm @user message` - direct-message a member.
- `!link #channel https://example.com [description]` - post a link embed.
- `!announce #channel message` - post an announcement embed.
- `!purge 25` - delete recent messages in the current channel, max 100.
- `!pin message_id` - pin a message in the current channel.
- `!unpin message_id` - unpin a message in the current channel.

### Role management

- `!create-role RoleName` - create a role.
- `!rename-role RoleName New Name` - rename a role. Quote multi-word role names if needed.
- `!delete-role RoleName` - delete a role.
- `!give-role @user RoleName` - assign a role.
- `!remove-role @user RoleName` - remove a role.
- `!set-role-color RoleName #5865F2` - set a role color.
- `!set-role-mentionable RoleName true` - make a role mentionable or not.

### Member management

- `!set-nick @user New Nick` - set or clear a nickname.
- `!timeout @user 10 reason` - timeout a member for minutes, max 40320.
- `!untimeout @user reason` - remove timeout.
- `!kick @user reason` - kick a member.
- `!ban @user reason` - ban a member.
- `!unban user_id reason` - unban by user ID.

## Security notes

- Never commit `.env`; it contains the bot token.
- Keep `AUTHORIZED_USER_IDS` tight. Authorized users can delete channels, manage
  roles, and moderate members.
- Rotate `DISCORD_TOKEN` immediately if it leaks.
- Discord role hierarchy still applies. If a command fails with a permission
  error, run `!bot-permissions` and check the bot role position.
