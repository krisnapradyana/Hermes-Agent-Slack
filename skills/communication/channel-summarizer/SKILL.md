---
name: channel-summarizer
description: "Read the chat history of any Slack channel — including the channel this conversation is happening in — and summarize, recap, or answer questions about it. Use for ANY request about what was said, discussed, decided, or missed in a channel, even when the user never says 'summarize': catch me up, what did I miss, what happened here, what's been going on, remember this channel / what we discussed, recap, tl;dr, who said what, what did the team decide, rangkum, ringkas, rekap channel ini. Supports date-range filtering (last week, December, Q1)."
version: 3.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [summarize, summary, channel, history, catch up, catch me up, what did i miss, what happened, whats been going on, chat history, read channel, read messages, this channel, here, remember, recall, recap, tldr, digest, review, discussion, decisions, date range, since, until, last week, rangkum, ringkas, rekap]
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

**NEVER install anything for this skill.** The script has ZERO external
dependencies (Python stdlib + curl only). Do NOT `pip install` slack_sdk or
anything else, and do NOT write your own fetch script. If you are tempted to
install something, you are doing it wrong — run the pre-installed script.

---

## When this skill applies (implicit requests count!)

Users almost never say the word "skill" or "summarize". ALL of these mean
"run the fetch script and summarize the result":

- "catch me up" / "what did I miss?" / "what's been going on?"
- "what happened in this channel?" / "what happened here last week?"
- "do you remember what we discussed?" / "remember this channel"
- "what did the team decide about X?" / "who said what about X?"
- "recap" / "tl;dr" / "give me a digest"
- Indonesian: "rangkum channel ini", "ringkas obrolan", "rekap chat"

You are stateless between conversations — you do NOT remember past channel
messages on your own. The ONLY way to "remember" or know what was said in a
channel is to fetch its history with this script. So any question about past
channel content ⇒ run the script first, then answer from the transcript.

---

## Current channel ("this channel", "here", the channel you reside in)

When the user says "this channel", "here", or just asks what happened without
naming a channel, they mean **the channel the current message came from**.
Its channel ID is already in your conversation context (the Slack channel ID
of this very conversation, format `C…`/`G…`). Use it directly — NEVER ask the
user for a channel ID in that case.

---

## Pre-installed Script

Script path: `/opt/data/custom-skills/communication/channel-summarizer/fetch_history.py`

### First-run check (one time only)

Before the very first use, verify the script is in place — once, never again:

```bash
[ -f /opt/data/.channel-summarizer-ready ] || { test -f /opt/data/custom-skills/communication/channel-summarizer/fetch_history.py && touch /opt/data/.channel-summarizer-ready && echo READY; }
```

- If the marker `/opt/data/.channel-summarizer-ready` already exists, skip
  this entirely and just run the script.
- If the script file is missing, report:
  `⛔ fetch_history.py is missing from custom-skills. Ask your admin to check the skills mount.`
  Do NOT recreate it, download anything, or install a replacement.

There is nothing to install — ever. The script runs on the container's
Python as-is.

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
- "remember this channel" / "do you remember what we discussed?"
- "what's been going on here?" / "what did the team decide?"
- "rangkum / ringkas / rekap channel ini"
- "summarize last [month/week/period]" → use `--since` / `--until`
- "what happened in [month/quarter/year]?" → use `--since` / `--until`
- "summarize messages from [date] to [date]" → use `--since` / `--until`
- "what was discussed during [period]?" → use `--since` / `--until`
