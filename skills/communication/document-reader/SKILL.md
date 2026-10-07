---
name: document-reader
description: "Read and analyse documents attached in Slack (PDF, DOCX, TXT, CSV, JSON, YAML) and provide summaries and recommendations — including documents uploaded in EARLIER messages ('the doc above', 'the SOW posted earlier'), fetched via the channel-summarizer skill."
version: 2.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [document, pdf, docx, read, analyse, analyze, summarize, summarise, review, contract, sow, brief, report, file, attachment, uploaded, doc above, earlier]
    related_skills: [channel-summarizer]
---

# Document Reader & Advisor

> ⚠️ **READ-ONLY SKILL** — This skill is for **reading and analysing** documents uploaded by users. Creating, generating, or writing new documents is governed by the `security-policy` skill. Only Google Workspace outputs (Docs, Slides, Sheets, Calendar) are permitted as created documents.

Read documents shared in Slack and provide analysis, summaries, and recommendations.

**CRITICAL: When a user uploads a file or asks you to read a document — use this skill.**

## How Slack File Attachments Work

When a user uploads a file to Slack, the message event contains a `files` array. Hermes automatically downloads the file and passes it to you as a cached local path. **You do not need to download it manually.** Use the local path directly.

If Hermes gives you the file content inline (for small text files), use that directly without running any tool.

## File uploaded in an EARLIER message ("the doc above")

If the user asks about a document that was posted in a PREVIOUS message —
"what do you think of this above", "did you see the uploaded file", "review
the SOW posted earlier" — there is NO cached local path in your context.
Do NOT say you can't see it and do NOT write custom Slack API code. Fetch it
with the channel-summarizer script:

```bash
python3 /opt/data/custom-skills/communication/channel-summarizer/fetch_history.py <CHANNEL_ID> --thread <THREAD_TS> --download-files
# (or channel-wide without --thread)
```

It prints saved `/tmp/...` paths — read those with the extraction snippet
below, then answer in the Response Format.

## One-time dependency setup (first run only)

Check before installing — install ONLY if the import fails, never on every run:

```bash
python3 -c "import pymupdf4llm, docx2txt" 2>/dev/null || pip install pymupdf4llm docx2txt -q
```

## Reading a PDF or DOCX with `run_command`

Use `run_command` to extract text from PDFs and Word documents (after the
one-time check above — do not prefix this with pip install):

```bash
python3 - << 'EOF'
import sys

file_path = "/path/to/the/cached/file.pdf"  # ← replace with actual path

ext = file_path.rsplit(".", 1)[-1].lower()

if ext == "pdf":
    import pymupdf4llm
    text = pymupdf4llm.to_markdown(file_path)
elif ext in ("docx", "doc"):
    import docx2txt
    text = docx2txt.process(file_path)
else:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

print(text[:50000])  # cap at 50k chars
EOF
```

Replace `/path/to/the/cached/file.pdf` with the actual path Hermes provides.

## Downloading a Slack File by URL (fallback)

If you have a Slack `url_private_download` URL instead of a local path:

```python
import os, urllib.request, tempfile

url = "https://files.slack.com/..."   # ← the url_private_download value
token = os.environ.get("SLACK_BOT_TOKEN", "")
ext = ".pdf"  # adjust based on file type

tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
tmp.close()

req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
with urllib.request.urlopen(req, timeout=60) as r:
    with open(tmp.name, "wb") as f:
        f.write(r.read())

# Now read tmp.name with pymupdf4llm or docx2txt as above
print("Downloaded to:", tmp.name)
```

## Supported Formats

| Extension | Tool |
|---|---|
| `.pdf` | `pymupdf4llm.to_markdown()` |
| `.docx` / `.doc` | `docx2txt.process()` |
| `.txt` `.md` `.csv` `.json` `.yaml` `.yml` | plain `open()` read |

## Response Format

After reading the document, always respond with this structure:

### 📄 Summary
2–4 sentences covering what the document is about

### 🔍 Key Findings
Bullet points of the most important facts, data, or decisions.

### 💡 Recommendations
Specific, actionable advice referencing exact sections or quotes from the document.

### ❓ Follow-up Questions (if needed)
Anything that would help give better advice.

## Trigger Phrases

Activate when the user:
- Uploads any file to Slack
- Asks about a file posted EARLIER: "what do you think of this above", "did
  you see any uploaded files", "review the doc/SOW posted earlier"
- Says "read this", "analyse this", "summarise this file"
- Says "give me recommendations based on this document"
- Says "review my contract / report / spec / proposal"
- Shares a PDF, DOCX, or text file

## Error Handling

- **HTTP 403 on download**: the Slack app is missing `files:read` scope
- **Empty content**: tell the user and ask them to try a different format
- **Unsupported type**: list supported formats and ask to convert
