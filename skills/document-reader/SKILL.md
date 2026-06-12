---
name: document-reader
description: "Read and analyse documents attached in Slack (PDF, DOCX, TXT, CSV, JSON, YAML) and provide summaries and recommendations."
version: 2.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [document, pdf, read, analyse, analyze, summarize, summarise, review, contract, report, file, attachment]
    related_skills: []
---

# Document Reader & Advisor

Read documents shared in Slack and provide analysis, summaries, and recommendations.

**CRITICAL: When a user uploads a file or asks you to read a document — use this skill.**

## How Slack File Attachments Work

When a user uploads a file to Slack, the message event contains a `files` array. Hermes automatically downloads the file and passes it to you as a cached local path. **You do not need to download it manually.** Use the local path directly.

If Hermes gives you the file content inline (for small text files), use that directly without running any tool.

## Reading a PDF or DOCX with `run_command`

Use `run_command` to extract text from PDFs and Word documents:

```bash
pip install pymupdf4llm docx2txt -q && python3 - << 'EOF'
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
2–4 sentences covering what the document is about.

### 🔍 Key Findings
Bullet points of the most important facts, data, or decisions.

### 💡 Recommendations
Specific, actionable advice referencing exact sections or quotes from the document.

### ❓ Follow-up Questions (if needed)
Anything that would help give better advice.

## Trigger Phrases

Activate when the user:
- Uploads any file to Slack
- Says "read this", "analyse this", "summarise this file"
- Says "give me recommendations based on this document"
- Says "review my contract / report / spec / proposal"
- Shares a PDF, DOCX, or text file

## Error Handling

- **HTTP 403 on download**: the Slack app is missing `files:read` scope
- **Empty content**: tell the user and ask them to try a different format
- **Unsupported type**: list supported formats and ask to convert
