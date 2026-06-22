"""
fetch_history.py — Slack channel history fetcher for Hermes
============================================================
Fetches the last N messages from a Slack channel and prints a clean,
chronological transcript to stdout. Uses slack-sdk WebClient.

Usage:
    python3 fetch_history.py <CHANNEL_ID> [--limit N]

Arguments:
    CHANNEL_ID   Slack channel ID (e.g. C0B9YPS8HDZ)
    --limit N    Number of messages to fetch (default: 250, max per page: 1000)

Environment:
    SLACK_BOT_TOKEN   Required. Bot token with channels:history + users:read scopes.
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
    if not user_id or user_id.startswith("B"):  # Bot IDs start with B
        return f"Bot({user_id})"

    if user_id in _user_cache:
        return _user_cache[user_id]

    try:
        resp = client.users_info(user=user_id)
        profile = resp["user"]["profile"]
        # Prefer display_name, fall back to real_name, then the raw ID
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
# History Fetcher
# ---------------------------------------------------------------------------

def fetch_history(channel_id: str, limit: int = 250) -> None:
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        print("Error: SLACK_BOT_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    client = WebClient(token=token)
    messages: list[dict] = []

    try:
        # Slack's API returns max 1000 per page. Paginate if limit > 1000.
        remaining = limit
        cursor = None

        while remaining > 0:
            batch_size = min(remaining, 1000)
            kwargs: dict = {
                "channel": channel_id,
                "limit": batch_size,
            }
            if cursor:
                kwargs["cursor"] = cursor

            resp = client.conversations_history(**kwargs)

            if not resp.get("ok"):
                print(f"Error fetching history: {resp.get('error')}", file=sys.stderr)
                if resp.get("error") == "missing_scope":
                    print(
                        "The Slack app requires 'channels:history' and/or 'groups:history' scopes.",
                        file=sys.stderr,
                    )
                sys.exit(1)

            batch = resp.get("messages", [])
            messages.extend(batch)
            remaining -= len(batch)

            next_cursor = resp.get("response_metadata", {}).get("next_cursor", "")
            if not next_cursor or len(batch) < batch_size:
                break  # No more pages
            cursor = next_cursor

    except SlackApiError as e:
        error = e.response.get("error", str(e))
        print(f"Slack API error: {error}", file=sys.stderr)
        if error == "channel_not_found":
            print("Check that the bot is a member of the channel.", file=sys.stderr)
        sys.exit(1)

    if not messages:
        print("No messages found in this channel.")
        return

    # Build chronological transcript (API returns newest-first)
    lines: list[str] = []
    for msg in reversed(messages):
        # Skip system events with no readable text
        subtype = msg.get("subtype", "")
        text = msg.get("text", "").strip()
        if not text or subtype in ("channel_join", "channel_leave", "channel_purpose", "channel_topic"):
            continue

        ts = float(msg.get("ts", 0))
        time_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")

        # Resolve author: prefer username, then bot_id, then user ID
        user_id = msg.get("user") or msg.get("bot_id", "UnknownUser")
        author = resolve_user(client, user_id) if msg.get("user") else f"Bot({user_id})"

        lines.append(f"[{time_str}] {author}: {text}")

    actual = len(lines)
    print(f"--- CHANNEL HISTORY (last {actual} messages) ---")
    print("\n".join(lines))
    print("--- END OF HISTORY ---")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Slack channel history and print a clean transcript."
    )
    parser.add_argument("channel_id", help="Slack channel ID (e.g. C0B9YPS8HDZ)")
    parser.add_argument(
        "--limit",
        type=int,
        default=250,
        metavar="N",
        help="Number of messages to fetch (default: 250)",
    )
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be a positive integer")

    fetch_history(args.channel_id, args.limit)


if __name__ == "__main__":
    main()
