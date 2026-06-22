"""
Create a Google Slides presentation with the given title and optional slides.

Usage:
    python3 create_slides.py <SLACK_USER_ID> <TITLE> [SLIDES_JSON]

Arguments:
    SLACK_USER_ID   The Slack user ID of the requester (for OAuth token resolution)
    TITLE           The title of the presentation (quote if it contains spaces)
    SLIDES_JSON     Optional. A JSON array of slide objects. Each object may have:
                      - "title": string (slide title text)
                      - "body":  string (slide body text)
                    Example: '[{"title":"Slide 1","body":"Content here"},{"title":"Slide 2","body":"More content"}]'
                    If omitted, a blank presentation is created.

Output:
    Prints the URL of the created Google Slides presentation on success.
    Prints an auth prompt and exits if no token is found.
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))
import gws_auth

from googleapiclient.discovery import build


def create_slides(slack_user_id: str, title: str, slides_data: list) -> str:
    creds = gws_auth.get_credentials(slack_user_id)
    slides_svc = build("slides", "v1", credentials=creds)

    # Create the presentation
    presentation = slides_svc.presentations().create(body={"title": title}).execute()
    pres_id = presentation["presentationId"]

    if slides_data:
        requests = []
        # The presentation starts with one blank slide; use it for the first slide
        first_slide_id = presentation["slides"][0]["objectId"]

        for i, slide_info in enumerate(slides_data):
            slide_title = slide_info.get("title", "")
            slide_body = slide_info.get("body", "")

            if i == 0:
                # Populate the existing first slide
                title_shape_id = None
                body_shape_id = None
                for element in presentation["slides"][0].get("pageElements", []):
                    ph = element.get("shape", {}).get("placeholder", {})
                    if ph.get("type") == "CENTERED_TITLE" or ph.get("type") == "TITLE":
                        title_shape_id = element["objectId"]
                    elif ph.get("type") in ("BODY", "SUBTITLE"):
                        body_shape_id = element["objectId"]

                if title_shape_id and slide_title:
                    requests.append(
                        {"insertText": {"objectId": title_shape_id, "text": slide_title}}
                    )
                if body_shape_id and slide_body:
                    requests.append(
                        {"insertText": {"objectId": body_shape_id, "text": slide_body}}
                    )
            else:
                # Create additional slides
                new_slide_id = f"slide_{i}"
                requests.append(
                    {
                        "createSlide": {
                            "objectId": new_slide_id,
                            "slideLayoutReference": {"predefinedLayout": "TITLE_AND_BODY"},
                            "placeholderIdMappings": [
                                {
                                    "layoutPlaceholder": {"type": "TITLE", "index": 0},
                                    "objectId": f"title_{i}",
                                },
                                {
                                    "layoutPlaceholder": {"type": "BODY", "index": 0},
                                    "objectId": f"body_{i}",
                                },
                            ],
                        }
                    }
                )
                if slide_title:
                    requests.append(
                        {"insertText": {"objectId": f"title_{i}", "text": slide_title}}
                    )
                if slide_body:
                    requests.append(
                        {"insertText": {"objectId": f"body_{i}", "text": slide_body}}
                    )

        if requests:
            slides_svc.presentations().batchUpdate(
                presentationId=pres_id, body={"requests": requests}
            ).execute()

    pres_url = f"https://docs.google.com/presentation/d/{pres_id}/edit"
    print(pres_url)
    return pres_url


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('Usage: python3 create_slides.py <SLACK_USER_ID> <TITLE> [SLIDES_JSON]')
        print('SLIDES_JSON example: \'[{"title":"Slide 1","body":"Hello"},{"title":"Slide 2","body":"World"}]\'')
        sys.exit(1)

    slack_user_id = sys.argv[1]
    title = sys.argv[2]
    slides_data = []
    if len(sys.argv) > 3:
        try:
            slides_data = json.loads(sys.argv[3])
        except json.JSONDecodeError as e:
            print(f"Error: Invalid SLIDES_JSON — {e}")
            sys.exit(1)

    create_slides(slack_user_id, title, slides_data)
