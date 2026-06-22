---
name: google-auth-helper
description: "Handles Google Workspace authentication errors. When Hermes cannot access Google Drive, Google Docs, Google Calendar, or Google Sheets due to missing or expired authorization, this skill instructs Hermes to guide users to the OAuth setup page instead of failing silently or showing raw error URLs."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [google, auth, oauth, authentication, authorization, google-drive, google-docs, google-calendar, google-sheets, token, credentials, permission, access, connect, login]
    related_skills: [seedance-video-image-generator]
---

# Google Workspace Authentication Helper

## When to apply this skill

Apply this skill whenever you encounter **any of the following**:
- The user explicitly asks to authenticate, log in, or connect their Google Workspace account (e.g., "authenticate me", "login to google")
- A Google API call fails with an authentication or authorization error
- `token.json` is missing or expired
- Google Drive, Docs, Calendar, or Sheets returns a 401 / 403 error
- The built-in `google_api.py` script raises an auth-related exception
- You would normally output a raw `http://localhost/?code=...` OAuth URL to the user

**Do NOT paste raw OAuth authorization URLs into Slack.** Remote users cannot use them and they are confusing to non-technical people.

---

## What to do instead

When Google authentication is required (or requested), send the following message to the user in Slack:

---

**Template for explicit authentication requests (e.g. "authenticate me"):**

> 🔗 **Connect your personal Google account**
> 
> To authorize Hermes to use your Google Workspace account, please visit this setup page:
> 👉 [Helper URL]/oauth/start?user=<SLACK_USER_ID>
> 
> *(Replace `[Helper URL]` with the URL from `config.yaml` -> `google_drive.oauth_helper_url` and `<SLACK_USER_ID>` with the actual Slack user ID).*

---

**Template for failed API calls (adapt tone to the conversation):**

> ⚠️ **Google authorization needed**
>
> I can't complete this request because Hermes hasn't been authorized to access Google Workspace yet (or the authorization has expired).
>
> **Please ask your admin to visit the setup page:**
> 👉 Check `config.yaml` → `google_drive.oauth_helper_url` for the exact link.
>
> The admin clicks **"Connect Google Account"**, signs in once, and everyone's requests will work automatically after that. No technical steps required.
>
> _(If you are the admin and are on the same network as the Hermes server, you can open that link directly.)_

---

## How to get the helper URL

Read it from `config.yaml` at the path `google_drive.oauth_helper_url`.

```python
# Example: read config to get the URL
import yaml
cfg = yaml.safe_load(open("/opt/data/custom-config.yaml"))
helper_url = cfg.get("google_drive", {}).get("oauth_helper_url", "http://localhost:8643")
```

Then include the actual URL in your Slack message, e.g.:
> 👉 **Setup page:** http://192.168.1.50:8643

---

## Important notes for remote users

- The setup page may be hosted on the **internal network** (not the public internet)
- Remote/WFH users may need to be on **VPN** or ask their admin to connect on their behalf
- The authorization only needs to be done **once** — after that, all Slack users benefit automatically
- The token is stored securely on the server and is never shared with Slack users

---

## After authorization is complete

Once the admin has authorized, simply retry the original request. No restart is needed — the agent picks up the new token automatically.
