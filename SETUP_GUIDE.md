# PhoneTrack Timeline Automation - Setup Guide

## For Nextcloud AIO (Docker)

### 1. Clone the Repository on the Server

```bash
cd ~
git clone https://github.com/Byter3/Nextcloud-tools.git
```

### 2. Deploy the Script to the Container

```bash
cd ~/Nextcloud-tools
sudo docker cp phonetrack_timeline_updater.py nextcloud-aio-nextcloud:/opt/
```

### 3. Configure the Cron Script

Edit `cron_phonetrack.sh` and update these variables to match your setup:

```bash
REPO_DIR="/home/YOUR_USER/Nextcloud-tools"    # Path to the cloned repo
NC_CONTAINER="nextcloud-aio-nextcloud"         # Nextcloud container name
NC_USER="YOUR_NC_USER"                         # Nextcloud username
```

### 4. Set Up the Daily Cron Job

The cron job should run daily after PhoneTrack creates its daily exports. It will:
- Re-deploy the script if it was lost after a container update
- Process yesterday's and today's daily PhoneTrack exports

```bash
# Make the cron script executable
chmod +x ~/Nextcloud-tools/cron_phonetrack.sh

# Add to root's crontab
sudo crontab -e
```

Add this line (adjust time and paths):

```
0 22 * * * /home/YOUR_USER/Nextcloud-tools/cron_phonetrack.sh >> /home/YOUR_USER/phonetrack_cron.log 2>&1
```

### 5. Test

```bash
# Run the cron script manually
sudo ~/Nextcloud-tools/cron_phonetrack.sh

# Or test a specific date directly
sudo docker exec nextcloud-aio-nextcloud python3 /opt/phonetrack_timeline_updater.py --process-date 2026-03-21 --user YOUR_NC_USER

# Check logs
sudo docker exec nextcloud-aio-nextcloud cat /tmp/phonetrack_timeline.log | tail -20

# Verify timelines
sudo docker exec nextcloud-aio-nextcloud ls -lt "/mnt/ncdata/YOUR_NC_USER/files/PhoneTrack_export/TIMELINES/" | head -10
```

### 6. Batch Process Missed Files

If the script was down for a period, process each missed date:

```bash
# Process a specific date
sudo docker exec nextcloud-aio-nextcloud python3 /opt/phonetrack_timeline_updater.py --process-date YYYY-MM-DD --user YOUR_NC_USER

# Process a range of dates (e.g., all of March)
for d in $(seq -f "%02g" 1 31); do
  sudo docker exec nextcloud-aio-nextcloud python3 /opt/phonetrack_timeline_updater.py --process-date "2026-03-$d" --user YOUR_NC_USER
done
```

### 7. Update the Script

When the script is updated on GitHub:

```bash
cd ~/Nextcloud-tools
git pull
sudo docker cp phonetrack_timeline_updater.py nextcloud-aio-nextcloud:/opt/
```

The cron job will also auto-redeploy if the script is missing from the container.

### 8. Check Logs

```bash
# Cron execution log
cat ~/phonetrack_cron.log

# Script processing log (inside container)
sudo docker exec nextcloud-aio-nextcloud cat /tmp/phonetrack_timeline.log | tail -30
```

---

## Notes

- **Container updates**: The script inside `/opt/` is lost when Nextcloud AIO updates. The cron job handles re-deployment automatically.
- **Timeline files**: Stored in `.../PhoneTrack_export/TIMELINES/` as `{Session}_{Device}_TIMELINE.gpx`
- **Deduplication**: The script deduplicates by (lat, lon, timestamp) so re-running on already-processed files is safe
- **Nextcloud Flow**: Previously used `workflow_script` app but it proved unreliable after container updates. Replaced with cron approach.
