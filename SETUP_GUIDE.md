# PhoneTrack Timeline Automation - Setup Guide

## For Nextcloud AIO (Docker)

### 1. Copy Script to Container

```bash
# Copy the script
docker cp phonetrack_timeline_updater.py nextcloud-aio-nextcloud:/opt/

# Make executable
docker exec nextcloud-aio-nextcloud chmod +x /opt/phonetrack_timeline_updater.py
```

### 2. Install workflow_script App

In Nextcloud:
1. Go to **Apps** → Search "workflow_script"
2. Install **External scripts**

### 3. Configure Workflow Rule

Go to **Admin Settings** → **Flow** → **External scripts**

Create a new rule:
- **When**: File created
- **and**: File name matches `*_daily_*.gpx`
- **Run script**:

```
python3 /opt/phonetrack_timeline_updater.py --file "%f" --path "%n"
```

### 4. Test

1. Wait for PhoneTrack to create a daily export, or manually create a test file
2. Check logs: `docker exec nextcloud-aio-nextcloud cat /tmp/phonetrack_timeline.log`
3. Verify timeline appears in `/PhoneTrack_export/TIMELINES/`

### 5. Make Script Persistent (Important!)

The script will be lost when container updates. Add to your docker-compose or create a volume mount for `/opt/`.
