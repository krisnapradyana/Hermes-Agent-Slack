"""
Shared Google OAuth authentication helper for all Google Workspace scripts.
Usage: import from other workspace scripts, don't run directly.
"""

import os
import sys

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar",
]

OAUTH_HELPER_URL = "http://103.49.239.127:8643"


def get_credentials(slack_user_id: str):
    """
    Resolve and return valid Google OAuth credentials for the given Slack user.
    Prefers a per-user token, falls back to the shared token.
    If no token is found, prints an auth prompt and exits.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    user_token_dir = os.path.expanduser("~/.hermes/user_tokens")
    user_token = os.path.join(user_token_dir, f"{slack_user_id}.json")
    shared_token = os.path.expanduser("~/.hermes/google_token.json")

    if os.path.exists(user_token):
        token_file = user_token
    elif os.path.exists(shared_token):
        token_file = shared_token
    else:
        print(
            f"\U0001f517 To use Google Workspace, please connect your Google account first:\n"
            f"\U0001f449 {OAUTH_HELPER_URL}/oauth/start?user={slack_user_id}\n\n"
            f"(Takes ~1 minute. After that, your Docs, Sheets, Slides, and Calendar events\n"
            f"will be created under your own Google account.)"
        )
        sys.exit(0)

    creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return creds
