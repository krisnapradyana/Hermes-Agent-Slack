import argparse
import json
import os
import subprocess
import urllib.request
import sys
from pathlib import Path

import uuid

# Paths
VENV_PYTHON = "/opt/hermes/.venv/bin/python"
GOOGLE_API_SCRIPT = "/opt/hermes/skills/productivity/google-workspace/scripts/google_api.py"
TEMP_FILE = f"/tmp/seedance_{uuid.uuid4().hex}.mp4"

def log(msg):
    print(f"[GDrive-Helper] {msg}", flush=True)

def download_video(url, output_path):
    log(f"Downloading video from CDN...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        with open(output_path, "wb") as f:
            f.write(r.read())
    log(f"Download complete: {os.path.getsize(output_path)/1024/1024:.2f} MB saved to {output_path}")

def run_google_api(args):
    cmd = [VENV_PYTHON, GOOGLE_API_SCRIPT] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Google API call failed: {result.stderr or result.stdout}")
    return json.loads(result.stdout)

def main():
    parser = argparse.ArgumentParser(description="Download video and upload to Google Drive")
    parser.add_argument("--url", required=True, help="CDN URL of the video")
    parser.add_argument("--folder", help="Optional parent folder ID in Google Drive")
    args = parser.parse_args()

    try:
        # 1. Download to temporary path
        download_video(args.url, TEMP_FILE)

        # 2. Upload to Google Drive
        log("Uploading to Google Drive...")
        upload_args = ["drive", "upload", TEMP_FILE]
        if args.folder:
            upload_args += ["--parent", args.folder]
        
        upload_res = run_google_api(upload_args)
        file_id = upload_res.get("id")
        if not file_id:
            raise RuntimeError(f"Upload succeeded but no file ID returned: {upload_res}")
        log(f"Upload complete. File ID: {file_id}")

        # 3. Share publicly (anyone can view)
        log("Setting sharing permissions to public (anyone with link can view)...")
        share_res = run_google_api(["drive", "share", file_id, "--type", "anyone", "--role", "reader"])
        log(f"Sharing complete: {share_res.get('status')}")

        # 4. Fetch shareable link
        log("Retrieving shareable link...")
        get_res = run_google_api(["drive", "get", file_id])
        web_link = get_res.get("webViewLink")
        if not web_link:
            raise RuntimeError(f"Could not retrieve webViewLink for file {file_id}")

        # Output the final success message with link
        print("\n" + "="*60)
        print(f"SUCCESS: Video uploaded and shared successfully!")
        print(f"Google Drive Link: {web_link}")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\nERROR: Failed to download/upload video: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        # 5. Clean up temporary file
        if os.path.exists(TEMP_FILE):
            try:
                os.remove(TEMP_FILE)
                log(f"Cleaned up temporary file: {TEMP_FILE}")
            except Exception as cleanup_err:
                log(f"Warning: Failed to delete temporary file {TEMP_FILE}: {cleanup_err}")

if __name__ == "__main__":
    main()
