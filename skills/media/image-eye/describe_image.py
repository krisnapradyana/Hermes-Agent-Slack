"""
describe_image.py — Hermes's eye for LOCAL image files
=======================================================
Sends an image from disk to the Anthropic API (auxiliary vision model) and
prints a detailed description / transcription, optionally answering a
specific question about it. Zero external dependencies (stdlib + curl).

Usage:
    python3 describe_image.py <image_path> [question ...]

Examples:
    python3 describe_image.py /tmp/hermes_gen_slackfile_1_shot.png
    python3 describe_image.py /tmp/x.png what deadline is shown in this screenshot

Key resolution: ANTHROPIC_API_KEY env var, else /opt/data/custom-.env.
Model: HERMES_EYE_MODEL env var, default claude-haiku-4-5 (cheap, vision).
"""

import base64
import json
import os
import subprocess
import sys
import tempfile

MAX_BYTES = 4_800_000  # stay under the API's ~5MB per-image limit

MEDIA_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}


def get_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    try:
        with open("/opt/data/custom-.env") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if key:
                        return key
    except FileNotFoundError:
        pass
    print("Error: ANTHROPIC_API_KEY not found in env or /opt/data/custom-.env", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: describe_image.py <image_path> [question ...]", file=sys.stderr)
        sys.exit(1)
    path = sys.argv[1]
    question = " ".join(sys.argv[2:]).strip() or (
        "Describe this image in detail. Transcribe any visible text verbatim. "
        "If it is a screenshot of an app or chat, say which app it looks like "
        "and what is happening in it."
    )

    ext = path.rsplit(".", 1)[-1].lower()
    media = MEDIA_TYPES.get(ext)
    if not media:
        print(f"Error: unsupported image type .{ext} (supported: {', '.join(MEDIA_TYPES)})", file=sys.stderr)
        sys.exit(1)
    try:
        raw = open(path, "rb").read()
    except OSError as e:
        print(f"Error: cannot read {path}: {e}", file=sys.stderr)
        sys.exit(1)
    if len(raw) == 0:
        print(f"Error: {path} is empty", file=sys.stderr)
        sys.exit(1)
    if len(raw) > MAX_BYTES:
        print(
            f"Error: image is {len(raw)/1e6:.1f}MB (limit ~4.8MB). "
            "Ask the user for a smaller version, or skip this image.",
            file=sys.stderr,
        )
        sys.exit(1)

    body = {
        "model": os.environ.get("HERMES_EYE_MODEL", "claude-haiku-4-5"),
        "max_tokens": 1200,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media,
                            "data": base64.b64encode(raw).decode(),
                        },
                    },
                    {"type": "text", "text": question},
                ],
            }
        ],
    }

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        json.dump(body, tf)
        payload = tf.name
    try:
        r = subprocess.run(
            [
                "curl", "-s", "https://api.anthropic.com/v1/messages",
                "-H", f"x-api-key: {get_key()}",
                "-H", "anthropic-version: 2023-06-01",
                "-H", "content-type: application/json",
                "-d", f"@{payload}",
                "--max-time", "90",
            ],
            capture_output=True,
            text=True,
        )
    finally:
        try:
            os.unlink(payload)
        except OSError:
            pass

    if r.returncode != 0:
        print(f"curl error: {r.stderr}", file=sys.stderr)
        sys.exit(1)
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        print(f"Unparseable API response: {r.stdout[:500]}", file=sys.stderr)
        sys.exit(1)
    if data.get("type") == "error":
        print(f"API error: {data.get('error', {}).get('message', 'unknown')}", file=sys.stderr)
        sys.exit(1)

    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    print(f"--- IMAGE DESCRIPTION ({os.path.basename(path)}) ---")
    print(text.strip() or "(model returned no text)")
    print("--- END OF DESCRIPTION ---")


if __name__ == "__main__":
    main()
