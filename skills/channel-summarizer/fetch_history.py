"""
fetch_history.py — Slack channel history fetcher for Hermes
============================================================
Zero external dependencies. Uses curl (always available in the container)
via subprocess. Fetches root messages + all thread replies, with optional
date range filtering.

Usage:
    python3 fetch_history.py <CHANNEL_ID> [--limit N] [--since DATE] [--until DATE]

Arguments:
    CHANNEL_ID      Slack channel ID (e.g. C0B9YPS8HDZ)
    --limit N       Max root messages to fetch (default: 250; ignored when date range is set)
    --since DATE    Fetch messages on or after this date/datetime (UTC)
    --until DATE    Fetch messages on or before this date/datetime (UTC)

Date formats accepted for --since / --until:
    YYYY-MM-DD                e.g. 2024-12-01
    YYYY-MM-DDTHH:MM:SS       e.g. 2024-12-01T09:00:00
    YYYY-MM-DD HH:MM:SS       e.g. 2024-12-01 09:00:00

    Dates without a time component default to:
        --since  → start of day (00:00:00 UTC)
        --until  → end of day   (23:59:59 UTC)

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
from datetime import datetime, timezone, timedelta


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
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
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
# Date Parsing
# ---------------------------------------------------------------------------

_DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
]


def parse_date(value: str, end_of_day: bool = False) -> float:
    """
    Parse a date/datetime string into a UTC Unix timestamp.

    Args:
        value:      Date string (see module docstring for accepted formats).
        end_of_day: If True and no time component is present, use 23:59:59
                    instead of 00:00:00. Used for --until dates.

    Returns:
        UTC Unix timestamp as a float.
    """
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
            # If the format has no time component and end_of_day is requested,
            # push to 23:59:59 of that day.
            if fmt == "%Y-%m-%d" and end_of_day:
                dt = dt.replace(hour=23, minute=59, second=59)
            # Treat as UTC
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            continue

    print(
        f"Error: Cannot parse date '{value}'.\n"
        "Accepted formats: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, YYYY-MM-DD HH:MM:SS",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# curl Helper
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
    """Fetch display names for all unique user IDs found in a list of messages."""
    user_ids: set[str] = set()
    for m in messages:
        if "user" in m:
            user_ids.add(m["user"])
        for r in m.get("replies", []):
            if r.get("user"):
                user_ids.add(r["user"])

    user_map: dict[str, str] = {}
    for uid in user_ids:
        data = slack_get(f"https://slack.com/api/users.info?user={uid}", token)
        if data.get("ok"):
            profile = data["user"].get("profile", {})
            name = (
                profile.get("display_name")
                or data["user"].get("real_name")
                or data["user"].get("name")
                or uid
            )
            user_map[uid] = name
        else:
            user_map[uid] = uid
    return user_map


# ---------------------------------------------------------------------------
# Text Helpers
# ---------------------------------------------------------------------------

_SKIP_SUBTYPES = {
    "channel_join", "channel_leave", "channel_purpose",
    "channel_topic", "channel_archive", "channel_unarchive",
}


def resolve_mentions(text: str, user_map: dict[str, str]) -> str:
    """Replace <@UXXXXXXX> Slack mention tokens with @DisplayName."""
    for uid, name in user_map.items():
        text = text.replace(f"<@{uid}>", f"@{name}")
    return text


def format_ts(ts: str) -> str:
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    except (ValueError, TypeError):
        return ts


# ---------------------------------------------------------------------------
# Thread Reply Fetcher
# ---------------------------------------------------------------------------

def fetch_thread_replies(
    channel_id: str,
    thread_ts: str,
    token: str,
    user_map: dict[str, str],
) -> list[str]:
    """
    Fetch all replies for a thread. Skips the first item (root message duplicate).
    Returns indented, formatted lines.
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
    while data.get("has_more"):
        cursor = data.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
        data = slack_get(url + f"&cursor={cursor}", token)
        replies.extend(data.get("messages", []))

    for reply in replies[1:]:  # Skip index 0 — it is the root message
        subtype = reply.get("subtype", "")
        text = reply.get("text", "").strip()
        if not text or subtype in _SKIP_SUBTYPES:
            continue

        uid = reply.get("user") or reply.get("bot_id", "")
        author = user_map.get(uid, uid or "Bot")
        text = resolve_mentions(text, user_map)
        lines.append(f"    ↳ [{format_ts(reply.get('ts', ''))}] {author}: {text}")

        for f in reply.get("files", []):
            lines.append(f"      [File: {f.get('name', 'unknown')} — {f.get('mimetype', '')}]")

    return lines


# ---------------------------------------------------------------------------
# Root Message Fetcher
# ---------------------------------------------------------------------------

