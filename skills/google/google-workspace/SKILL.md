---
name: google-workspace
description: "Use Google Workspace APIs to create Google Docs, Slides, Sheets, and Calendar events. Covers authentication, creating documents, uploading to Drive, and returning links to users via Slack."
version: 2.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [google, docs, slides, sheets, calendar, drive, create, document, spreadsheet, presentation, event, workspace, gdocs, gsheets, gslides, gcal]
    related_skills: [google-auth-helper]
---

# Google Workspace — Create & Deliver

---

## 🚫 ABSOLUTE RULE — READ THIS FIRST

**YOU MUST NEVER:**
- Write a Python script to **any** path — `/tmp/`, `/opt/data/`, `~`, or anywhere else
- Use `python3 - << 'EOF' ... EOF` inline heredocs
- Use `write_file`, `patch`, or any tool to create `.py` files on the fly
- Fall back to writing custom code when a script "doesn't support" something

**If a pre-installed script fails or returns an error:**
- Copy the exact error message and report it to the user
- Do NOT attempt to write a replacement or workaround script
- Respond: "⛔ The pre-installed script encountered an error: `<exact error>`. Please ask your admin to check the script."

**Pre-installed scripts already exist for every operation. Use them. Period.**

---

## Pre-installed Scripts — Use These Directly

All scripts live at `/opt/data/custom-skills/google/google-workspace/scripts/`.

Run them with `run_command`. No code writing. No temp files. Just call the script.

---

## Auth — No Token Found

If a script prints a message starting with 🔗, forward that message verbatim to the user. Do not attempt to generate auth code.

---

## Create a Google Doc

```bash
python3 /opt/data/custom-skills/google/google-workspace/scripts/create_doc.py \
  "<SLACK_USER_ID>" \
  "<TITLE>" \
  "<CONTENT>"
```

| Arg | Description |
|---|---|
| `SLACK_USER_ID` | From the current Slack message context |
| `TITLE` | Document title |
| `CONTENT` | Full text body. Quote it carefully. |

---

## Create a Google Slides Presentation

```bash
python3 /opt/data/custom-skills/google/google-workspace/scripts/create_slides.py \
  "<SLACK_USER_ID>" \
  "<TITLE>" \
  '<SLIDES_JSON>'
```

| Arg | Description |
|---|---|
| `SLACK_USER_ID` | From the current Slack message context |
| `TITLE` | Presentation title |
| `SLIDES_JSON` | JSON array: `[{"title":"Slide 1","body":"Content"},{"title":"Slide 2","body":"More"}]` — omit for blank |

---

## Create a Google Sheet

```bash
python3 /opt/data/custom-skills/google/google-workspace/scripts/create_sheet.py \
  "<SLACK_USER_ID>" \
  "<TITLE>" \
  '<DATA_JSON>'
```

| Arg | Description |
|---|---|
| `SLACK_USER_ID` | From the current Slack message context |
| `TITLE` | Spreadsheet title |
| `DATA_JSON` | JSON 2D array: `[["Header A","Header B"],["Row 1A","Row 1B"]]` — omit for empty |

---

## Create a Google Calendar Event

```bash
python3 /opt/data/custom-skills/google/google-workspace/scripts/create_calendar_event.py \
  "<SLACK_USER_ID>" \
  '<EVENT_JSON>'
```

`EVENT_JSON` fields:

| Field | Type | Required | Description |
|---|---|---|---|
| `title` | string | ✅ | Event name |
| `start` | ISO 8601 string | ✅ | `"2026-06-25T10:00:00+07:00"` (timed) or `"2026-06-25"` (all-day) |
| `end` | ISO 8601 string | ✅ | Same format as `start` |
| `description` | string | ❌ | Event details |
| `attendees` | array of emails | ❌ | `["alice@example.com", "bob@example.com"]` |
| `timezone` | string | ❌ | Default `"UTC"` — e.g. `"Asia/Jakarta"` |

---

## Delivering Results to Slack

After running any script, **send only the link** — do not summarize document content.

```
✅ Done! Here's your Google Doc:
https://docs.google.com/document/d/XXXX/edit
```
