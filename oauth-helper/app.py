"""
app.py — Google OAuth2 Web Helper for Hermes Agent

Serves a simple web UI at http://<server>:8643 so a non-technical admin
can authorize Google Drive access in two clicks — no domain name required.

Flow (works for any remote user without a public domain):
  1. User clicks "Connect Google Account" → Flask generates a Google auth URL
     with redirect_uri=http://localhost (allowed for "Desktop app" client type).
  2. User's browser is redirected to Google sign-in.
  3. After sign-in, Google redirects to http://localhost/?code=...&state=...
     This fails in the browser (nothing on localhost:80), but the URL bar
     shows the full URL with the authorization code.
  4. The UI shows a paste box. User copies that URL from address bar, pastes it.
  5. Flask extracts code+state, exchanges server-side → saves token.json.
"""

import os
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from flask import Flask, redirect, render_template, request, session, url_for
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

# ── Config ────────────────────────────────────────────────────────────────────
CLIENT_SECRETS_FILE = "/documents/google_client_secret.json"
TOKEN_FILE          = "/documents/token.json"

# The redirect_uri we tell Google to send the user to after sign-in.
# We use http://localhost because Google ALWAYS allows it for "Desktop app"
# (installed) client types — no domain registration needed.
# After the redirect fails in the browser, the user copies the URL and pastes
# it into the helper UI (Step 4 above), where we process it server-side.
LOOPBACK_REDIRECT_URI = "http://localhost"

SCOPES = [
    # Google Drive
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    # Google Docs
    "https://www.googleapis.com/auth/documents",
    # Google Slides
    "https://www.googleapis.com/auth/presentations",
    # Google Sheets
    "https://www.googleapis.com/auth/spreadsheets",
    # Google Calendar
    "https://www.googleapis.com/auth/calendar",
]

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "hermes-oauth-helper-default-secret")

# Public-facing URL of this helper — used only for display purposes.
PUBLIC_URL = os.environ.get("OAUTH_PUBLIC_URL", "").rstrip("/")


# ── Helpers ───────────────────────────────────────────────────────────────────
def get_connection_status() -> dict:
    """Check if token.json exists and is still valid (or refreshable)."""
    if not os.path.exists(TOKEN_FILE):
        return {"connected": False, "email": None, "reason": "No token found"}

    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds.valid:
            return {"connected": True, "email": None, "reason": None}
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
            return {"connected": True, "email": None, "reason": None}
        return {"connected": False, "email": None, "reason": "Token expired — please reconnect"}
    except Exception as e:
        return {"connected": False, "email": None, "reason": str(e)}


def display_url() -> str:
    """Best-effort public URL for display in templates."""
    return PUBLIC_URL or request.host_url.rstrip("/")


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    status = get_connection_status()
    secrets_missing = not os.path.exists(CLIENT_SECRETS_FILE)
    return render_template(
        "index.html",
        connected=status["connected"],
        reason=status["reason"],
        secrets_missing=secrets_missing,
        public_url=display_url(),
    )


@app.route("/oauth/start")
def oauth_start():
    """Generate Google auth URL and redirect the user to it.

    We pass redirect_uri=http://localhost — Google allows this for Desktop/installed
    app clients without any domain registration. After the user authorizes,
    Google redirects to http://localhost/?code=...  which fails in the browser.
    The UI then asks the user to copy & paste that URL back.
    """
    if not os.path.exists(CLIENT_SECRETS_FILE):
        return render_template(
            "error.html",
            message="google_client_secret.json not found in /documents. "
                    "Please make sure the file is mounted correctly.",
        )

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=LOOPBACK_REDIRECT_URI,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # Always return refresh_token
    )
    session["oauth_state"] = state
    return render_template("authorize.html", auth_url=auth_url, public_url=display_url())


@app.route("/oauth/paste", methods=["GET", "POST"])
def oauth_paste():
    """Show (GET) or process (POST) the paste-URL form.

    The user pastes the full http://localhost/?code=...&state=... URL that
    appeared in their browser after Google redirected them. We extract the
    code and state parameters and exchange them for tokens server-side.
    """
    if request.method == "GET":
        return render_template("paste.html", public_url=display_url())

    pasted = request.form.get("redirect_url", "").strip()
    if not pasted:
        return render_template(
            "paste.html",
            public_url=display_url(),
            error="Please paste the URL from your browser's address bar.",
        )

    # Parse query parameters from the pasted URL
    try:
        parsed = urlparse(pasted)
        params = parse_qs(parsed.query)
    except Exception:
        return render_template(
            "paste.html",
            public_url=display_url(),
            error="That doesn't look like a valid URL. Please copy the full address bar URL.",
        )

    # Check for Google error (e.g. user clicked "Deny")
    if "error" in params:
        return render_template(
            "error.html",
            message=f"Google returned an error: {params['error'][0]}",
        )

    code = params.get("code", [None])[0]
    state = params.get("state", [None])[0]

    if not code:
        return render_template(
            "paste.html",
            public_url=display_url(),
            error="No authorization code found in that URL. Make sure you copied the full address bar URL after signing in with Google.",
        )

    # Validate state to prevent CSRF — but be lenient if the session expired
    stored_state = session.get("oauth_state")
    if stored_state and state and stored_state != state:
        return render_template(
            "error.html",
            message="State mismatch — the URL may be stale or tampered with. Please start over.",
        )

    try:
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            state=state or stored_state,
            redirect_uri=LOOPBACK_REDIRECT_URI,
        )

        # Reconstruct a clean authorization_response URL that fetch_token can parse.
        # We only need the path + query from the pasted URL; scheme and host must
        # match LOOPBACK_REDIRECT_URI exactly.
        loopback_parsed = urlparse(LOOPBACK_REDIRECT_URI)
        auth_response = urlunparse((
            loopback_parsed.scheme,
            loopback_parsed.netloc,
            parsed.path or "/",
            "",
            parsed.query,
            "",
        ))

        flow.fetch_token(authorization_response=auth_response)
        credentials = flow.credentials

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
    s["helper_url"] = display_url()
    s["redirect_uri"] = LOOPBACK_REDIRECT_URI
    return s


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8643, debug=False)
