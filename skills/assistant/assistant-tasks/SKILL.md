---
name: assistant-tasks
description: "Create tasks AND create/update projects on the SuperPixel Assistant (the studio's single source of truth for project info), list projects, read the member directory, and link members' Slack accounts — all via the assistant web app's internal HTTP API. Use when asked to add/create/assign a task, create a project (e.g. from a brief in this channel), change a project's deadline/start date/description/tags, or look up projects or team members. Entering it here updates every surface — dashboard, schedule, clock, constellation — with no retyping."
version: 1.1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [task, tasks, assign, assignment, project, projects, create project, new project, board, todo, deadline, change deadline, start date, reschedule, postpone, tags, flagship, brief, sow, member, directory, roster, team, buat project, ubah deadline]
    related_skills: [channel-summarizer, document-reader]
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

Returns `{projects: [{id, name, color, createdBy, description, startDate, deadline, tags, doneAt}]}`.

## Create a project (e.g. from a brief in the channel)

When someone asks you to create a project — especially "from this brief" /
"from the SOW above" — FIRST read the brief (channel-summarizer `--thread` /
document-reader for attached PDFs), extract name, dates, and a 1–3 sentence
description, then create it. Never ask the user to retype information that
is already in the brief.

```bash
curl -s -X POST http://assistant-web:3000/api/internal/projects \
  -H "x-internal-token: $INTERNAL_TOKEN" \
  -H "content-type: application/json" \
  -d '{
    "name": "HHN14 RaveYard Pre-Show",
    "description": "Additional pre-show dance instructional content for Halloween Horror Nights 14.",
    "startDate": "2026-10-10",
    "deadline": "2026-10-25",
    "tags": ["high-budget"],
    "slackChannel": "#proj-raveyard-hhn2026",
    "createdBy": {"name": "Krisna", "slackId": "U0XXXXXXX"}
  }'
```

Rules:
- `name` is required; everything else optional. Dates are `YYYY-MM-DD`.
- `tags`: any of `flagship`, `high-budget`, `retainer`, `first-client`.
- `createdBy`: the Slack user who ASKED you (their display name + Slack id
  from the conversation) — never invent someone.
- 409 means a project with that name already exists — update it instead.
- On success, repeat the `summary` field to the user as confirmation.

## Update a project (deadline, dates, description, tags)

"Move the NEON deadline to Nov 3", "retag X as flagship", "update the
description". One call — it propagates to the dashboard, schedule, clock and
constellation automatically; never tell the user to also edit it elsewhere.

```bash
curl -s -X PATCH http://assistant-web:3000/api/internal/projects \
  -H "x-internal-token: $INTERNAL_TOKEN" \
  -H "content-type: application/json" \
  -d '{"project": "NEON", "deadline": "2026-11-03"}'
```

Rules:
- `project`: id or name (case-insensitive, unique partial works).
- Updatable: `name`, `description`, `startDate`, `deadline`, `tags`,
  `slackChannel`. Send `null` for a date to clear it.
- NOT updatable here (the API will refuse): `doneAt` (projects are marked
  done via the web app's wrap-up flow — flagship projects require a
  post-mortem first), `archived`, folders. If asked, explain that and link
  the project page.
- On success, repeat the `summary` to the user.

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

## List a member's open tasks

```bash
curl -s "http://assistant-web:3000/api/internal/tasks?assignee=U0XXXXXXX" \
  -H "x-internal-token: $INTERNAL_TOKEN"
```

`assignee` is a Slack id — resolve names via the member directory first.
Returns `{tasks:[{id, projectId, title, phase, status, dueDate, ...}]}` —
open tasks only, soonest deadline first.

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
