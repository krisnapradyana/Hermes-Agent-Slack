"""
Create a Google Doc with the given title and content.

Usage:
    python3 create_doc.py <SLACK_USER_ID> <TITLE> <CONTENT>

Arguments:
    SLACK_USER_ID   The Slack user ID of the requester (for OAuth token resolution)
    TITLE           The title of the Google Doc (quote if it contains spaces)
    CONTENT         The body text content to insert into the document

Output:
    Prints the URL of the created Google Doc on success.
    Prints an auth prompt and exits if no token is found.
"""

import sys
import os

# Allow importing gws_auth from the same scripts directory
sys.path.insert(0, os.path.dirname(__file__))
import gws_auth

from googleapiclient.discovery import build


def create_doc(slack_user_id: str, title: str, content: str) -> str:
    creds = gws_auth.get_credentials(slack_user_id)
    docs = build("docs", "v1", credentials=creds)

    # Create the document
    doc = docs.documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]

    # Insert content
    if content:
        docs.documents().batchUpdate(
            documentId=doc_id,
            body={
                "requests": [
                    {"insertText": {"location": {"index": 1}, "text": content + "\n"}}
                ]
            },
        ).execute()

    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
    print(doc_url)
    return doc_url


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 create_doc.py <SLACK_USER_ID> <TITLE> [CONTENT]")
        sys.exit(1)

    slack_user_id = sys.argv[1]
    title = sys.argv[2]
    content = sys.argv[3] if len(sys.argv) > 3 else ""

    create_doc(slack_user_id, title, content)
