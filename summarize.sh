#!/usr/bin/env bash
# =============================================================================
# summarize.sh — Fetch and print a Slack channel's history via Hermes
# =============================================================================
#
# Usage:
#   ./summarize.sh <CHANNEL_ID> [--limit N]
#
# Arguments:
#   CHANNEL_ID   Slack channel ID (e.g. C0B9YPS8HDZ)
#   --limit N    Number of messages to fetch (default: 250, max recommended: 500)
#
# Examples:
#   ./summarize.sh C0B9YPS8HDZ                 # fetch last 250 messages
#   ./summarize.sh C0B9YPS8HDZ --limit 500     # fetch last 500 messages
#   ./summarize.sh C0B9YPS8HDZ > history.txt   # save to file
#
# Requirements:
#   - Docker must be running
#   - The 'hermes-local-agent' container must be up
#   - SLACK_BOT_TOKEN must be set in your .env file
# =============================================================================

set -euo pipefail

# --- Argument Parsing -------------------------------------------------------

CHANNEL_ID="${1:?Error: CHANNEL_ID is required. Usage: ./summarize.sh <CHANNEL_ID> [--limit N]}"
LIMIT=250  # Default: 250 messages

# Parse optional --limit flag from remaining args
shift
while [[ $# -gt 0 ]]; do
    case "$1" in
        --limit)
            LIMIT="${2:?--limit requires a value (e.g. --limit 500)}"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            echo "Usage: ./summarize.sh <CHANNEL_ID> [--limit N]" >&2
            exit 1
            ;;
    esac
done

# --- Container Check --------------------------------------------------------

CONTAINER="hermes-local-agent"

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "Error: Container '${CONTAINER}' is not running." >&2
    echo "Start it with: docker-compose up -d" >&2
    exit 1
fi

# --- Run Fetcher Inside Container -------------------------------------------

echo "Fetching last ${LIMIT} messages from channel ${CHANNEL_ID}..." >&2

docker exec "${CONTAINER}" \
    /opt/hermes/.venv/bin/python3 \
    /opt/data/custom-skills/communication/channel-summarizer/fetch_history.py \
    "${CHANNEL_ID}" --limit "${LIMIT}"
