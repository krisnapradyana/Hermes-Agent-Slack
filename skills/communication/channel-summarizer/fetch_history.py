"""
fetch_history.py — Slack channel history fetcher for Hermes
============================================================
Zero external dependencies. Uses curl (always available in the container)
via subprocess. Fetches root messages + all thread replies, with optional
date range filtering.

Usage:
    python3 fetch_history.py <CHANNEL_ID> [--limit N] [--since DATE] [--until DATE]
                             [--thread TS] [--download-images [N]]

Arguments:
    CHANNEL_ID      Slack channel ID (e.g. C0B9YPS8HDZ)
    --limit N       Max root messages to fetch (default: 250; ignored when date range is set)
    --since DATE    Fetch messages on or after this date/datetime (UTC)
    --until DATE    Fetch messages on or before this date/datetime (UTC)
    --thread TS     Fetch ONE thread only (TS = the thread root's Slack timestamp,
                    e.g. 1759640000.123456). Ignores --limit/--since/--until.
    --download-images [N]
                    Also download the newest N image attachments (default 5) to
                    /tmp/hermes_gen_slackimg_* and list their local paths, so a
                    vision-capable agent can open them.
    --download-files [N]
                    Like --download-images but for ALL attachment types (PDF,
                    DOCX, TXT, CSV, images, ...). Documents can then be read
                    with the document-reader skill's extraction snippet.
    --list-channels List every channel the bot is a member of (id + name),
                    for workspace-wide summaries. No CHANNEL_ID needed: pass
                    "-" as the channel id.

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
import re
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
# Image Attachments
# ---------------------------------------------------------------------------

# (ts, author, file_object) for every attachment seen while formatting.
ImgRef = tuple  # (str, str, dict)

IMG_DIR = "/tmp"
# Prefix rides the agent's existing cleanup sweep (temp_patterns: hermes_gen_*).
IMG_PREFIX = "hermes_gen_slackfile"


def collect_images(msg: dict, author: str, sink: list | None) -> None:
    """Remember ALL attachments on a message for optional download later."""
    if sink is None:
        return
    for f in msg.get("files", []):
        sink.append((msg.get("ts", ""), author, f))


def download_images(atts: list, token: str, max_n: int, images_only: bool) -> list[str]:
    """
    Download the NEWEST max_n attachments with the bot token (requires the
    files:read scope). images_only restricts to image/* mimetypes.
    Returns printable result lines.
    """
    lines: list[str] = []
    pool = [a for a in atts if not images_only or (a[2].get("mimetype") or "").startswith("image/")]
    newest = sorted(pool, key=lambda x: x[0])[-max_n:]
    for i, (ts, author, f) in enumerate(newest, 1):
        url = f.get("url_private_download") or f.get("url_private")
        name = re.sub(r"[^\w.-]+", "_", f.get("name") or f"file{i}")
        if not url:
            lines.append(f"[{format_ts(ts)}] {author}: {name} — no downloadable URL")
            continue
        path = os.path.join(IMG_DIR, f"{IMG_PREFIX}_{i}_{name}")
        r = subprocess.run(
            ["curl", "-s", "-L", "-o", path, url, "-H", f"Authorization: Bearer {token}"],
            capture_output=True,
            text=True,
        )
        ok = r.returncode == 0 and os.path.exists(path) and os.path.getsize(path) > 0
        if ok:
            # Slack serves an HTML page instead of bytes when the token lacks
            # files:read — detect it so the agent never "views" an error page.
            with open(path, "rb") as fh:
                head = fh.read(64).lstrip()
            if head.startswith(b"<") :
                os.unlink(path)
                lines.append(
                    f"[{format_ts(ts)}] {author}: {name} — download refused "
                    "(bot token likely missing the files:read scope)"
                )
                continue
            lines.append(f"[{format_ts(ts)}] {author}: {path} (original: {f.get('name')})")
        else:
            lines.append(f"[{format_ts(ts)}] {author}: {name} — download failed")
    return lines


# ---------------------------------------------------------------------------
# Thread Reply Fetcher
# ---------------------------------------------------------------------------

def fetch_thread_replies(
    channel_id: str,
    thread_ts: str,
    token: str,
    user_map: dict[str, str],
    images: list | None = None,
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
        collect_images(reply, author, images)

    return lines


# ---------------------------------------------------------------------------
# Single-Thread Mode
# ---------------------------------------------------------------------------

def fetch_thread(channel_id: str, thread_ts: str, download_imgs: int, images_only: bool = True) -> None:
    """Print ONE thread (root + every reply) as a chronological transcript."""
    token = get_token()
    print(f"Fetching thread {thread_ts}...", file=sys.stderr)

    url = (
        f"https://slack.com/api/conversations.replies"
        f"?channel={channel_id}&ts={thread_ts}&limit=1000"
    )
    data = slack_get(url, token)
    if not data.get("ok"):
        error = data.get("error", "unknown_error")
        print(f"Error fetching thread: {error}", file=sys.stderr)
        if error == "thread_not_found":
            print("Check the thread timestamp — it must be the ROOT message's ts.", file=sys.stderr)
        sys.exit(1)
    messages = data.get("messages", [])
    while data.get("has_more"):
        cursor = data.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
        data = slack_get(url + f"&cursor={cursor}", token)
        messages.extend(data.get("messages", []))

    if not messages:
        print("Thread is empty or not found.")
        return

    user_map = build_user_map(messages, token)
    images: list | None = [] if download_imgs > 0 else None
    out: list[str] = []
    for i, msg in enumerate(messages):
        subtype = msg.get("subtype", "")
        text = msg.get("text", "").strip()
        if subtype in _SKIP_SUBTYPES:
            continue
        uid = msg.get("user") or msg.get("bot_id", "")
        author = user_map.get(uid, uid or "Bot")
        text = resolve_mentions(text, user_map)
        prefix = "" if i == 0 else "    ↳ "
        if text or msg.get("files"):
            out.append(f"{prefix}[{format_ts(msg.get('ts', ''))}] {author}: {text}")
        for f in msg.get("files", []):
            out.append(f"{prefix}  [File: {f.get('name', 'unknown')} — {f.get('mimetype', '')}]")
        collect_images(msg, author, images)

    print(f"--- THREAD ({len(messages)} messages, root first) ---")
    print("\n".join(out))
    print("--- END OF THREAD ---")
    if images is not None:
        print_image_section(images, token, download_imgs, images_only)


def print_image_section(atts: list, token: str, max_n: int, images_only: bool) -> None:
    kind = "IMAGE" if images_only else "FILE"
    pool = [a for a in atts if not images_only or (a[2].get("mimetype") or "").startswith("image/")]
    if not pool:
        print(f"--- NO {kind} ATTACHMENTS FOUND ---")
        return
    lines = download_images(atts, token, max_n, images_only)
    print(f"--- {kind}S SAVED (newest {min(max_n, len(pool))} of {len(pool)}) ---")
    print("\n".join(lines))
    print(
        f"--- END OF {kind}S — view images directly; extract PDF/DOCX text "
        "with the document-reader skill's snippet ---"
    )


# ---------------------------------------------------------------------------
# Channel Listing (for workspace-wide summaries)
# ---------------------------------------------------------------------------

def list_channels() -> None:
    """Print every channel the bot is a member of: '<id>\t#<name>'."""
    token = get_token()
    url = (
        "https://slack.com/api/users.conversations"
        "?types=public_channel,private_channel&limit=200&exclude_archived=true"
    )
    cursor = ""
    count = 0
    while True:
        data = slack_get(url + (f"&cursor={cursor}" if cursor else ""), token)
        if not data.get("ok"):
            print(f"Error listing channels: {data.get('error', 'unknown')}", file=sys.stderr)
            sys.exit(1)
        for ch in data.get("channels", []):
            print(f"{ch.get('id')}\t#{ch.get('name')}")
            count += 1
        cursor = data.get("response_metadata", {}).get("next_cursor", "")
        if not cursor:
            break
    print(f"--- {count} channels (bot is a member) ---", file=sys.stderr)


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
    download_imgs: int = 0,
    images_only: bool = True,
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
    images: list | None = [] if download_imgs > 0 else None
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
        collect_images(msg, author, images)
        for a in msg.get("attachments", []):
            title = a.get("title") or a.get("text", "")[:60] or "attachment"
            output_lines.append(f"  [Attachment: {title}]")

        if msg.get("reply_count", 0) > 0:
            thread_lines = fetch_thread_replies(channel_id, msg["ts"], token, user_map, images)
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
    if images is not None:
        print_image_section(images, token, download_imgs, images_only)


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
    parser.add_argument(
        "--thread",
        metavar="TS",
        help="Fetch ONE thread only — TS is the thread ROOT message's Slack timestamp.",
    )
    parser.add_argument(
        "--download-images",
        nargs="?",
        const=5,
        default=0,
        type=int,
        metavar="N",
        help="Also download the newest N image attachments (default 5 when flag given) "
        "to /tmp for viewing.",
    )
    parser.add_argument(
        "--download-files",
        nargs="?",
        const=5,
        default=0,
        type=int,
        metavar="N",
        help="Like --download-images but for ALL attachment types (PDF, DOCX, ...).",
    )
    parser.add_argument(
        "--list-channels",
        action="store_true",
        help="List channels the bot is a member of, then exit (channel id arg ignored).",
    )
    args = parser.parse_args()

    if args.list_channels:
        list_channels()
        return

    if args.limit < 1:
        parser.error("--limit must be a positive integer")
    for v in (args.download_images, args.download_files):
        if v < 0 or v > 20:
            parser.error("--download-images/--download-files must be between 0 and 20")
    dl_n = args.download_files or args.download_images
    images_only = args.download_files == 0

    if args.thread:
        fetch_thread(args.channel_id, args.thread, dl_n, images_only)
        return

    oldest_ts = parse_date(args.since, end_of_day=False) if args.since else None
    latest_ts = parse_date(args.until, end_of_day=True) if args.until else None

    if oldest_ts and latest_ts and oldest_ts > latest_ts:
        parser.error("--since date must be earlier than --until date")

    fetch_history(args.channel_id, args.limit, oldest_ts, latest_ts, dl_n, images_only)


if __name__ == "__main__":
    main()
