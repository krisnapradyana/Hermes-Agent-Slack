"""
token_refresher.py — Background token keepalive for Hermes (Multi-User)

Runs as a daemon inside the oauth-helper container.
Refreshes ALL token files every 12 hours:
  - /documents/token.json          (shared/admin token)
  - /documents/user_tokens/*.json  (per-user tokens)
"""

import logging
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

TOKEN_FILE     = Path("/documents/token.json")
USER_TOKEN_DIR = Path("/documents/user_tokens")

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar",
]

REFRESH_INTERVAL_SECONDS = 12 * 60 * 60  # 12 hours

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [token-refresher] %(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)


def refresh_once(token_path: Path) -> bool:
    """Attempt a single token refresh. Returns True on success."""
    label = token_path.name
    try:
        if not token_path.exists():
            return False  # not yet authorized — silent skip

        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds.refresh_token:
            log.warning("[%s] No refresh_token — cannot auto-refresh.", label)
            return False

        creds.refresh(Request())

        with open(token_path, "w") as f:
            f.write(creds.to_json())

        log.info("[%s] Refreshed. New expiry: %s", label, creds.expiry)
        return True

    except FileNotFoundError:
        return False
    except Exception as e:
        log.error("[%s] Refresh failed: %s", label, e)
        return False


def refresh_all() -> None:
    """Refresh the shared token and every user token."""
    # Shared / admin token
    refresh_once(TOKEN_FILE)

    # Per-user tokens
    if USER_TOKEN_DIR.exists():
        user_files = list(USER_TOKEN_DIR.glob("*.json"))
        if user_files:
            log.info("Refreshing %d user token(s)...", len(user_files))
            for f in user_files:
                refresh_once(f)
    else:
        # Create the directory so it's ready when users start connecting
        USER_TOKEN_DIR.mkdir(parents=True, exist_ok=True)


def main():
    log.info("Token refresher started. Interval: %dh", REFRESH_INTERVAL_SECONDS // 3600)
    while True:
        refresh_all()
        log.info("Next refresh in %dh.", REFRESH_INTERVAL_SECONDS // 3600)
        time.sleep(REFRESH_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
