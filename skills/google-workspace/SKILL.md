---
name: google-workspace
description: "Use Google Workspace APIs to create Google Docs, Slides, Sheets, and Calendar events. Covers authentication, creating documents, uploading to Drive, and returning links to users via Slack."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [google, docs, slides, sheets, calendar, drive, create, document, spreadsheet, presentation, event, workspace, gdocs, gsheets, gslides, gcal]
    related_skills: [google-auth-helper]
---

# Google Workspace — Create & Deliver

> **Auth is already configured.** The OAuth token lives at `/opt/data/google_token.json`.
> Do NOT ask the user to set up OAuth or download credentials — it is done.

---

## ⛔ CRITICAL — Do NOT search for these files

**NEVER run `find`, `search_files`, `ls`, or any file-discovery command to locate the Google token or client secret.**
They are at fixed, known paths. If they are missing, instruct the user to re-authorize at the OAuth helper — do not search.

---

## File Paths — Exact, Always

```python
import os

# OAuth token (symlinked from /documents/token.json at container start)
TOKEN_FILE = os.path.expanduser("~/.hermes/google_token.json")

# OAuth client secret (symlinked from /documents/google_client_secret.json)
CLIENT_SECRET_FILE = os.path.expanduser("~/.hermes/google_client_secret.json")
```

`os.path.expanduser("~")` resolves the container's actual home directory automatically — no guessing, no searching.

---

## Authentication — Always Use This Pattern


```python
import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

TOKEN_FILE = os.path.expanduser("~/.hermes/google_token.json")

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar",
]

creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())
```

If `Credentials.from_authorized_user_file` raises `FileNotFoundError`, apply the `google-auth-helper` skill.

---

## Create a Google Doc

```python
from googleapiclient.discovery import build

docs = build("docs", "v1", credentials=creds)

# Create empty doc
doc = docs.documents().create(body={"title": "Your Title Here"}).execute()
doc_id = doc["documentId"]
doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

# Insert content
docs.documents().batchUpdate(
    documentId=doc_id,
    body={"requests": [
        {"insertText": {"location": {"index": 1}, "text": "Your content here\n"}}
    ]}
).execute()

print(doc_url)
```

---

## Create a Google Slides Presentation

```python
slides_svc = build("slides", "v1", credentials=creds)

presentation = slides_svc.presentations().create(
    body={"title": "Your Presentation Title"}
).execute()
pres_id = presentation["presentationId"]
pres_url = f"https://docs.google.com/presentation/d/{pres_id}/edit"

print(pres_url)
```

To add slides and content, use `presentations().batchUpdate()` with `createSlide`, `insertText`, etc.

---

## Create a Google Sheet

```python
sheets_svc = build("sheets", "v4", credentials=creds)

spreadsheet = sheets_svc.spreadsheets().create(body={
    "properties": {"title": "Your Sheet Title"},
    "sheets": [{"properties": {"title": "Sheet1"}}]
}).execute()
sheet_id = spreadsheet["spreadsheetId"]
sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"

# Write data
sheets_svc.spreadsheets().values().update(
    spreadsheetId=sheet_id,
    range="Sheet1!A1",
    valueInputOption="USER_ENTERED",
    body={"values": [["Col A", "Col B"], ["row1a", "row1b"]]}
).execute()

print(sheet_url)
```

---

## Create a Google Calendar Event

```python
cal = build("calendar", "v3", credentials=creds)

event = cal.events().insert(
    calendarId="primary",
    body={
        "summary": "Event Title",
        "description": "Event description",
        "start": {"dateTime": "2026-06-23T10:00:00+07:00"},
        "end":   {"dateTime": "2026-06-23T11:00:00+07:00"},
    }
).execute()

print(event.get("htmlLink"))
```

For all-day events, use `"date": "2026-06-23"` instead of `"dateTime"`.

---

## Upload a File to Google Drive

```python
from googleapiclient.http import MediaFileUpload

drive = build("drive", "v3", credentials=creds)

import yaml
cfg = yaml.safe_load(open("/opt/data/custom-config.yaml"))
folder_id = cfg.get("google_drive", {}).get("folder_id", "")

file_metadata = {"name": "filename.pdf", "parents": [folder_id]}
media = MediaFileUpload("/tmp/localfile.pdf", mimetype="application/pdf")
uploaded = drive.files().create(body=file_metadata, media_body=media, fields="id,webViewLink").execute()
print(uploaded["webViewLink"])
```

---

## Required pip packages

These are pre-installed in the Hermes container:
- `google-auth`
- `google-auth-oauthlib`
- `google-api-python-client`

> **Do NOT run `pip install`** — they are already available.

---

## Delivering results to Slack

After creating any document, **send only the link** — do not summarize the document content in chat.
This is the owner's explicit preference (see USER memory).

Example response format:
```
✅ Done! Here's your Google Doc:
https://docs.google.com/document/d/XXXX/edit
```

---

## Full Script Template

Use `run_command` with this pattern:

```bash
python3 - << 'EOF'
import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_FILE = os.path.expanduser("~/.hermes/google_token.json")
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar",
]

creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
if creds.expired and creds.refresh_token:
    creds.refresh(Request())

# --- your API calls here ---

EOF
```
