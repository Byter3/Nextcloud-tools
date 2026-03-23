#!/bin/bash
# PhoneTrack Timeline Cron Script
# Ensures the timeline updater is deployed and processes daily exports.
#
# Configure the variables below, then install in root's crontab:
#   0 22 * * * /path/to/cron_phonetrack.sh >> /path/to/phonetrack_cron.log 2>&1

# === CONFIGURATION ===
REPO_DIR="/home/YOUR_USER/Nextcloud-tools"     # Path to the cloned repo on the host
NC_CONTAINER="nextcloud-aio-nextcloud"          # Nextcloud Docker container name
NC_USER="YOUR_NC_USER"                          # Nextcloud username
SCRIPT_PATH="/opt/phonetrack_timeline_updater.py"

echo "$(date): === PhoneTrack Cron Start ==="

# Step 1: Ensure the script is deployed in the container
if ! docker exec "$NC_CONTAINER" test -f "$SCRIPT_PATH" 2>/dev/null; then
    echo "$(date): Script missing, re-deploying..."
    docker cp "$REPO_DIR/phonetrack_timeline_updater.py" "$NC_CONTAINER:$SCRIPT_PATH"
    echo "$(date): Script re-deployed"
fi

# Step 2: Get yesterday's and today's date (UTC)
TODAY=$(date -u +%Y-%m-%d)
YESTERDAY=$(date -u -d "yesterday" +%Y-%m-%d)

# Step 3: Process daily exports using Python (handles spaces in filenames)
echo "$(date): Processing exports for $YESTERDAY"
docker exec "$NC_CONTAINER" python3 "$SCRIPT_PATH" --process-date "$YESTERDAY" --user "$NC_USER"

echo "$(date): Processing exports for $TODAY"
docker exec "$NC_CONTAINER" python3 "$SCRIPT_PATH" --process-date "$TODAY" --user "$NC_USER"

echo "$(date): === PhoneTrack Cron Complete ==="
