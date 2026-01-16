# Nextcloud PhoneTrack Timeline Tools

Automation tools for merging Nextcloud PhoneTrack daily GPS exports into unified timeline files.

## What This Does

PhoneTrack exports daily GPX files with your location history. This project automatically merges those daily exports into a single timeline file per user/session, sorted chronologically with duplicates removed.

## Files

| File | Description |
|------|-------------|
| `phonetrack_timeline_updater.py` | Main script - triggered by Nextcloud workflow_script to auto-merge new exports |
| `SETUP_GUIDE.md` | Installation instructions for Nextcloud AIO (Docker) |

## Quick Setup (Nextcloud AIO)

```bash
# Copy script to container
docker cp phonetrack_timeline_updater.py nextcloud-aio-nextcloud:/opt/
docker exec nextcloud-aio-nextcloud chmod +x /opt/phonetrack_timeline_updater.py
```

In Nextcloud, install the **workflow_script** app and create a rule:
- **Trigger**: File created matching `*_daily_*.gpx`
- **Command**: `python3 /opt/phonetrack_timeline_updater.py --file "%f" --path "%n"`

## How It Works

1. PhoneTrack exports a daily GPX file (e.g., `Session_daily_2026-01-17_User.gpx`)
2. Nextcloud workflow_script triggers the Python script
3. Script parses the filename to identify session/user
4. Loads existing timeline (if any) and new points
5. Deduplicates, sorts chronologically, writes updated timeline
6. Output: `PhoneTrack_export/TIMELINES/Session_User_TIMELINE.gpx`

## Features

- **Accent normalization**: `Ági` and `Agi` treated as same user
- **Duplicate removal**: Same lat/lon/time = one point
- **Full GPX structure**: Preserves elevation, satellites, speed, accuracy, battery, user agent

## Requirements

- Nextcloud with PhoneTrack app
- workflow_script app installed
- Python 3.8+ (included in Nextcloud AIO container)

