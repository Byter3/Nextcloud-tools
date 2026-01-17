#!/usr/bin/env python3
"""
Auto-merge PhoneTrack GPX exports into timeline files.

This script scans a folder for GPX files exported from Nextcloud PhoneTrack,
groups them by session name and username, and merges each group into a
single timeline file.

Supported filename patterns:
- Daily exports: {SessionName}_daily_{YYYY-MM-DD}_{Username}.gpx
- Full exports: {SessionName}_{Username}.gpx

Output: Timelines/{SessionName}_{Username}_TIMELINE.gpx
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import unicodedata
import copy
import re
import argparse
import os

GPX_NS = 'http://www.topografix.com/GPX/1/1'

# Regex patterns for parsing filenames
DAILY_PATTERN = re.compile(r'^(.+)_daily_(\d{4}-\d{2}-\d{2})_(.+)\.gpx$')
FULL_PATTERN = re.compile(r'^(.+)_([^_]+)\.gpx$')


def normalize_text(text: str) -> str:
    """
    Normalize text by removing accents/diacritics.
    E.g., 'Ági' -> 'Agi', 'Amír' -> 'Amir', 'Gabó' -> 'Gabo'
    """
    # Normalize to NFD (decomposed form), then remove combining characters
    normalized = unicodedata.normalize('NFD', text)
    # Remove combining diacritical marks (category 'Mn')
    stripped = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return stripped


def parse_timestamp(time_str: str) -> datetime:
    """Parse ISO format timestamp from GPX."""
    if 'Z' in time_str:
        return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    return datetime.fromisoformat(time_str)


def parse_filename(filename: str) -> tuple[str, str, str | None] | None:
    """
    Parse a PhoneTrack GPX filename.
    
    Returns: (session_name, username, date_str) or None if not parseable.
    date_str is None for full exports.
    """
    # Skip timeline files
    if '_TIMELINE.gpx' in filename:
        return None
    
    # Try daily export pattern first
    match = DAILY_PATTERN.match(filename)
    if match:
        session_name = match.group(1)
        date_str = match.group(2)
        username = match.group(3)
        return (session_name, username, date_str)
    
    # Try full export pattern
    match = FULL_PATTERN.match(filename)
    if match:
        session_name = match.group(1)
        username = match.group(2)
        # Skip if it looks like a special file
        if username.lower() in ['timeline', 'merged', 'combined']:
            return None
        return (session_name, username, None)
    
    return None


def collect_track_points(file_path: Path) -> list[tuple[datetime, ET.Element]]:
    """Collect all track points from a GPX file with their timestamps."""
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        points = []
        
        for trkpt in root.findall('.//{%s}trkpt' % GPX_NS):
            time_elem = trkpt.find('{%s}time' % GPX_NS)
            if time_elem is not None and time_elem.text:
                try:
                    ts = parse_timestamp(time_elem.text)
                    # Skip year 2000 entries (clock not set bug)
                    if ts.year == 2000:
                        continue
                    points.append((ts, copy.deepcopy(trkpt)))
                except ValueError:
                    pass
        
        return points
    except Exception as e:
        print(f"  Warning: Could not parse {file_path}: {e}")
        return []


def write_gpx(points: list[tuple[datetime, ET.Element]], 
              output_path: Path,
              session_name: str,
              username: str) -> None:
    """Write points to a GPX file with full PhoneTrack structure."""
    export_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    
    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>',
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" '
        'xmlns:gpxx="http://www.garmin.com/xmlschemas/GpxExtensions/v3" '
        'xmlns:wptx1="http://www.garmin.com/xmlschemas/WaypointExtension/v1" '
        'xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1" '
        'creator="PhoneTrack Timeline Merger" version="1.1" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd '
        'http://www.garmin.com/xmlschemas/GpxExtensions/v3 http://www8.garmin.com/xmlschemas/GpxExtensionsv3.xsd '
        'http://www.garmin.com/xmlschemas/WaypointExtension/v1 http://www8.garmin.com/xmlschemas/WaypointExtensionv1.xsd '
        'http://www.garmin.com/xmlschemas/TrackPointExtension/v1 http://www.garmin.com/xmlschemas/TrackPointExtensionv1.xsd">',
        '<metadata>',
        f' <time>{export_time}</time>',
        f' <name>{session_name}</name>',
        '</metadata>',
        '<trk>',
        f' <name>{username}</name>',
        ' <trkseg>',
    ]

    for ts, pt in points:
        lat = pt.get('lat')
        lon = pt.get('lon')
        lines.append(f'  <trkpt lat="{lat}" lon="{lon}">')
        
        # Time
        time_elem = pt.find('{%s}time' % GPX_NS)
        if time_elem is not None:
            lines.append(f'   <time>{time_elem.text}</time>')
        
        # Elevation
        ele = pt.find('{%s}ele' % GPX_NS)
        if ele is not None and ele.text:
            lines.append(f'   <ele>{ele.text}</ele>')
        
        # Satellites
        sat = pt.find('{%s}sat' % GPX_NS)
        if sat is not None and sat.text:
            lines.append(f'   <sat>{sat.text}</sat>')
        
        # Extensions
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

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def scan_and_group_files(source_dir: Path) -> dict[tuple[str, str], tuple[str, str, list[Path]]]:
    """
    Scan directory recursively for GPX files and group by (session, username).
    Uses normalized (accent-stripped, lowercased) names for grouping.
    
    Returns dict with:
        key: (normalized_session, normalized_username)
        value: (first_original_session, first_original_username, list_of_files)
    """
    # Temporary storage: key -> (original_names, files)
    temp_groups: dict[tuple[str, str], tuple[str, str, list[Path]]] = {}
    
    for gpx_file in source_dir.rglob('*.gpx'):
        parsed = parse_filename(gpx_file.name)
        if parsed:
            session_name, username, date_str = parsed
            # Normalize for grouping (strips accents + lowercase)
            norm_session = normalize_text(session_name).lower()
            norm_username = normalize_text(username).lower()
            key = (norm_session, norm_username)
            
            if key not in temp_groups:
                # First file for this group - use its original names
                temp_groups[key] = (session_name, username, [gpx_file])
            else:
                # Add to existing group
                temp_groups[key][2].append(gpx_file)
    
    return temp_groups


def merge_group(files: list[Path], 
                output_path: Path,
                session_name: str,
                username: str,
                existing_timeline: Path | None = None) -> int:
    """
    Merge all GPX files in a group into a single timeline.
    
    Returns the number of unique points in the merged timeline.
    """
    all_points = []
    
    # Load existing timeline if it exists
    if existing_timeline and existing_timeline.exists():
        print(f"    Loading existing timeline: {existing_timeline.name}")
        points = collect_track_points(existing_timeline)
        all_points.extend(points)
        print(f"      {len(points)} existing points")
    
    # Load all source files
    for gpx_file in files:
        points = collect_track_points(gpx_file)
        if points:
            print(f"    {gpx_file.name}: {len(points)} points")
            all_points.extend(points)
    
    if not all_points:
        return 0
    
    # Remove duplicates
    seen = set()
    unique = []
    for ts, pt in all_points:
        key = (pt.get('lat'), pt.get('lon'), ts.isoformat())
        if key not in seen:
            seen.add(key)
            unique.append((ts, pt))
    
    # Sort by timestamp
    unique.sort(key=lambda x: x[0])
    
    # Write output
    write_gpx(unique, output_path, session_name, username)
    
    return len(unique)


def main():
    parser = argparse.ArgumentParser(
        description='Auto-merge PhoneTrack GPX exports into timeline files'
    )
    parser.add_argument(
        'source_dir',
        type=Path,
        help='Source directory containing GPX files (scanned recursively)'
    )
    parser.add_argument(
        '-o', '--output-dir',
        type=Path,
        default=None,
        help='Output directory for timeline files (default: source_dir/Timelines)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually merging'
    )
    parser.add_argument(
        '--include-existing',
        action='store_true',
        help='Include existing timeline files when merging (useful for incremental updates)'
    )
    
    args = parser.parse_args()
    
    source_dir = args.source_dir.resolve()
    if not source_dir.exists():
        print(f"Error: Source directory does not exist: {source_dir}")
        return 1
    
    output_dir = args.output_dir or (source_dir / 'Timelines')
    
    print(f"Scanning: {source_dir}")
    print(f"Output:   {output_dir}")
    print()
    
    # Scan and group files
    groups = scan_and_group_files(source_dir)
    
    if not groups:
        print("No PhoneTrack GPX files found.")
        return 0
    
    print(f"Found {len(groups)} session/user combinations:\n")
    
    # Process each group
    total_files = 0
    total_points = 0
    
    for (norm_session, norm_username), (session_name, username, files) in sorted(groups.items()):
        # Use normalized names for the output filename (without accents)
        clean_session = normalize_text(session_name)
        clean_username = normalize_text(username)
        output_filename = f"{clean_session}_{clean_username}_TIMELINE.gpx"
        output_path = output_dir / output_filename
        
        print(f"[{session_name}] - {username}")
        print(f"  Files: {len(files)}")
        print(f"  Output: {output_filename}")
        
        if args.dry_run:
            for f in sorted(files):
                print(f"    - {f.name}")
            print()
            continue
        
        # Check for existing timeline
        existing = output_path if args.include_existing else None
        
        # Merge
        num_points = merge_group(files, output_path, session_name, username, existing)
        
        print(f"  Total unique points: {num_points}")
        print()
        
        total_files += len(files)
        total_points += num_points
    
    if not args.dry_run:
        print("=" * 50)
        print(f"Summary: Processed {total_files} files into {len(groups)} timelines")
        print(f"         Total points: {total_points}")
    
    return 0


if __name__ == '__main__':
    exit(main())
