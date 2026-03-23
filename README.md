# Nextcloud PhoneTrack Timeline Tools

Automation tools for merging Nextcloud PhoneTrack daily GPS exports into unified timeline files.

## What This Does

PhoneTrack exports daily GPX files with your location history. This project automatically merges those daily exports into a single timeline file per session/device, sorted chronologically with duplicates removed.

## Files

| File | Description |
|------|-------------|
| `phonetrack_timeline_updater.py` | Main script — merges daily GPX exports into timeline files |
| `cron_phonetrack.sh` | Cron script — ensures the updater is deployed and runs daily |
| `SETUP_GUIDE.md` | Installation and setup instructions for Nextcloud AIO |

## Quick Setup (Nextcloud AIO)

```bash
# 1. Clone on your server
git clone https://github.com/Byter3/Nextcloud-tools.git
cd Nextcloud-tools

# 2. Deploy script to container
sudo docker cp phonetrack_timeline_updater.py nextcloud-aio-nextcloud:/opt/

# 3. Set up daily cron (runs at 23:00 local / 22:00 UTC)
chmod +x cron_phonetrack.sh
sudo crontab -e
# Add: 0 22 * * * /home/ag/Nextcloud-tools/cron_phonetrack.sh >> /home/ag/phonetrack_cron.log 2>&1
```

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed instructions.

## How It Works

1. PhoneTrack exports daily GPX files (e.g., `Session_daily_2026-01-17_User.gpx`)
2. Cron job runs nightly after exports are created
3. Script discovers all daily exports for the date via `--process-date`
4. Loads existing timeline (if any) and merges new points
5. Deduplicates, sorts chronologically, writes updated timeline
6. Triggers Nextcloud file scan so changes appear in the UI
7. Output: `PhoneTrack_export/TIMELINES/Session_Device_TIMELINE.gpx`

## Usage

```bash
# Process all exports for a specific date
python3 phonetrack_timeline_updater.py --process-date 2026-03-21

# Process a single file
python3 phonetrack_timeline_updater.py --file "/path/to/daily.gpx" --path "user/files/PhoneTrack_export/daily.gpx"

# Dry run (no changes)
python3 phonetrack_timeline_updater.py --process-date 2026-03-21 --dry-run
```

## Features

- **Batch date processing**: `--process-date` finds and processes all exports for a given date
- **Accent normalization**: `Ági` and `Agi` treated as same device
- **Duplicate removal**: Same lat/lon/time = one point
- **Full GPX structure**: Preserves elevation, satellites, speed, accuracy, battery, user agent
- **Auto-redeploy**: Cron script re-copies the updater if lost after container updates
- **Nextcloud scan**: Automatically triggers file scan after updates

## Requirements

- Nextcloud with PhoneTrack app
- Python 3.8+ (included in Nextcloud AIO container)
