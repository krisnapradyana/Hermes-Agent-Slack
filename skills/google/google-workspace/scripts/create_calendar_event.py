"""
Create a Google Calendar event.

Usage:
    python3 create_calendar_event.py <SLACK_USER_ID> <EVENT_JSON>

Arguments:
    SLACK_USER_ID   The Slack user ID of the requester (for OAuth token resolution)
    EVENT_JSON      A JSON object describing the event. Supported fields:
                      - "title":       string  (required) — event name
                      - "description": string  (optional) — event description
                      - "start":       string  (required) — ISO 8601 datetime or date
                                       e.g. "2026-06-25T10:00:00+07:00"  (timed event)
                                            "2026-06-25"                  (all-day event)
                      - "end":         string  (required) — ISO 8601 datetime or date
                      - "attendees":   array of email strings (optional)
                                       e.g. ["alice@example.com","bob@example.com"]
                      - "timezone":    string  (optional, default "UTC")
                                       e.g. "Asia/Jakarta"

    Example (timed event):
        '{"title":"Team Sync","description":"Weekly sync","start":"2026-06-25T10:00:00+07:00","end":"2026-06-25T11:00:00+07:00","attendees":["alice@example.com"]}'

    Example (all-day event):
        '{"title":"Public Holiday","start":"2026-06-25","end":"2026-06-26"}'

Output:
    Prints the URL of the created Calendar event on success.
    Prints an auth prompt and exits if no token is found.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))
import gws_auth

from googleapiclient.discovery import build


def create_event(slack_user_id: str, event_data: dict) -> str:
    creds = gws_auth.get_credentials(slack_user_id)
    cal = build("calendar", "v3", credentials=creds)

    title = event_data.get("title", "Untitled Event")
    description = event_data.get("description", "")
    start_str = event_data.get("start")
    end_str = event_data.get("end")
    attendees = event_data.get("attendees", [])
    timezone = event_data.get("timezone", "UTC")

    if not start_str or not end_str:
        print("Error: 'start' and 'end' fields are required in EVENT_JSON.")
        sys.exit(1)

    # Detect if all-day (date only) or timed
    def build_time(dt_str):
        if "T" in dt_str or ":" in dt_str:
            return {"dateTime": dt_str, "timeZone": timezone}
        else:
            return {"date": dt_str}

    body = {
        "summary": title,
        "description": description,
        "start": build_time(start_str),
        "end": build_time(end_str),
    }

    if attendees:
        body["attendees"] = [{"email": a} for a in attendees]

    event = cal.events().insert(calendarId="primary", body=body).execute()
    event_url = event.get("htmlLink", "")
    print(event_url)
    return event_url


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Usage: python3 create_calendar_event.py <SLACK_USER_ID> <EVENT_JSON>')
        print('EVENT_JSON example: \'{"title":"Team Sync","start":"2026-06-25T10:00:00+07:00","end":"2026-06-25T11:00:00+07:00"}\'')
        sys.exit(1)

    slack_user_id = sys.argv[1]
    try:
        event_data = json.loads(sys.argv[2])
    except json.JSONDecodeError as e:
        print(f"Error: Invalid EVENT_JSON — {e}")
        sys.exit(1)

    create_event(slack_user_id, event_data)
