"""
app.py — Google OAuth2 Web Helper for Hermes Agent

Serves a simple web UI at http://localhost:8643 so a non-technical admin
can authorize Google Drive access with one click. Saves token.json to the
shared /documents volume which the hermes container also mounts.
"""

import json
import os

from flask import Flask, redirect, render_template, request, session, url_for
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

# ── Config ─────────────────────────────────────────────────────────────────────
CLIENT_SECRETS_FILE = "/documents/google_client_secret.json"
TOKEN_FILE          = "/documents/token.json"
REDIRECT_URI        = "http://localhost:8643/oauth/callback"
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
]

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "hermes-oauth-helper-default-secret")


# ── Helpers ────────────────────────────────────────────────────────────────────
def get_connection_status() -> dict:
    """Check if token.json exists and is still valid (not expired)."""
    if not os.path.exists(TOKEN_FILE):
        return {"connected": False, "email": None, "reason": "No token found"}

    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds.valid:
            return {"connected": True, "email": None, "reason": None}
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed token
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
            return {"connected": True, "email": None, "reason": None}
        return {"connected": False, "email": None, "reason": "Token expired — please reconnect"}
    except Exception as e:
        return {"connected": False, "email": None, "reason": str(e)}


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    status = get_connection_status()
    secrets_missing = not os.path.exists(CLIENT_SECRETS_FILE)
    return render_template(
        "index.html",
        connected=status["connected"],
        reason=status["reason"],
        secrets_missing=secrets_missing,
    )


@app.route("/oauth/start")
def oauth_start():
    if not os.path.exists(CLIENT_SECRETS_FILE):
        return render_template(
            "error.html",
            message="google_client_secret.json not found in /documents. "
                    "Please make sure the file is mounted correctly.",
        )

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",          # Forces refresh_token to always be returned
    )
    session["oauth_state"] = state
    return redirect(auth_url)


@app.route("/oauth/callback")
def oauth_callback():
    # Error returned by Google (e.g. user cancelled)
    if "error" in request.args:
        error = request.args.get("error", "Unknown error")
        return render_template("error.html", message=f"Google returned an error: {error}")

    state = session.get("oauth_state")
    if not state:
        return render_template(
            "error.html",
            message="Session state missing. Please try connecting again — "
                    "this can happen if cookies are blocked or the session expired.",
        )

    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            state=state,
            redirect_uri=REDIRECT_URI,
        )
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials

        # Persist token to shared volume
        with open(TOKEN_FILE, "w") as f:
            f.write(credentials.to_json())

        session.pop("oauth_state", None)
        return render_template("success.html")

    except Exception as e:
        return render_template("error.html", message=str(e))


@app.route("/oauth/disconnect")
def oauth_disconnect():
    """Remove the saved token so the admin can re-authorize."""
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
    return redirect(url_for("index"))


@app.route("/status")
def status():
    """JSON health endpoint for quick checks."""
    s = get_connection_status()
    return s


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8643, debug=False)
