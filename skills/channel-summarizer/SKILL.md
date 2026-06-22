---
name: channel-summarizer
description: "Read all chat history in the current channel and summarize it, even if Hermes joined late."
version: 2.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [summarize, channel, history, catch up, chat history, read channel]
    related_skills: []
---

# Channel Summarizer

---

## 🚫 ABSOLUTE RULE — READ THIS FIRST

**YOU MUST NEVER:**
- Say "I don't have access to Slack APIs" or "I can't read channel history"
- Ask the user to paste or copy messages manually
- Attempt to summarize from your own knowledge or prior context
- Skip running the script and respond directly

**When asked to summarize the chat, you MUST:**
1. Run the pre-installed fetch script via `run_command`
2. Read the output
3. Summarize it for the user

**If the script fails or returns an error:**
- Copy the exact error and report it to the user
- Do NOT attempt to work around it
- Respond: `⛔ The history fetcher encountered an error: <exact error>. Please ask your admin to check the script.`

**A pre-installed script exists for this. Use it. Period.**

---

## Pre-installed Script

Script path: `/opt/data/custom-skills/channel-summarizer/fetch_history.py`

### Usage

```bash
python3 /opt/data/custom-skills/channel-summarizer/fetch_history.py <CHANNEL_ID> --limit 250
```

- Replace `<CHANNEL_ID>` with the actual Slack channel ID from the current message context.
- Increase `--limit` up to 500 for very busy channels, or as the user requests.

### Flags

| Flag | Default | Description |
|---|---|---|
| `--limit N` | `250` | Number of messages to fetch. Values > 1000 trigger automatic pagination. |

---

## Instructions for Hermes

1. Extract the channel ID from the current Slack message context.
2. Run the script using `run_command` with the channel ID and `--limit 250`.
3. Read the chronological transcript from the output (format: `[timestamp] DisplayName: message`).
4. Provide a structured summary covering:
   - The general topic or context
   - Key decisions made
   - Outstanding action items
   - Important files or links shared
   - The approximate time span covered

---

## Trigger Phrases

Activate when the user says:
- "summarize the chat"
- "summarize this channel"
- "read channel history"
- "catch me up"
- "catch up on this channel"
- "what happened before you joined?"
- "what did I miss?"
- "recap this channel"
- "explain the channel history"
