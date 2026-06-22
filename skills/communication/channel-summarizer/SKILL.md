---
name: channel-summarizer
description: "Read all chat history in the current channel and summarize it, with optional date range filtering."
version: 3.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [summarize, channel, history, catch up, chat history, read channel, date range, since, recap]
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

Script path: `/opt/data/custom-skills/communication/channel-summarizer/fetch_history.py`

---

## Flags Reference

| Flag | Default | Description |
|---|---|---|
| `--limit N` | `250` | Max root messages when no date range is set |
| `--since DATE` | *(none)* | Fetch messages on or after this date (UTC) |
| `--until DATE` | *(none)* | Fetch messages on or before this date (UTC) |

**Accepted date formats:**
- `YYYY-MM-DD` → e.g. `2024-12-01`
- `YYYY-MM-DDTHH:MM:SS` → e.g. `2024-12-01T09:00:00`

> When `--since` or `--until` is set, `--limit` is ignored and **all messages** in the date range are fetched automatically.

---

## Instructions for Hermes

### Case 1 — Recent history (no date specified)

```bash
python3 /opt/data/custom-skills/communication/channel-summarizer/fetch_history.py <CHANNEL_ID> --limit 250
```

Use when the user says: *"summarize the chat"*, *"catch me up"*, *"what did I miss?"*

---

### Case 2 — From a specific date onwards

```bash
python3 /opt/data/custom-skills/communication/channel-summarizer/fetch_history.py <CHANNEL_ID> --since YYYY-MM-DD
```

Use when the user says: *"summarize since January 1st"*, *"what happened after the launch?"*

---

### Case 3 — Up to a specific date

```bash
python3 /opt/data/custom-skills/communication/channel-summarizer/fetch_history.py <CHANNEL_ID> --until YYYY-MM-DD
```

---

### Case 4 — Date range (most common for historical queries)

```bash
python3 /opt/data/custom-skills/communication/channel-summarizer/fetch_history.py <CHANNEL_ID> --since YYYY-MM-DD --until YYYY-MM-DD
```

Use when the user says: *"summarize last December"*, *"what happened in Q1 2025?"*, *"recap messages from winter"*

**Examples:**
```bash
# Last 250 messages (default)
python3 /opt/data/custom-skills/communication/channel-summarizer/fetch_history.py C0B9YPS8HDZ

# All of December 2024
python3 /opt/data/custom-skills/communication/channel-summarizer/fetch_history.py C0B9YPS8HDZ --since 2024-12-01 --until 2024-12-31

# Q1 2025 (Jan–Mar)
python3 /opt/data/custom-skills/communication/channel-summarizer/fetch_history.py C0B9YPS8HDZ --since 2025-01-01 --until 2025-03-31

# Single day
python3 /opt/data/custom-skills/communication/channel-summarizer/fetch_history.py C0B9YPS8HDZ --since 2025-06-22 --until 2025-06-22

# From a date to now (no --until)
python3 /opt/data/custom-skills/communication/channel-summarizer/fetch_history.py C0B9YPS8HDZ --since 2025-06-01
```

---

### After running the script

Read the chronological transcript (format: `[YYYY-MM-DD HH:MM:SS UTC] DisplayName: message`) and provide a structured summary covering:
- The general topic or context
- Key decisions made
- Outstanding action items
- Important files or links shared
- The time span covered

---

## Trigger Phrases

Activate when the user says:
- "summarize the chat"
- "summarize this channel"
- "catch me up" / "catch up on this channel"
- "what did I miss?"
- "read channel history"
- "recap this channel"
- "what happened before you joined?"
- "summarize last [month/week/period]" → use `--since` / `--until`
- "what happened in [month/quarter/year]?" → use `--since` / `--until`
- "summarize messages from [date] to [date]" → use `--since` / `--until`
- "what was discussed during [period]?" → use `--since` / `--until`
