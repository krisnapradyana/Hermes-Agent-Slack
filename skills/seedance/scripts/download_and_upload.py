"""
download_and_upload.py — Seedance video download + Google Drive upload helper

Cleanup behaviour is driven by config.yaml `cleanup.*` keys:
  on_success      (bool, default True)  — delete temp file after a successful upload
  on_failure      (bool, default False) — delete temp file even if the upload fails
  max_age_seconds (int,  default 3600)  — only relevant for startup sweeps (not used here)

CLI flags can override config values for one-off runs:
  --no-cleanup          never delete the temp file (overrides both on_success + on_failure)
  --cleanup-on-failure  delete temp file even on failure (overrides on_failure from config)
"""

import argparse
import json
import os
import subprocess
import urllib.request
import sys
from pathlib import Path

import uuid

# ── Paths ──────────────────────────────────────────────────────────────────────
VENV_PYTHON     = "/opt/hermes/.venv/bin/python"
GOOGLE_API_SCRIPT = "/opt/hermes/skills/productivity/google-workspace/scripts/google_api.py"
CONFIG_PATH     = "/opt/data/custom-config.yaml"
TEMP_DIR_FALLBACK = "/tmp"

# ── Logging ────────────────────────────────────────────────────────────────────
def log(msg: str) -> None:
    print(f"[GDrive-Helper] {msg}", flush=True)

# ── Config loader ──────────────────────────────────────────────────────────────
def load_cleanup_config() -> dict:
    """Read cleanup settings from config.yaml. Returns safe defaults if missing."""
    defaults = {
        "on_success": True,
        "on_failure": False,
        "on_startup": True,
        "max_age_seconds": 3600,
        "temp_dir": TEMP_DIR_FALLBACK,
        "temp_patterns": ["seedance_*.mp4", "hermes_doc_*.tmp", "hermes_gen_*"],
    }
    try:
        import yaml  # only available inside the container
        cfg_path = Path(CONFIG_PATH)
        if cfg_path.exists():
            raw = yaml.safe_load(cfg_path.read_text()) or {}
            cleanup = raw.get("cleanup", {})
            defaults.update({k: v for k, v in cleanup.items() if v is not None})
    except Exception as e:
        log(f"Warning: could not read cleanup config ({e}). Using defaults.")
    return defaults

# ── Helpers ────────────────────────────────────────────────────────────────────
def download_video(url: str, output_path: str) -> None:
    log("Downloading video from CDN...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        with open(output_path, "wb") as f:
            f.write(r.read())
    size_mb = os.path.getsize(output_path) / 1024 / 1024
    log(f"Download complete: {size_mb:.2f} MB saved to {output_path}")


def run_google_api(args: list) -> dict:
    cmd = [VENV_PYTHON, GOOGLE_API_SCRIPT] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Google API call failed: {result.stderr or result.stdout}")
    return json.loads(result.stdout)


def remove_temp_file(path: str) -> None:
    """Attempt to delete *path*; log a warning on failure but never raise."""
    if os.path.exists(path):
        try:
            os.remove(path)
            log(f"Cleaned up temporary file: {path}")
        except Exception as err:
            log(f"Warning: Failed to delete temporary file {path}: {err}")
    else:
        log(f"Temp file already gone (nothing to clean): {path}")

# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    # ── CLI args ───────────────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(
        description="Download a generated video and upload it to Google Drive."
    )
    parser.add_argument("--url",    required=True,  help="CDN URL of the video")
    parser.add_argument("--folder", default=None,   help="Optional parent folder ID in Google Drive")
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Never delete the temp file, regardless of config settings",
    )
    parser.add_argument(
        "--cleanup-on-failure",
        action="store_true",
        help="Delete the temp file even if upload fails (overrides config on_failure=false)",
    )
    args = parser.parse_args()

    # ── Load config-driven cleanup flags ──────────────────────────────────────
    cfg = load_cleanup_config()
    temp_dir = cfg.get("temp_dir", TEMP_DIR_FALLBACK)

    # CLI overrides
    cleanup_on_success = not args.no_cleanup and cfg["on_success"]
    cleanup_on_failure = (not args.no_cleanup) and (args.cleanup_on_failure or cfg["on_failure"])

    log(f"Cleanup policy → on_success={cleanup_on_success}, on_failure={cleanup_on_failure}")

    temp_file = os.path.join(temp_dir, f"seedance_{uuid.uuid4().hex}.mp4")
    success = False

    try:
        # 1. Download to temporary path
        download_video(args.url, temp_file)

        # 2. Upload to Google Drive
        log("Uploading to Google Drive...")
        upload_args = ["drive", "upload", temp_file]
        if args.folder:
            upload_args += ["--parent", args.folder]

        upload_res = run_google_api(upload_args)
        file_id = upload_res.get("id")
        if not file_id:
            raise RuntimeError(f"Upload succeeded but no file ID returned: {upload_res}")
        log(f"Upload complete. File ID: {file_id}")

        # 3. Share publicly (anyone with link can view)
        log("Setting sharing permissions to public (anyone with link can view)...")
        share_res = run_google_api(
            ["drive", "share", file_id, "--type", "anyone", "--role", "reader"]
        )
        log(f"Sharing complete: {share_res.get('status')}")

        # 4. Fetch shareable link
        log("Retrieving shareable link...")
        get_res = run_google_api(["drive", "get", file_id])
        web_link = get_res.get("webViewLink")
        if not web_link:
            raise RuntimeError(f"Could not retrieve webViewLink for file {file_id}")

        success = True

        # Output final success result
        print("\n" + "=" * 60)
        print("SUCCESS: Video uploaded and shared successfully!")
        print(f"Google Drive Link: {web_link}")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\nERROR: Failed to download/upload video: {e}", file=sys.stderr)
        if cleanup_on_failure:
            remove_temp_file(temp_file)
        else:
            log(f"Temp file kept for inspection (on_failure=false): {temp_file}")
        sys.exit(1)

    finally:
        # Only reach here on the success path (failures sys.exit above)
        if success and cleanup_on_success:
            remove_temp_file(temp_file)
        elif success and not cleanup_on_success:
            log(f"Temp file kept (on_success=false): {temp_file}")


if __name__ == "__main__":
    main()
