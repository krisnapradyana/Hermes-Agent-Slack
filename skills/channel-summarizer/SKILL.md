---
name: channel-summarizer
description: "Read all chat history in the current channel and summarize it, even if Hermes joined late."
version: 2.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [summarize, channel, history, catch up, chat history, read channel]
    related_skills: []
---

# Channel Summarizer

Use this skill when the user asks you to read the chat history of the current channel, summarize it, or catch up on what happened before you joined.

## How it works

1. Use `run_command` to execute the pre-installed Python script that fetches channel history via the Slack API `conversations.history`.
2. Extract the `channel_id` from the current message context and pass it as an argument to the script.
3. The script resolves raw Slack User IDs to display names automatically.
4. Read the clean, chronological transcript and synthesize a summary for the user.

## Instructions for Hermes

1. Extract the channel ID from the current Slack context.
2. Execute the following command using `run_command`:
   ```bash
   python3 /opt/data/custom-skills/channel-summarizer/fetch_history.py <CHANNEL_ID> --limit 250
   ```
   *(Replace `<CHANNEL_ID>` with the actual Slack channel ID. Increase `--limit` up to 500 for very busy channels, or as the user requests.)*
3. Read the chronological transcript from the output (format: `[timestamp] DisplayName: message`).
4. Provide a structured and informative summary of the conversation back to the user, highlighting:
   - The general topic or context.
   - Any key decisions made.
   - Any outstanding action items.
   - Important files or links shared (if mentioned).
   - The approximate time span the history covers.
5. If the script outputs an error (such as `missing_scope` or `channel_not_found`), explain the issue directly to the user without retrying.

## Flags

| Flag | Default | Description |
|---|---|---|
| `--limit N` | `250` | Number of messages to fetch. Values > 1000 trigger automatic pagination. |

## Trigger Phrases

Activate when the user says:
- "read channel history"
- "summarize the chat"
- "what happened before you joined?"
- "catch up on this channel"
- "explain the channel history"
- "what did I miss?"
- "recap this channel"
