---
name: google-workspace
description: "Use Google Workspace APIs to create Google Docs, Slides, Sheets, and Calendar events. Covers authentication, creating documents, uploading to Drive, and returning links to users via Slack."
version: 2.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [google, docs, slides, sheets, calendar, drive, create, document, spreadsheet, presentation, event, workspace, gdocs, gsheets, gslides, gcal]
    related_skills: [google-auth-helper]
---

# Google Workspace — Create & Deliver

> **Auth is already configured.** The OAuth token lives at `~/.hermes/google_token.json`.
> Do NOT ask the user to set up OAuth or download credentials — it is done.

---

## ⛔ CRITICAL — Do NOT generate Python code

**All Google Workspace operations use pre-installed scripts.** Do NOT write or generate Python code for Docs, Slides, Sheets, or Calendar. Run the correct script directly.

Script directory: `/opt/data/custom-skills/google-workspace/scripts/`

---

## Auth — No Token Found

If a script outputs an auth prompt (starting with 🔗), copy and send that message verbatim to the user. Do not try to fix or generate auth code yourself.

---

## Create a Google Doc

```bash
python3 /opt/data/custom-skills/google-workspace/scripts/create_doc.py \
  "<SLACK_USER_ID>" \
  "<TITLE>" \
  "<CONTENT>"
```

- `SLACK_USER_ID` — from the current Slack message context
- `TITLE` — the document title
- `CONTENT` — full text body (can be multiline, quote carefully)

---

## Create a Google Slides Presentation

```bash
python3 /opt/data/custom-skills/google-workspace/scripts/create_slides.py \
  "<SLACK_USER_ID>" \
  "<TITLE>" \
  '<SLIDES_JSON>'
```

- `SLIDES_JSON` — a JSON array of slide objects: `[{"title":"Slide 1","body":"Content"},...]`
- Omit `SLIDES_JSON` to create a blank presentation.

---

## Create a Google Sheet

```bash
python3 /opt/data/custom-skills/google-workspace/scripts/create_sheet.py \
  "<SLACK_USER_ID>" \
  "<TITLE>" \
  '<DATA_JSON>'
```

- `DATA_JSON` — a JSON 2D array: `[["Header A","Header B"],["Row1A","Row1B"],...]`
- Omit `DATA_JSON` to create an empty sheet.

---

## Create a Google Calendar Event

```bash
python3 /opt/data/custom-skills/google-workspace/scripts/create_calendar_event.py \
  "<SLACK_USER_ID>" \
  '<EVENT_JSON>'
```

`EVENT_JSON` fields:
| Field | Type | Required | Description |
|---|---|---|---|
| `title` | string | ✅ | Event name |
| `start` | ISO 8601 string | ✅ | `"2026-06-25T10:00:00+07:00"` or `"2026-06-25"` for all-day |
| `end` | ISO 8601 string | ✅ | Same format as `start` |
| `description` | string | ❌ | Event description |
| `attendees` | array of emails | ❌ | `["alice@example.com"]` |
| `timezone` | string | ❌ | Default `"UTC"`, e.g. `"Asia/Jakarta"` |

---

## Delivering Results to Slack

After running any script, **send only the link** — do not summarize the document content in chat.

```
✅ Done! Here's your Google Doc:
https://docs.google.com/document/d/XXXX/edit
```
