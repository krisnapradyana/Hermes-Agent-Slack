---
name: assistant-tasks
description: "Create tasks on SuperPixel Assistant project boards, list projects, read the member directory, and link members' Slack accounts — all via the assistant web app's internal HTTP API. Use when asked to add/create/assign a task, or to look up projects or team members."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [task, tasks, assign, assignment, project, board, todo, deadline, member, directory, roster, team]
    related_skills: []
---

# SuperPixel Assistant — Tasks & Directory API

The SuperPixel Assistant web app (project boards, tasks, member directory,
timeclock views) runs as the container `assistant-web` on your Docker network.

**CRITICAL — read before doing anything:**
- This is an **HTTP API**. It is NOT a file on disk, NOT a database you can
  open, NOT reachable via the public URL with any token you hold.
- **Never** explore the filesystem, source code, or try other tokens/auth
  methods for this. If a call fails, report the API's error message verbatim.
- Auth for every call: header `x-internal-token` with the value of your
  `INTERNAL_TOKEN` environment variable (already in your env).
- Base URL: `http://assistant-web:3000`

## List projects (do this first to resolve names)

```bash
curl -s http://assistant-web:3000/api/internal/projects \
  -H "x-internal-token: $INTERNAL_TOKEN"
```

Returns `{projects: [{id, name, color, createdBy}]}`.

## Create a task

```bash
curl -s -X POST http://assistant-web:3000/api/internal/tasks \
  -H "x-internal-token: $INTERNAL_TOKEN" \
  -H "content-type: application/json" \
  -d '{
    "project": "Superpixel Assistant development",
    "title": "test",
    "assignee": "Krisna",
    "dueDate": "2026-09-18",
    "phase": "Development",
    "note": "Optional longer description"
  }'
```

Rules:
- `project`: id or name; case-insensitive; a unique partial name works.
- `title`: required.
- `assignee` (optional): a member's name (resolved via the member directory —
  their record must have a Slack account linked) or a raw Slack id (U…).
  The assignee gets a Slack DM automatically — do not DM them yourself.
- `dueDate` / `startDate` (optional): `YYYY-MM-DD`. Convert phrases like
  "3 days from now" to a concrete date yourself before calling.
- The API is **create-only**. You cannot edit, complete, or delete tasks —
  if asked, say those actions are done in the web app for now.
- On success the response contains `summary` — repeat it to the user as
  confirmation.
- On error the response `error` explains what to fix (ambiguous project name,
  member without a linked Slack account, etc.). Fix and retry once; if it
  still fails, tell the user the error text.

## Member directory (read + link)

```bash
# roster: {members: [{id, name, type, primaryRole, slackId}]}
curl -s http://assistant-web:3000/api/internal/directory/members \
  -H "x-internal-token: $INTERNAL_TOKEN"

# link a member record to a Slack account
curl -s -X POST http://assistant-web:3000/api/internal/directory/link \
  -H "x-internal-token: $INTERNAL_TOKEN" \
  -H "content-type: application/json" \
  -d '{"links":[{"name":"Krisna","slackId":"U0XXXXXXX"}]}'
```

Use the roster to answer "who does X / what is Y's role" questions and to
check whether an assignee has a Slack account linked before creating a task
for them.

## What lives where (so you stop looking in the wrong place)

- Tasks, projects, member directory → this API (above).
- Who is clocked in / attendance / standby / general duty → read the file
  `TEAM-STATUS.md` in the Drive `SUPERPIXEL` folder (auto-generated; never
  edit it).
- Time clock actions (clock in/out) → not available to you; people use
  https://clock.spx-assistant.duckdns.org themselves.