def fetch_root_messages(
    channel_id: str,
    token: str,
    limit: int,
    oldest_ts: float | None,
    latest_ts: float | None,
) -> list[dict]:
    """
    Fetch root messages from conversations.history with optional date range.
    Paginates automatically until `limit` is reached or no more pages exist.
    """
    messages: list[dict] = []
    cursor_param = ""
    # When a date range is set, remove the hard cap so we get everything in range.
    # Use a large sentinel instead to keep the loop simple.
    effective_limit = limit if (oldest_ts is None and latest_ts is None) else 10_000

    remaining = effective_limit

    while remaining > 0:
        batch_size = min(remaining, 1000)
        params = [f"channel={channel_id}", f"limit={batch_size}"]

        if oldest_ts is not None:
            params.append(f"oldest={oldest_ts}")
        if latest_ts is not None:
            params.append(f"latest={latest_ts}")
        if cursor_param:
            params.append(f"cursor={cursor_param}")
        # inclusive=true so boundary timestamps are included
        params.append("inclusive=true")

        url = "https://slack.com/api/conversations.history?" + "&".join(params)
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
        messages.extend(batch)
        remaining -= len(batch)

        next_cursor = data.get("response_metadata", {}).get("next_cursor", "")
        if not next_cursor or len(batch) < batch_size:
            break
        cursor_param = next_cursor

    return messages


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def fetch_history(
    channel_id: str,
    limit: int = 250,
    oldest_ts: float | None = None,
    latest_ts: float | None = None,
) -> None:
    token = get_token()

    # --- Describe what we're fetching ---
    if oldest_ts or latest_ts:
        since_str = datetime.fromtimestamp(oldest_ts, tz=timezone.utc).strftime("%Y-%m-%d") if oldest_ts else "beginning"
        until_str = datetime.fromtimestamp(latest_ts, tz=timezone.utc).strftime("%Y-%m-%d") if latest_ts else "now"
        print(f"Fetching messages from {since_str} → {until_str}...", file=sys.stderr)
    else:
        print(f"Fetching last {limit} root messages...", file=sys.stderr)

    # --- Fetch root messages ---
    all_messages = fetch_root_messages(channel_id, token, limit, oldest_ts, latest_ts)

    if not all_messages:
        print("No messages found for the given channel / date range.")
        return

    print(f"Got {len(all_messages)} root messages. Resolving users...", file=sys.stderr)
    user_map = build_user_map(all_messages, token)

    # Build chronological transcript (API returns newest-first)
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
        text = resolve_mentions(text, user_map)
        output_lines.append(f"[{format_ts(msg.get('ts', ''))}] {author}: {text}")

        for f in msg.get("files", []):
            output_lines.append(f"  [File: {f.get('name', 'unknown')} — {f.get('mimetype', '')}]")
        for a in msg.get("attachments", []):
            title = a.get("title") or a.get("text", "")[:60] or "attachment"
            output_lines.append(f"  [Attachment: {title}]")

        if msg.get("reply_count", 0) > 0:
            thread_lines = fetch_thread_replies(channel_id, msg["ts"], token, user_map)
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
            "Fetch Slack channel history (with thread replies) and print a clean transcript.\n"
            "Supports optional date range filtering via --since / --until."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Last 250 messages (default):
    python3 fetch_history.py C0B9YPS8HDZ

  Last 500 root messages:
    python3 fetch_history.py C0B9YPS8HDZ --limit 500

  Messages from a specific date onwards:
    python3 fetch_history.py C0B9YPS8HDZ --since 2025-01-01

  Messages within a date range:
    python3 fetch_history.py C0B9YPS8HDZ --since 2024-12-01 --until 2025-02-28

  Messages on a single day:
    python3 fetch_history.py C0B9YPS8HDZ --since 2025-06-01 --until 2025-06-01
        """,
    )
    parser.add_argument("channel_id", help="Slack channel ID (e.g. C0B9YPS8HDZ)")
    parser.add_argument(
        "--limit",
        type=int,
        default=250,
        metavar="N",
        help="Max root messages to fetch when no date range is set (default: 250).",
    )
    parser.add_argument(
        "--since",
        metavar="DATE",
        help="Fetch messages on or after this date (UTC). Format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS",
    )
    parser.add_argument(
        "--until",
        metavar="DATE",
        help="Fetch messages on or before this date (UTC). Format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS",
    )
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be a positive integer")

    oldest_ts = parse_date(args.since, end_of_day=False) if args.since else None
    latest_ts = parse_date(args.until, end_of_day=True) if args.until else None

    if oldest_ts and latest_ts and oldest_ts > latest_ts:
        parser.error("--since date must be earlier than --until date")

    fetch_history(args.channel_id, args.limit, oldest_ts, latest_ts)


if __name__ == "__main__":
    main()
