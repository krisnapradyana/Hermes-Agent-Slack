"""
token_refresher.py — Background token keepalive for Hermes

Runs as a daemon inside the oauth-helper container.
Refreshes /documents/token.json every 12 hours so the access token
never goes stale between Slack interactions.
"""

import json
import logging
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

TOKEN_FILE = "/documents/token.json"
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]

REFRESH_INTERVAL_SECONDS = 12 * 60 * 60  # 12 hours

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [token-refresher] %(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)


def refresh_once() -> bool:
    """Attempt a single token refresh. Returns True on success."""
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not creds.refresh_token:
            log.warning("No refresh_token in token.json — cannot auto-refresh. Re-authorize via the OAuth helper.")
            return False

        # Refresh even if the token is still valid, so we always have a fresh one
        creds.refresh(Request())

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

        log.info("Token refreshed successfully. New expiry: %s", creds.expiry)
        return True

    except FileNotFoundError:
        log.warning("token.json not found at %s — skipping refresh (not yet authorized).", TOKEN_FILE)
        return False
    except Exception as e:
        log.error("Token refresh failed: %s", e)
        return False


def main():
    log.info("Token refresher started. Refresh interval: %dh", REFRESH_INTERVAL_SECONDS // 3600)

    while True:
        refresh_once()
        log.info("Next refresh in %d hours.", REFRESH_INTERVAL_SECONDS // 3600)
        time.sleep(REFRESH_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
