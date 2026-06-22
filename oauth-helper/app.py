"""
app.py — Google OAuth2 Web Helper for Hermes Agent (Multi-User)

Per-Slack-user Google authorization. Each user's token is stored as:
  /documents/user_tokens/{slack_user_id}.json

The shared admin token at /documents/token.json is kept for backward compatibility
and used as fallback when a user hasn't connected their own account.

Auth flow (paste-based, works for any remote user without a domain name):
  1. Hermes posts auth URL in Slack: http://<ip>:8643/oauth/start?user=UXXXXXXX
  2. User opens URL → Google sign-in page
  3. After sign-in, Google redirects to http://localhost (fails in browser)
  4. User copies the full URL from address bar
  5. User pastes it at /oauth/paste
  6. Flask extracts code, exchanges for token server-side → saved per user
"""

import os
import re
import json
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlunparse

from flask import Flask, redirect, render_template, request, session, url_for
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

# ── Config ────────────────────────────────────────────────────────────────────
CLIENT_SECRETS_FILE = "/documents/google_client_secret.json"
TOKEN_FILE          = "/documents/token.json"           # shared / admin token
USER_TOKEN_DIR      = "/documents/user_tokens"          # per-user tokens

LOOPBACK_REDIRECT_URI = "http://localhost"

# Relax token scope matching to allow Google to return different (e.g. more) scopes
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

PUBLIC_URL = os.environ.get("OAUTH_PUBLIC_URL", "").rstrip("/")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "hermes-oauth-helper-default-secret")


# ── Helpers ───────────────────────────────────────────────────────────────────
_SAFE_USER_ID = re.compile(r'^[A-Za-z0-9_\-]{1,64}$')


def sanitize_user_id(user_id: str | None) -> str | None:
    """Validate Slack-style user IDs. Returns None if invalid."""
    if not user_id:
        return None
    return user_id if _SAFE_USER_ID.match(user_id) else None


def get_token_file(user_id: str | None = None) -> str:
    """Return the token file path for a user (or shared token if no user_id)."""
    if user_id:
        os.makedirs(USER_TOKEN_DIR, exist_ok=True)
        return os.path.join(USER_TOKEN_DIR, f"{user_id}.json")
    return TOKEN_FILE


def check_token(token_path: str) -> dict:
    """Check a single token file. Returns status dict."""
    if not os.path.exists(token_path):
        return {"connected": False, "reason": "No token found", "expiry": None}
    try:
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if creds.valid:
            return {"connected": True, "reason": None, "expiry": str(creds.expiry)}
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "w") as f:
                f.write(creds.to_json())
            return {"connected": True, "reason": None, "expiry": str(creds.expiry)}
        return {"connected": False, "reason": "Token expired — please reconnect", "expiry": None}
    except Exception as e:
        return {"connected": False, "reason": str(e), "expiry": None}


def get_connection_status(user_id: str | None = None) -> dict:
    return check_token(get_token_file(user_id))


def list_all_users() -> list[dict]:
    """Return status for all connected users."""
    users = []
    if os.path.exists(USER_TOKEN_DIR):
        for f in sorted(Path(USER_TOKEN_DIR).glob("*.json")):
            user_id = f.stem
            status = check_token(str(f))
            users.append({"user_id": user_id, **status})
    return users


def display_url() -> str:
    return PUBLIC_URL or request.host_url.rstrip("/")


def make_auth_url_for(user_id: str | None) -> tuple[str, str]:
    """Generate (auth_url, state) for a given user_id."""
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=LOOPBACK_REDIRECT_URI,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url, state


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    """Admin dashboard — shows all connected users and shared token status."""
    secrets_missing = not os.path.exists(CLIENT_SECRETS_FILE)
    shared_status   = get_connection_status(None)       # shared/admin token
    users           = list_all_users()
    return render_template(
        "index.html",
        secrets_missing=secrets_missing,
        shared_status=shared_status,
        users=users,
        public_url=display_url(),
    )


@app.route("/oauth/start")
def oauth_start():
    """Start OAuth flow for a user.

    ?user=UXXXXXXX  → per-user token (saved to user_tokens/{user_id}.json)
    (no param)      → shared/admin token (saved to token.json)
    """
    if not os.path.exists(CLIENT_SECRETS_FILE):
        return render_template("error.html",
                               message="google_client_secret.json not found.")

    user_id = sanitize_user_id(request.args.get("user"))
    auth_url, state = make_auth_url_for(user_id)

    session["oauth_state"]   = state
    session["oauth_user_id"] = user_id  # None for shared flow

    return render_template(
        "authorize.html",
        auth_url=auth_url,
        user_id=user_id,
        public_url=display_url(),
    )


@app.route("/oauth/paste", methods=["GET", "POST"])
def oauth_paste():
    """Show (GET) or process (POST) the paste-URL step."""
    # User ID can come from session (set in oauth_start) or query param
    user_id = sanitize_user_id(
        session.get("oauth_user_id") or request.args.get("user") or request.form.get("user_id")
    )

    if request.method == "GET":
        return render_template("paste.html", user_id=user_id, public_url=display_url())

    pasted = request.form.get("redirect_url", "").strip()
    if not pasted:
        return render_template("paste.html", user_id=user_id, public_url=display_url(),
                               error="Please paste the URL from your browser's address bar.")

    try:
        parsed = urlparse(pasted)
        params = parse_qs(parsed.query)
    except Exception:
        return render_template("paste.html", user_id=user_id, public_url=display_url(),
                               error="That doesn't look like a valid URL.")

    if "error" in params:
        return render_template("error.html",
                               message=f"Google returned an error: {params['error'][0]}")

    code  = params.get("code",  [None])[0]
    state = params.get("state", [None])[0]

    if not code:
        return render_template("paste.html", user_id=user_id, public_url=display_url(),
                               error="No authorization code found. Copy the full address bar URL.")

    stored_state = session.get("oauth_state")
    if stored_state and state and stored_state != state:
        return render_template("error.html", message="State mismatch — please start over.")

    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            state=state or stored_state,
            redirect_uri=LOOPBACK_REDIRECT_URI,
        )

        loopback = urlparse(LOOPBACK_REDIRECT_URI)
        auth_response = urlunparse((
            loopback.scheme, loopback.netloc,
            parsed.path or "/", "",
            parsed.query, "",
        ))

        flow.fetch_token(authorization_response=auth_response)
        credentials = flow.credentials

        token_path = get_token_file(user_id)
        with open(token_path, "w") as f:
            f.write(credentials.to_json())

        session.pop("oauth_state",   None)
        session.pop("oauth_user_id", None)
        return render_template("success.html", user_id=user_id)

    except Exception as e:
        return render_template("error.html", message=str(e))


@app.route("/oauth/disconnect")
def oauth_disconnect():
    """Remove a user's token.

    ?user=UXXXXXXX  → remove that user's token
    (no param)      → remove shared token
    """
    user_id    = sanitize_user_id(request.args.get("user"))
    token_path = get_token_file(user_id)
    if os.path.exists(token_path):
        os.remove(token_path)
    return redirect(url_for("index"))


@app.route("/status")
def status():
    """JSON health endpoint. ?user=UXXXXXXX for per-user status."""
    user_id = sanitize_user_id(request.args.get("user"))
    s = get_connection_status(user_id)
    s["user_id"]      = user_id or "shared"
    s["helper_url"]   = display_url()
    s["redirect_uri"] = LOOPBACK_REDIRECT_URI
    return s

@app.route("/users")
def users_json():
    """JSON list of all connected users and their status."""
    return {"users": list_all_users()}


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8643, debug=False)
