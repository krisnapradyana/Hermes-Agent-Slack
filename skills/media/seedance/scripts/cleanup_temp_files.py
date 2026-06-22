"""
cleanup_temp_files.py — Startup / on-demand sweep of stale generated temp files.

Run automatically by the Hermes container entrypoint when cleanup.on_startup=true.
Can also be called manually:

  python /opt/data/custom-skills/media/seedance/scripts/cleanup_temp_files.py [--dry-run]

Reads settings from config.yaml (cleanup section):
  on_startup      (bool) — if false, this script exits immediately without doing anything
  temp_dir        (str)  — directory to scan
  temp_patterns   (list) — glob patterns for files to consider
  max_age_seconds (int)  — files older than this are deleted
"""

import argparse
import glob
import os
import sys
import time
from pathlib import Path

# ── Config loader ──────────────────────────────────────────────────────────────
CONFIG_PATHS = [
    "/opt/data/config.yaml",          # merged runtime config (inside container)
    "/opt/data/custom-config.yaml",   # host-mounted override
]

DEFAULTS = {
    "on_startup":      True,
    "temp_dir":        "/tmp",
    "temp_patterns":   ["seedance_*.*", "hermes_doc_*.tmp", "hermes_gen_*"],
    "max_age_seconds": 3600,
}


def log(msg: str) -> None:
    print(f"[Cleanup] {msg}", flush=True)


def load_cleanup_config() -> dict:
    cfg = dict(DEFAULTS)
    try:
        import yaml
        for path in CONFIG_PATHS:
            p = Path(path)
            if p.exists():
                raw = yaml.safe_load(p.read_text()) or {}
                cleanup = raw.get("cleanup", {})
                cfg.update({k: v for k, v in cleanup.items() if v is not None})
    except Exception as e:
        log(f"Warning: could not load config ({e}). Using defaults.")
    return cfg


# ── Core sweep ─────────────────────────────────────────────────────────────────
def sweep(cfg: dict, dry_run: bool = False) -> tuple[int, int]:
    """
    Scan temp_dir for files matching temp_patterns that are older than
    max_age_seconds. Delete them (unless dry_run).

    Returns (found, deleted) counts.
    """
    temp_dir    = cfg["temp_dir"]
    patterns    = cfg["temp_patterns"]
    max_age     = cfg["max_age_seconds"]
    now         = time.time()
    found       = 0
    deleted     = 0

    log(f"Scanning '{temp_dir}' for files matching {patterns} older than {max_age}s...")

    for pattern in patterns:
        full_pattern = os.path.join(temp_dir, pattern)
        for filepath in glob.glob(full_pattern):
            found += 1
            try:
                age = now - os.path.getmtime(filepath)
                size_mb = os.path.getsize(filepath) / 1024 / 1024
                if age >= max_age:
                    if dry_run:
                        log(f"  [DRY-RUN] Would delete: {filepath}  ({size_mb:.2f} MB, age {age:.0f}s)")
                    else:
                        os.remove(filepath)
                        log(f"  Deleted: {filepath}  ({size_mb:.2f} MB, age {age:.0f}s)")
                    deleted += 1
                else:
                    log(f"  Skipping (too recent, age {age:.0f}s < {max_age}s): {filepath}")
            except Exception as e:
                log(f"  Warning: could not process {filepath}: {e}")

    return found, deleted


# ── Entry point ────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sweep and remove stale temporary generated files."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files that would be deleted without actually removing them.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even if cleanup.on_startup is set to false in config.",
    )
    args = parser.parse_args()

    cfg = load_cleanup_config()

    if not cfg["on_startup"] and not args.force:
        log("cleanup.on_startup is false — skipping sweep. Use --force to override.")
        sys.exit(0)

    found, deleted = sweep(cfg, dry_run=args.dry_run)

    action = "would be deleted" if args.dry_run else "deleted"
    log(f"Sweep complete: {found} file(s) found, {deleted} {action}.")


if __name__ == "__main__":
    main()
