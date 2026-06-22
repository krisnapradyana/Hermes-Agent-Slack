"""
fetch_history.py — Slack channel history fetcher for Hermes
============================================================
Fetches the last N root messages from a Slack channel, then fetches all
thread replies for any message that has them. Prints a clean, chronological
transcript to stdout — root messages followed by indented thread replies.

Usage:
    python3 fetch_history.py <CHANNEL_ID> [--limit N]

Arguments:
    CHANNEL_ID   Slack channel ID (e.g. C0B9YPS8HDZ)
    --limit N    Number of root messages to fetch (default: 250)
                 Thread replies are always fetched in full regardless of this limit.

Environment:
    SLACK_BOT_TOKEN   Required. Bot token with channels:history + users:read scopes.

Required Scopes:
    channels:history  (or groups:history for private channels)
    channels:read
    users:read
"""

import os
import sys
import argparse
from datetime import datetime

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ImportError:
    print(
        "Error: slack-sdk is not installed.\n"
        "Run: pip install slack-sdk",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# User ID → Display Name Cache
# ---------------------------------------------------------------------------

_user_cache: dict[str, str] = {}


def resolve_user(client: WebClient, user_id: str) -> str:
    """Return the display name for a Slack user ID, falling back to the ID."""
    if not user_id:
        return "Unknown"

    if user_id in _user_cache:
        return _user_cache[user_id]

    # Bot IDs start with 'B' — skip API call
    if user_id.startswith("B"):
        _user_cache[user_id] = f"Bot({user_id})"
        return _user_cache[user_id]

    try:
        resp = client.users_info(user=user_id)
        profile = resp["user"]["profile"]
        name = (
            profile.get("display_name")
            or profile.get("real_name")
            or user_id
        )
        _user_cache[user_id] = name
    except SlackApiError:
        _user_cache[user_id] = user_id  # Graceful fallback

    return _user_cache[user_id]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Subtypes to skip — system events with no useful content
_SKIP_SUBTYPES = {
    "channel_join", "channel_leave", "channel_purpose",
    "channel_topic", "channel_archive", "channel_unarchive",
}


def format_message(client: WebClient, msg: dict, prefix: str = "") -> str | None:
    """Format a single message dict into a readable line, or None if it should be skipped."""
    subtype = msg.get("subtype", "")
    text = msg.get("text", "").strip()

    if not text or subtype in _SKIP_SUBTYPES:
        return None

    ts = float(msg.get("ts", 0))
    time_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

    user_id = msg.get("user") or msg.get("bot_id", "")
    if msg.get("user"):
        author = resolve_user(client, user_id)
    elif msg.get("bot_id"):
        # Try to use the bot's username if available
        author = msg.get("username") or f"Bot({msg.get('bot_id', '?')})"
    else:
        author = "Unknown"

    return f"{prefix}[{time_str}] {author}: {text}"


def fetch_thread_replies(client: WebClient, channel_id: str, thread_ts: str) -> list[str]:
    """
    Fetch all replies for a given thread. Returns formatted lines (indented).
    The first message returned by conversations.replies is the root message itself,
    so we skip it (index 0) to avoid duplicating it.
    """
    lines = []
    try:
        resp = client.conversations_replies(channel=channel_id, ts=thread_ts)
        replies = resp.get("messages", [])

        # Handle pagination for very long threads
        while resp.get("has_more"):
            next_cursor = resp.get("response_metadata", {}).get("next_cursor", "")
            if not next_cursor:
                break
            resp = client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                cursor=next_cursor,
            )
            replies.extend(resp.get("messages", []))

        # Skip index 0 — it's the root message (already printed)
        for reply in replies[1:]:
            line = format_message(client, reply, prefix="    ↳ ")
            if line:
                lines.append(line)

    except SlackApiError as e:
        lines.append(f"    ↳ [Error fetching thread: {e.response.get('error', str(e))}]")

    return lines


# ---------------------------------------------------------------------------
# Main History Fetcher
# ---------------------------------------------------------------------------

def fetch_history(channel_id: str, limit: int = 250) -> None:
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        print("Error: SLACK_BOT_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    client = WebClient(token=token)
    root_messages: list[dict] = []

    try:
        # Fetch root messages (conversations.history does NOT include thread replies)
        remaining = limit
        cursor = None

        while remaining > 0:
            batch_size = min(remaining, 1000)
            kwargs: dict = {"channel": channel_id, "limit": batch_size}
            if cursor:
                kwargs["cursor"] = cursor

            resp = client.conversations_history(**kwargs)

            if not resp.get("ok"):
                error = resp.get("error", "unknown_error")
                print(f"Error fetching history: {error}", file=sys.stderr)
                if error == "missing_scope":
                    print(
                        "The Slack app requires 'channels:history' and/or 'groups:history' scopes.",
                        file=sys.stderr,
                    )
                sys.exit(1)

            batch = resp.get("messages", [])
            root_messages.extend(batch)
            remaining -= len(batch)

            next_cursor = resp.get("response_metadata", {}).get("next_cursor", "")
            if not next_cursor or len(batch) < batch_size:
                break
            cursor = next_cursor

    except SlackApiError as e:
        error = e.response.get("error", str(e))
        print(f"Slack API error: {error}", file=sys.stderr)
        if error == "channel_not_found":
            print("Check that the bot is a member of the channel.", file=sys.stderr)
        sys.exit(1)

    if not root_messages:
        print("No messages found in this channel.")
        return

    # Build chronological transcript
    # conversations.history returns newest-first, so reverse for chronological order
    output_lines: list[str] = []
    thread_count = 0
    reply_count = 0

    for msg in reversed(root_messages):
        line = format_message(client, msg)
        if not line:
            continue

        output_lines.append(line)

        # If this root message has thread replies, fetch them all
        if msg.get("reply_count", 0) > 0:
            thread_ts = msg.get("ts", "")
            thread_lines = fetch_thread_replies(client, channel_id, thread_ts)
            if thread_lines:
                output_lines.extend(thread_lines)
                thread_count += 1
                reply_count += len(thread_lines)

    root_count = len([l for l in output_lines if not l.startswith("    ↳")])
    print(
        f"--- CHANNEL HISTORY "
        f"({root_count} messages, {thread_count} threads, {reply_count} replies) ---"
    )
    print("\n".join(output_lines))
    print("--- END OF HISTORY ---")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Slack channel history (including thread replies) and print a clean transcript."
    )
    parser.add_argument("channel_id", help="Slack channel ID (e.g. C0B9YPS8HDZ)")
    parser.add_argument(
        "--limit",
        type=int,
        default=250,
        metavar="N",
        help="Number of root messages to fetch (default: 250). Thread replies are always fetched in full.",
    )
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be a positive integer")

    fetch_history(args.channel_id, args.limit)


if __name__ == "__main__":
    main()
