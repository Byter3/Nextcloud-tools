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

### 3. Set Up the Daily Cron Job

The cron job runs daily at 23:00 (CET) / 22:00 (UTC) to:
- Re-deploy the script if it was lost after a container update
- Process yesterday's and today's daily PhoneTrack exports

```bash
# Make the cron script executable
chmod +x ~/Nextcloud-tools/cron_phonetrack.sh

# Add to root's crontab
sudo crontab -e
```

Add this line:

```
0 22 * * * /home/ag/Nextcloud-tools/cron_phonetrack.sh >> /home/ag/phonetrack_cron.log 2>&1
```

### 4. Test

```bash
# Run the cron script manually
sudo ~/Nextcloud-tools/cron_phonetrack.sh

# Or test a specific date directly
sudo docker exec nextcloud-aio-nextcloud python3 /opt/phonetrack_timeline_updater.py --process-date 2026-03-21

# Check logs
sudo docker exec nextcloud-aio-nextcloud cat /tmp/phonetrack_timeline.log | tail -20

# Verify timelines
sudo docker exec nextcloud-aio-nextcloud ls -lt "/mnt/ncdata/AG/files/PhoneTrack_export/TIMELINES/" | head -10
```

### 5. Batch Process Missed Files

If the script was down for a period, process each missed date:

```bash
# Process a specific date
sudo docker exec nextcloud-aio-nextcloud python3 /opt/phonetrack_timeline_updater.py --process-date YYYY-MM-DD

# Process a range of dates
for d in $(seq -f "%02g" 1 31); do
  sudo docker exec nextcloud-aio-nextcloud python3 /opt/phonetrack_timeline_updater.py --process-date "2026-03-$d"
done
```

### 6. Update the Script

When the script is updated on GitHub:

```bash
cd ~/Nextcloud-tools
git pull
sudo docker cp phonetrack_timeline_updater.py nextcloud-aio-nextcloud:/opt/
```

The cron job will also auto-redeploy if the script is missing from the container.

### 7. Check Logs

```bash
# Cron execution log
cat ~/phonetrack_cron.log

# Script processing log (inside container)
sudo docker exec nextcloud-aio-nextcloud cat /tmp/phonetrack_timeline.log | tail -30
```

---

## Notes

- **Container updates**: The script inside `/opt/` is lost when Nextcloud AIO updates. The cron job handles re-deployment automatically.
- **PhoneTrack exports**: Daily exports are created around 20:00-22:00 UTC in `/mnt/ncdata/AG/files/PhoneTrack_export/`
- **Timeline files**: Stored in `.../TIMELINES/` as `{Session}_{Device}_TIMELINE.gpx`
- **Deduplication**: The script deduplicates by (lat, lon, timestamp) so re-running on already-processed files is safe
- **Nextcloud Flow**: Previously used `workflow_script` app but it proved unreliable after container updates. Replaced with cron approach.
