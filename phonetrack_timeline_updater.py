#!/usr/bin/env python3
"""
PhoneTrack Timeline Updater for Nextcloud AIO

This script is triggered by the workflow_script app when a new PhoneTrack
daily export GPX file is created. It merges the new file into the user's
timeline file.

Usage (called by workflow_script):
    python3 /opt/phonetrack_timeline_updater.py --file "%f" --path "%n"

Arguments:
    --file: Path to the temporary file (%f placeholder)
    --path: Nextcloud-relative path (%n placeholder)
            Format: {user}/files/PhoneTrack_export/{filename}.gpx
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
import unicodedata
import argparse
import logging
import copy
import sys
import re
import os
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/phonetrack_timeline.log')
    ]
)
logger = logging.getLogger(__name__)

# GPX namespace
GPX_NS = 'http://www.topografix.com/GPX/1/1'

# Regex for parsing PhoneTrack daily export filenames
# Pattern: {SessionName}_daily_{YYYY-MM-DD}_{Username}.gpx
DAILY_PATTERN = re.compile(r'^(.+)_daily_(\d{4}-\d{2}-\d{2})_(.+)\.gpx$')

# Default paths for Nextcloud AIO
DEFAULT_DATA_DIR = '/mnt/ncdata'
TIMELINES_SUBDIR = 'TIMELINES'


def normalize_text(text: str) -> str:
    """Remove accents/diacritics from text."""
    normalized = unicodedata.normalize('NFD', text)
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')


def parse_nextcloud_path(nc_path: str) -> tuple[str, str, str, str] | None:
    """
    Parse Nextcloud-relative path to extract user and filename info.
    
    Path format: {user}/files/PhoneTrack_export/{filename}.gpx
    
    Returns: (username_nc, session_name, device_name, date_str) or None
    """
    parts = nc_path.replace('\\', '/').split('/')
    
    if len(parts) < 3:
        return None
    
    nc_user = parts[0]  # Nextcloud username (folder owner)
    filename = parts[-1]  # The GPX filename
    
    # Parse the filename
    match = DAILY_PATTERN.match(filename)
    if not match:
        logger.warning(f"Filename doesn't match daily export pattern: {filename}")
        return None
    
    session_name = match.group(1)
    date_str = match.group(2)
    device_name = match.group(3)
    
    return (nc_user, session_name, device_name, date_str)


def parse_timestamp(time_str: str) -> datetime:
    """Parse ISO format timestamp from GPX."""
    if 'Z' in time_str:
        return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    return datetime.fromisoformat(time_str)


def collect_track_points(file_path: Path) -> list[tuple[datetime, ET.Element]]:
    """Collect all track points from a GPX file."""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        points = []
        
        for trkpt in root.findall('.//{%s}trkpt' % GPX_NS):
            time_elem = trkpt.find('{%s}time' % GPX_NS)
            if time_elem is not None and time_elem.text:
                try:
                    ts = parse_timestamp(time_elem.text)
                    if ts.year == 2000:  # Skip year 2000 clock bug
                        continue
                    points.append((ts, copy.deepcopy(trkpt)))
                except ValueError:
                    pass
        
        return points
    except Exception as e:
        logger.error(f"Failed to parse GPX file {file_path}: {e}")
        return []


def write_gpx(points: list[tuple[datetime, ET.Element]], 
              output_path: Path,
              session_name: str,
              device_name: str) -> None:
    """Write points to a GPX file with full PhoneTrack structure."""
    export_time = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>',
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" '
        'xmlns:gpxx="http://www.garmin.com/xmlschemas/GpxExtensions/v3" '
        'xmlns:wptx1="http://www.garmin.com/xmlschemas/WaypointExtension/v1" '
        'xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1" '
        'creator="PhoneTrack Timeline Updater" version="1.1" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">',
        '<metadata>',
        f' <time>{export_time}</time>',
        f' <name>{session_name}</name>',
        '</metadata>',
        '<trk>',
        f' <name>{device_name}</name>',
        ' <trkseg>',
    ]

    for ts, pt in points:
        lat = pt.get('lat')
        lon = pt.get('lon')
        lines.append(f'  <trkpt lat="{lat}" lon="{lon}">')
        
        time_elem = pt.find('{%s}time' % GPX_NS)
        if time_elem is not None:
            lines.append(f'   <time>{time_elem.text}</time>')
        
        ele = pt.find('{%s}ele' % GPX_NS)
        if ele is not None and ele.text:
            lines.append(f'   <ele>{ele.text}</ele>')
        
        sat = pt.find('{%s}sat' % GPX_NS)
        if sat is not None and sat.text:
            lines.append(f'   <sat>{sat.text}</sat>')
        
        ext = pt.find('{%s}extensions' % GPX_NS)
        if ext is not None:
            lines.append('   <extensions>')
            for tag in ['speed', 'course', 'accuracy', 'batterylevel', 'useragent']:
                elem = ext.find('{%s}%s' % (GPX_NS, tag))
                if elem is not None and elem.text:
                    lines.append(f'     <{tag}>{elem.text}</{tag}>')
            lines.append('   </extensions>')
        
        lines.append('  </trkpt>')

    lines.extend([' </trkseg>', '</trk>', '</gpx>'])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def update_timeline(new_file: Path, nc_path: str, data_dir: Path) -> bool:
    """
    Main function to update a timeline with new GPX data.
    
    Args:
        new_file: Path to the new GPX file (temporary file from %f)
        nc_path: Nextcloud-relative path (%n)
        data_dir: Nextcloud data directory (/mnt/ncdata)
    
    Returns: True if successful, False otherwise
    """
    # Parse the path
    parsed = parse_nextcloud_path(nc_path)
    if not parsed:
        logger.error(f"Could not parse Nextcloud path: {nc_path}")
        return False
    
    nc_user, session_name, device_name, date_str = parsed
    logger.info(f"Processing: User={nc_user}, Session={session_name}, Device={device_name}, Date={date_str}")
    
    # Normalize names for filename
    clean_session = normalize_text(session_name)
    clean_device = normalize_text(device_name)
    
    # Build timeline path
    # {data_dir}/{user}/files/PhoneTrack_export/TIMELINES/{Session}_{Device}_TIMELINE.gpx
    timeline_dir = data_dir / nc_user / 'files' / 'PhoneTrack_export' / TIMELINES_SUBDIR
    timeline_filename = f"{clean_session}_{clean_device}_TIMELINE.gpx"
    timeline_path = timeline_dir / timeline_filename
    
    logger.info(f"Timeline file: {timeline_path}")
    
    # Collect points from new file
    new_points = collect_track_points(new_file)
    if not new_points:
        logger.warning(f"No valid track points in new file: {new_file}")
        return False
    
    logger.info(f"New file has {len(new_points)} track points")
    
    # Load existing timeline if exists
    all_points = []
    if timeline_path.exists():
        existing_points = collect_track_points(timeline_path)
        logger.info(f"Existing timeline has {len(existing_points)} points")
        all_points.extend(existing_points)
    else:
        logger.info("No existing timeline, creating new one")
    
    # Add new points
    all_points.extend(new_points)
    
    # Deduplicate
    seen = set()
    unique = []
    for ts, pt in all_points:
        key = (pt.get('lat'), pt.get('lon'), ts.isoformat())
        if key not in seen:
            seen.add(key)
            unique.append((ts, pt))
    
    logger.info(f"After dedup: {len(unique)} unique points")
    
    # Sort by timestamp
    unique.sort(key=lambda x: x[0])
    
    # Write timeline
    write_gpx(unique, timeline_path, session_name, device_name)
    logger.info(f"Timeline updated: {timeline_path}")
    
    # Trigger Nextcloud to rescan the file so it appears in the UI
    try:
        timeline_nc_path = f"/{nc_user}/files/PhoneTrack_export/{TIMELINES_SUBDIR}"
        scan_cmd = ['php', '/var/www/html/occ', 'files:scan', nc_user, '--path', timeline_nc_path]
        result = subprocess.run(scan_cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            logger.info(f"Nextcloud scan completed for {timeline_nc_path}")
        else:
            logger.warning(f"Nextcloud scan returned code {result.returncode}: {result.stderr}")
    except Exception as e:
        logger.warning(f"Failed to trigger Nextcloud scan: {e}")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Update PhoneTrack timeline with new GPX data'
    )
    parser.add_argument(
        '--file', '-f',
        type=Path,
        required=True,
        help='Path to the new GPX file (workflow_script %%f placeholder)'
    )
    parser.add_argument(
        '--path', '-p',
        type=str,
        required=True,
        help='Nextcloud-relative path (workflow_script %%n placeholder)'
    )
    parser.add_argument(
        '--data-dir', '-d',
        type=Path,
        default=Path(DEFAULT_DATA_DIR),
        help=f'Nextcloud data directory (default: {DEFAULT_DATA_DIR})'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Parse and log but do not write changes'
    )
    
    args = parser.parse_args()
    
    # Strip any surrounding quotes from paths (workflow_script may add them)
    file_str = str(args.file).strip("'\"")
    path_str = args.path.strip("'\"")
    args.file = Path(file_str)
    args.path = path_str
    
    logger.info(f"=== PhoneTrack Timeline Updater ===")
    logger.info(f"New file: {args.file}")
    logger.info(f"NC path: {args.path}")
    logger.info(f"Data dir: {args.data_dir}")
    
    if not args.file.exists():
        logger.error(f"File does not exist: {args.file}")
        sys.exit(1)
    
    if args.dry_run:
        logger.info("DRY RUN - no changes will be made")
        parsed = parse_nextcloud_path(args.path)
        if parsed:
            nc_user, session_name, device_name, date_str = parsed
            logger.info(f"Would update timeline for: {session_name}_{device_name}")
        sys.exit(0)
    
    success = update_timeline(args.file, args.path, args.data_dir)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
