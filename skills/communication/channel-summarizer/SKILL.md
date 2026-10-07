---
name: channel-summarizer
description: "Read the chat history of any Slack channel OR a single thread — including the channel/thread this conversation is happening in — and summarize, recap, or answer questions about it, INCLUDING attached images/screenshots AND uploaded documents (PDF, DOCX — downloadable for viewing/reading), and workspace-wide recaps across every channel the bot is in. Use for ANY request about what was said, discussed, decided, shared, uploaded, or missed, even when the user never says 'summarize': catch me up, what did I miss, what happened here, read this thread, what do you think of the doc/file above, did you see any uploaded files, remember this channel, recap, tl;dr, who said what, recent chats across the workspace, rangkum, ringkas, rekap, baca thread ini, lihat gambar/dokumen di atas. Supports date-range filtering (last week, December, Q1)."
version: 3.3.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [summarize, summary, channel, history, catch up, catch me up, what did i miss, what happened, whats been going on, chat history, read channel, read messages, this channel, here, thread, this thread, read thread, above, remember, recall, recap, tldr, digest, review, discussion, decisions, image, images, screenshot, picture, photo, attachment, file, files, uploaded, document, doc, pdf, sow, contract, look at, workspace, all channels, every channel, date range, since, until, last week, rangkum, ringkas, rekap, baca, lihat, gambar, dokumen]
    related_skills: [document-reader]
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
- "read this thread" / "what's this thread about" / being tagged mid-thread
  with a question about the discussion above you
- "look at the image/screenshot above" / "what does that screenshot say"
- Indonesian: "rangkum channel ini", "ringkas obrolan", "rekap chat",
  "baca thread ini", "lihat gambar di atas"

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
| `--thread TS` | *(none)* | Fetch ONE thread only (TS = root message's Slack timestamp) |
| `--download-images [N]` | off / `5` | Download the newest N image attachments to `/tmp` for viewing |
| `--download-files [N]` | off / `5` | Same, but ALL attachment types — PDF, DOCX, TXT, CSV, images |
| `--list-channels` | off | Print every channel the bot is in (`<id>\t#<name>`); pass `-` as channel id |

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

### Case 4 — ONE thread (tagged in a thread, or "read/summarize this thread")

```bash
python3 /opt/data/custom-skills/communication/channel-summarizer/fetch_history.py <CHANNEL_ID> --thread <THREAD_TS>
```

`<THREAD_TS>` is the Slack timestamp of the thread's ROOT message (format
`1759640000.123456`). When you are replying inside a thread, that timestamp
is in your conversation context — use it directly, never ask the user for it.

**When you are tagged inside a thread, ALWAYS run this FIRST and answer from
the transcript.** Never ask the user to repeat or re-explain what is above
you in the thread — read it yourself.

---

### Case 5 — Images and screenshots in the history

```bash
python3 /opt/data/custom-skills/communication/channel-summarizer/fetch_history.py <CHANNEL_ID> --download-images
# or for one thread:
python3 /opt/data/custom-skills/communication/channel-summarizer/fetch_history.py <CHANNEL_ID> --thread <THREAD_TS> --download-images
```

Use when the user asks about a picture, screenshot, render, or attachment in
the history ("look at the image above", "what does that screenshot say",
"lihat gambar di atas"). The script downloads the newest 5 image attachments
(pass a number for more, max 20) to `/tmp/hermes_gen_slackimg_*` and prints
the local paths in an `IMAGES SAVED FOR VIEWING` section.

- **Open those `/tmp/...` paths with your image-viewing capability**, then
  answer from what you see.
- If you cannot view image files, say so honestly and describe only the
  filenames/senders — do not guess at image content.
- If a line says `download refused (bot token likely missing the files:read
  scope)`, report exactly that to the user so the admin can add the scope.
- The files are temporary (`/tmp`, auto-cleaned) — never promise they persist.

---

### Case 6 — Documents uploaded EARLIER in the channel/thread

Use when the user asks about a file posted in a previous message — "what do
you think of the doc above", "did you see any uploaded files", "review the
SOW Kelvin's team posted" — i.e. the file is NOT attached to the message
that mentions you, so there is no cached local path.

```bash
python3 /opt/data/custom-skills/communication/channel-summarizer/fetch_history.py <CHANNEL_ID> --thread <THREAD_TS> --download-files
# or channel-wide: ... <CHANNEL_ID> --download-files
```

Then read each saved PDF/DOCX path with the **document-reader** skill's
extraction snippet (pymupdf4llm / docx2txt) and answer using its response
format. Images in the batch you can view directly.

---

### Case 7 — Workspace-wide recap ("recent chats across all channels")

NEVER write your own Slack API code for this. Instead:

```bash
python3 /opt/data/custom-skills/communication/channel-summarizer/fetch_history.py - --list-channels
```

…then run the script per channel of interest (use `--since` to keep each
fetch small, e.g. the last day or two) and synthesize one summary across the
transcripts. Skip channels that are clearly irrelevant to the question.

---

### Case 8 — Date range (most common for historical queries)

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
- "read this thread" / tagged in a thread → `--thread <TS>` FIRST, then answer
- "look at the image/screenshot above" → `--download-images`, then view
- "rangkum / ringkas / rekap channel ini" / "baca thread ini" / "lihat gambar"
- "summarize last [month/week/period]" → use `--since` / `--until`
- "what happened in [month/quarter/year]?" → use `--since` / `--until`
- "summarize messages from [date] to [date]" → use `--since` / `--until`
- "what was discussed during [period]?" → use `--since` / `--until`
