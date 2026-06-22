"""
Create a Google Sheet with the given title and optional data rows.

Usage:
    python3 create_sheet.py <SLACK_USER_ID> <TITLE> [DATA_JSON]

Arguments:
    SLACK_USER_ID   The Slack user ID of the requester (for OAuth token resolution)
    TITLE           The title of the spreadsheet (quote if it contains spaces)
    DATA_JSON       Optional. A JSON 2D array of rows/columns to populate starting at A1.
                    Example: '[["Name","Age"],["Alice","30"],["Bob","25"]]'
                    If omitted, an empty spreadsheet is created.

Output:
    Prints the URL of the created Google Sheet on success.
    Prints an auth prompt and exits if no token is found.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))
import gws_auth

from googleapiclient.discovery import build


def create_sheet(slack_user_id: str, title: str, data: list) -> str:
    creds = gws_auth.get_credentials(slack_user_id)
    sheets_svc = build("sheets", "v4", credentials=creds)

    # Create the spreadsheet
    spreadsheet = sheets_svc.spreadsheets().create(
        body={
            "properties": {"title": title},
            "sheets": [{"properties": {"title": "Sheet1"}}],
        }
    ).execute()
    sheet_id = spreadsheet["spreadsheetId"]

    # Write data if provided
    if data:
        sheets_svc.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="Sheet1!A1",
            valueInputOption="USER_ENTERED",
            body={"values": data},
        ).execute()

    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    print(sheet_url)
    return sheet_url


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Usage: python3 create_sheet.py <SLACK_USER_ID> <TITLE> [DATA_JSON]')
        print('DATA_JSON example: \'[["Name","Score"],["Alice","95"],["Bob","87"]]\'')
        sys.exit(1)

    slack_user_id = sys.argv[1]
    title = sys.argv[2]
    data = []
    if len(sys.argv) > 3:
        try:
            data = json.loads(sys.argv[3])
        except json.JSONDecodeError as e:
            print(f"Error: Invalid DATA_JSON — {e}")
            sys.exit(1)

    create_sheet(slack_user_id, title, data)
