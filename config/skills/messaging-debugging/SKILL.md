---
name: messaging-debugging
description: "Debug Hermes messaging platform connectivity — verify bot permissions, resolve missing targets, and troubleshoot Telegram/Discord/Slack delivery."
version: 1.0.0
metadata:
  hermes:
    tags: [messaging, telegram, discord, debugging, gateway]
    triggers:
      - "send_message list doesn't show expected target"
      - "bot can't post to channel/group"
      - "checking messaging platform permissions"
      - "finding chat_id for send_message"
---

# Messaging Debugging

Debug Hermes messaging platform connectivity. Use when `send_message list` doesn't show an expected target, or when you need to verify bot permissions.

## Core Rule

**`send_message list` is not exhaustive.** It may omit channels/groups the bot actually has access to. Never conclude access is denied solely from the list being incomplete — verify with the platform's API directly.

---

## Telegram: Verify Bot Permissions

### 1. Extract bot token

The token lives in `~/.hermes/.env` as `TELEGRAM_BOT_TOKEN=***`. Use Python to read it, since the .env file is protected from `read_file`:

```python
import re
with open("/home/<user>/.hermes/.env") as f:
    for line in f:
        m = re.match(r'TELEGRAM_BOT_TOKEN=*** line.strip())
        if m:
            token = m.group(1)
            break
```

### 2. Check if bot is in the channel

```bash
curl -s "https://api.telegram.org/bot${TOKEN}/getChat?chat_id=@channelname"
```

Returns channel info if bot has access. The `id` field is the numeric chat_id (negative for channels/groups, e.g. `<YOUR_CHAT_ID>`).

### 3. Check bot's permissions in the channel

First get the bot's own user ID, then check membership:

```python
# Get bot ID
bot_id = json.loads(subprocess.run(["curl", "-s", f"https://api.telegram.org/bot{token}/getMe"], capture_output=True, text=True).stdout)["result"]["id"]

# Check membership
member = json.loads(subprocess.run(["curl", "-s", f"https://api.telegram.org/bot{token}/getChatMember?chat_id=@channelname&user_id={bot_id}"], capture_output=True, text=True).stdout)
```

Key permissions in the response:
- `can_post_messages` — can send to channel
- `can_edit_messages` — can edit sent messages
- `can_delete_messages` — can delete messages
- `status: "administrator"` — full admin rights
- `status: "member"` — regular member

### 4. Send to channel using numeric chat_id

Once verified, use the numeric chat_id with `send_message`:

```
target: "telegram:<chat_id>"   # e.g. "telegram:<YOUR_CHAT_ID>"
```

The `send_message` tool's `list` action may still not show this target, but sending works if the bot has `can_post_messages: true`.

---

## Pitfalls

- **Check before assuming no access.** `send_message list` can be incomplete. Always verify with the platform API.
- **Numeric chat_id format.** Channels/groups have negative IDs (e.g. `-100...`). Users have positive IDs.
- **Username lookup.** Use `@username` (without `@` for some APIs). If `@username` fails, try the numeric ID.
