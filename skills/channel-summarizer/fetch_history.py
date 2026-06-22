import os
import sys
import json
import urllib.request
from datetime import datetime

def fetch_history(channel_id):
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        print("Error: SLACK_BOT_TOKEN environment variable is not set.")
        sys.exit(1)

    url = f"https://slack.com/api/conversations.history?channel={channel_id}&limit=100"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        if data.get("ok"):
            messages = data.get("messages", [])
            
            history = []
            # Messages are returned in reverse chronological order
            for msg in reversed(messages):
                user = msg.get("user", "UnknownUser")
                text = msg.get("text", "")
                ts = float(msg.get("ts", 0))
                time_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                if text:
                    history.append(f"[{time_str}] User {user}: {text}")
                    
            print("--- CHANNEL HISTORY ---")
            print("\n".join(history))
            print("--- END OF HISTORY ---")
        else:
            print(f"Error fetching history: {data.get('error')}")
            if data.get('error') == "missing_scope":
                print("The Slack app requires 'channels:history' and/or 'groups:history' scopes.")
    except Exception as e:
        print(f"Failed to fetch history: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 fetch_history.py <CHANNEL_ID>")
        sys.exit(1)
        
    fetch_history(sys.argv[1])
