"""
fetch_history.py — Slack channel history fetcher for Hermes
============================================================
Zero external dependencies. Uses curl (always available in the container)
via subprocess. Fetches root messages + all thread replies.

Usage:
    python3 fetch_history.py <CHANNEL_ID> [--limit N]

Arguments:
    CHANNEL_ID   Slack channel ID (e.g. C0B9YPS8HDZ)
    --limit N    Number of root messages to fetch (default: 250)
                 Thread replies are always fetched in full.

Token resolution order:
    1. SLACK_BOT_TOKEN environment variable (preferred)
    2. /opt/data/custom-.env file (fallback for container env)

Required Slack scopes:
    channels:history  (or groups:history for private channels)
    channels:read
    users:read
"""

import subprocess
import json
import os
import sys
import argparse
from datetime import datetime


# ---------------------------------------------------------------------------
# Token Resolution
# ---------------------------------------------------------------------------

def get_token() -> str:
    """Read SLACK_BOT_TOKEN from env var first, then fall back to .env file."""
    token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    if token:
        return token

    env_file = "/opt/data/custom-.env"
    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("SLACK_BOT_TOKEN="):
                    token = line.split("=", 1)[1].strip()
                    if token:
                        return token
    except FileNotFoundError:
        pass

    print(
        "Error: SLACK_BOT_TOKEN not found in environment or /opt/data/custom-.env",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# curl Helpers
# ---------------------------------------------------------------------------

def slack_get(url: str, token: str) -> dict:
    """Make a GET request to the Slack API via curl and return parsed JSON."""
    result = subprocess.run(
        [
            "curl", "-s",
            url,
            "-H", f"Authorization: Bearer {token}",
            "-H", "Content-Type: application/json",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"curl error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"Failed to parse Slack response: {e}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# User Resolution
# ---------------------------------------------------------------------------

def build_user_map(messages: list[dict], token: str) -> dict[str, str]:
    """Fetch display names for all unique user IDs found in messages."""
    user_ids: set[str] = set()
    for m in messages:
        if "user" in m:
            user_ids.add(m["user"])
        # Also collect user IDs from thread reply previews
        for reply_user in [r.get("user") for r in m.get("replies", []) if r.get("user")]:
            user_ids.add(reply_user)

    user_map: dict[str, str] = {}
    for uid in user_ids:
        data = slack_get(f"https://slack.com/api/users.info?user={uid}", token)
        if data.get("ok"):
            user = data["user"]
            name = (
                user.get("profile", {}).get("display_name")
                or user.get("real_name")
                or user.get("name")
                or uid
            )
            user_map[uid] = name
        else:
            user_map[uid] = uid  # Graceful fallback

    return user_map


# ---------------------------------------------------------------------------
# Text Cleanup
# ---------------------------------------------------------------------------

def resolve_mentions(text: str, user_map: dict[str, str]) -> str:
    """Replace <@UXXXXXXX> Slack mention tokens with @DisplayName."""
    for uid, name in user_map.items():
        text = text.replace(f"<@{uid}>", f"@{name}")
    return text


def format_timestamp(ts: str) -> str:
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return ts


# ---------------------------------------------------------------------------
# Thread Reply Fetcher
# ---------------------------------------------------------------------------

_SKIP_SUBTYPES = {
    "channel_join", "channel_leave", "channel_purpose",
    "channel_topic", "channel_archive", "channel_unarchive",
}


def fetch_thread_replies(
    channel_id: str,
    thread_ts: str,
    token: str,
    user_map: dict[str, str],
) -> list[str]:
    """
    Fetch all replies for a thread via conversations.replies.
    The first item is the root message itself — skip it to avoid duplication.
    Returns formatted, indented lines.
    """
    lines: list[str] = []
    url = (
        f"https://slack.com/api/conversations.replies"
        f"?channel={channel_id}&ts={thread_ts}&limit=1000"
    )

    data = slack_get(url, token)
    if not data.get("ok"):
        lines.append(f"    ↳ [Thread error: {data.get('error', 'unknown')}]")
        return lines

    replies = data.get("messages", [])

    # Handle pagination for very long threads
    while data.get("has_more"):
        next_cursor = data.get("response_metadata", {}).get("next_cursor", "")
        if not next_cursor:
            break
        data = slack_get(url + f"&cursor={next_cursor}", token)
        replies.extend(data.get("messages", []))

    # Skip index 0 — it is the root message (already printed)
    for reply in replies[1:]:
        subtype = reply.get("subtype", "")
        text = reply.get("text", "").strip()
        if not text or subtype in _SKIP_SUBTYPES:
            continue

        uid = reply.get("user") or reply.get("bot_id", "")
        author = user_map.get(uid, uid or "Bot")
        ts_str = format_timestamp(reply.get("ts", ""))
        text = resolve_mentions(text, user_map)

        lines.append(f"    ↳ [{ts_str}] {author}: {text}")

        # Files in thread replies
        for f in reply.get("files", []):
            lines.append(f"      [File: {f.get('name', 'unknown')} — {f.get('mimetype', '')}]")

    return lines


# ---------------------------------------------------------------------------
# Main Fetcher
# ---------------------------------------------------------------------------

def fetch_history(channel_id: str, limit: int = 250) -> None:
    token = get_token()

    # --- Fetch root messages ---
    all_messages: list[dict] = []
    remaining = limit
    cursor_param = ""

    while remaining > 0:
        batch_size = min(remaining, 1000)
        url = (
            f"https://slack.com/api/conversations.history"
            f"?channel={channel_id}&limit={batch_size}{cursor_param}"
        )
        data = slack_get(url, token)

        if not data.get("ok"):
            error = data.get("error", "unknown_error")
            print(f"Error fetching history: {error}", file=sys.stderr)
            if error == "missing_scope":
                print(
                    "The Slack app requires 'channels:history' and/or 'groups:history' scopes.",
                    file=sys.stderr,
                )
            elif error == "channel_not_found":
                print("Check that the bot is a member of the channel.", file=sys.stderr)
            sys.exit(1)

        batch = data.get("messages", [])
        all_messages.extend(batch)
        remaining -= len(batch)

        next_cursor = data.get("response_metadata", {}).get("next_cursor", "")
        if not next_cursor or len(batch) < batch_size:
            break
        cursor_param = f"&cursor={next_cursor}"

    if not all_messages:
        print("No messages found in this channel.")
        return

    print(f"Got {len(all_messages)} root messages. Resolving users...", file=sys.stderr)

    # --- Build user map ---
    user_map = build_user_map(all_messages, token)

    # --- Build chronological transcript ---
    # conversations.history returns newest-first → reverse for chronological order
    output_lines: list[str] = []
    thread_count = 0
    reply_count = 0

    for msg in reversed(all_messages):
        subtype = msg.get("subtype", "")
        text = msg.get("text", "").strip()

        if not text or subtype in _SKIP_SUBTYPES:
            continue

        uid = msg.get("user") or msg.get("bot_id", "")
        author = user_map.get(uid, uid or "Bot")
        ts_str = format_timestamp(msg.get("ts", ""))
        text = resolve_mentions(text, user_map)

        output_lines.append(f"[{ts_str}] {author}: {text}")

        # Files attached to root message
        for f in msg.get("files", []):
            output_lines.append(
                f"  [File: {f.get('name', 'unknown')} — {f.get('mimetype', '')}]"
            )

        # Attachments (link previews, etc.)
        for a in msg.get("attachments", []):
            title = a.get("title") or a.get("text", "")[:60] or "attachment"
            output_lines.append(f"  [Attachment: {title}]")

        # Thread replies
        if msg.get("reply_count", 0) > 0:
            thread_ts = msg.get("ts", "")
            thread_lines = fetch_thread_replies(channel_id, thread_ts, token, user_map)
            if thread_lines:
                output_lines.extend(thread_lines)
                thread_count += 1
                reply_count += len(thread_lines)

    root_count = sum(1 for l in output_lines if not l.startswith("    ↳"))
    print(
        f"--- CHANNEL HISTORY "
        f"({root_count} messages · {thread_count} threads · {reply_count} replies) ---"
    )
    print("\n".join(output_lines))
    print("--- END OF HISTORY ---")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch Slack channel history (including thread replies) "
            "and print a clean transcript. Zero external dependencies."
        )
    )
    parser.add_argument("channel_id", help="Slack channel ID (e.g. C0B9YPS8HDZ)")
    parser.add_argument(
        "--limit",
        type=int,
        default=250,
        metavar="N",
        help="Number of root messages to fetch (default: 250). Thread replies always fetched in full.",
    )
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be a positive integer")

    fetch_history(args.channel_id, args.limit)


if __name__ == "__main__":
    main()
