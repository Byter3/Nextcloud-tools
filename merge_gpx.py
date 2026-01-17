#!/usr/bin/env python3
"""
GPX Merger Script for Nextcloud PhoneTrack exports.
Merges two GPX files while preserving the COMPLETE original structure
including all extensions (speed, course, accuracy, batterylevel, useragent, sat).
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
import argparse
import sys
import copy

# GPX namespace
GPX_NS = 'http://www.topografix.com/GPX/1/1'
NAMESPACES = {
    'gpx': GPX_NS,
    'gpxx': 'http://www.garmin.com/xmlschemas/GpxExtensions/v3',
    'wptx1': 'http://www.garmin.com/xmlschemas/WaypointExtension/v1',
    'gpxtpx': 'http://www.garmin.com/xmlschemas/TrackPointExtension/v1'
}

def register_namespaces():
    """Register all namespaces to preserve them in output."""
    ET.register_namespace('', GPX_NS)
    ET.register_namespace('gpxx', 'http://www.garmin.com/xmlschemas/GpxExtensions/v3')
    ET.register_namespace('wptx1', 'http://www.garmin.com/xmlschemas/WaypointExtension/v1')
    ET.register_namespace('gpxtpx', 'http://www.garmin.com/xmlschemas/TrackPointExtension/v1')
    ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')


def parse_timestamp(time_str: str) -> datetime:
    """Parse ISO format timestamp from GPX."""
    if 'Z' in time_str:
        return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    return datetime.fromisoformat(time_str)


def get_trkpt_time(trkpt) -> datetime | None:
    """Extract timestamp from a track point element."""
    time_elem = trkpt.find('gpx:time', {'gpx': GPX_NS})
    if time_elem is not None and time_elem.text:
        try:
            return parse_timestamp(time_elem.text)
        except ValueError:
            return None
    return None


def collect_track_points(file_path: str) -> list[tuple[datetime, ET.Element]]:
    """
    Parse a GPX file and collect all track points with their timestamps.
    Returns list of (timestamp, element) tuples preserving the full element structure.
    """
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    points = []
    for trkpt in root.findall('.//gpx:trkpt', {'gpx': GPX_NS}):
        timestamp = get_trkpt_time(trkpt)
        if timestamp:
            # Deep copy to preserve all child elements
            points.append((timestamp, copy.deepcopy(trkpt)))
    
    return points


def fix_year_2000_timestamps(points: list[tuple[datetime, ET.Element]], new_year: int = 2019):
    """
    Fix track points with year 2000 timestamps by changing them to the specified year.
    Modifies elements in place.
    """
    fixed_count = 0
    for i, (timestamp, trkpt) in enumerate(points):
        if timestamp.year == 2000:
            new_timestamp = timestamp.replace(year=new_year)
            time_elem = trkpt.find('gpx:time', {'gpx': GPX_NS})
            if time_elem is not None:
                # Preserve original format (with Z suffix)
                time_elem.text = new_timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
            points[i] = (new_timestamp, trkpt)
            fixed_count += 1
    return fixed_count


def remove_namespace_prefix(elem):
    """Remove namespace prefixes from element tags for cleaner output."""
    if elem.tag.startswith('{'):
        elem.tag = elem.tag.split('}', 1)[1]
    for child in elem:
        remove_namespace_prefix(child)


def create_merged_gpx(points: list[tuple[datetime, ET.Element]], 
                      session_name: str = "Pifi Mifi Day to Day",
                      device_name: str = "Gabor") -> str:
    """
    Create a merged GPX file matching the original PhoneTrack structure.
    Returns the GPX content as a string.
    """
    # Sort points by timestamp
    sorted_points = sorted(points, key=lambda p: p[0])
    
    # Get current time for metadata
    export_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    
    # Build GPX header matching PhoneTrack format
    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>',
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" '
        'xmlns:gpxx="http://www.garmin.com/xmlschemas/GpxExtensions/v3" '
        'xmlns:wptx1="http://www.garmin.com/xmlschemas/WaypointExtension/v1" '
        'xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1" '
        'creator="PhoneTrack Nextcloud app 0.9.1" version="1.1" '
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
        f' <name>{device_name}</name>',
        ' <trkseg>',
    ]
    
    # Add each track point
    for timestamp, trkpt in sorted_points:
        lat = trkpt.get('lat')
        lon = trkpt.get('lon')
        
        lines.append(f'  <trkpt lat="{lat}" lon="{lon}">')
        
        # Add time element
        time_elem = trkpt.find('gpx:time', {'gpx': GPX_NS})
        if time_elem is not None and time_elem.text:
            lines.append(f'   <time>{time_elem.text}</time>')
        
        # Add elevation
        ele_elem = trkpt.find('gpx:ele', {'gpx': GPX_NS})
        if ele_elem is not None and ele_elem.text:
            lines.append(f'   <ele>{ele_elem.text}</ele>')
        
        # Add satellites
        sat_elem = trkpt.find('gpx:sat', {'gpx': GPX_NS})
        if sat_elem is not None and sat_elem.text:
            lines.append(f'   <sat>{sat_elem.text}</sat>')
        
        # Add extensions block if present
        ext_elem = trkpt.find('gpx:extensions', {'gpx': GPX_NS})
        if ext_elem is not None:
            lines.append('   <extensions>')
            
            # Speed
            speed = ext_elem.find('gpx:speed', {'gpx': GPX_NS})
            if speed is not None and speed.text:
                lines.append(f'     <speed>{speed.text}</speed>')
            
            # Course
            course = ext_elem.find('gpx:course', {'gpx': GPX_NS})
            if course is not None and course.text:
                lines.append(f'     <course>{course.text}</course>')
            
            # Accuracy
            accuracy = ext_elem.find('gpx:accuracy', {'gpx': GPX_NS})
            if accuracy is not None and accuracy.text:
                lines.append(f'     <accuracy>{accuracy.text}</accuracy>')
            
            # Battery level
            battery = ext_elem.find('gpx:batterylevel', {'gpx': GPX_NS})
            if battery is not None and battery.text:
                lines.append(f'     <batterylevel>{battery.text}</batterylevel>')
            
            # User agent
            useragent = ext_elem.find('gpx:useragent', {'gpx': GPX_NS})
            if useragent is not None and useragent.text:
                lines.append(f'     <useragent>{useragent.text}</useragent>')
            
            lines.append('   </extensions>')
        
        lines.append('  </trkpt>')
    
    # Close tags
    lines.extend([
        ' </trkseg>',
        '</trk>',
        '</gpx>'
    ])
    
    return '\n'.join(lines)


def merge_gpx_files(file1: str, file2: str, output_file: str, 
                    session_name: str = "Pifi Mifi Day to Day",
                    device_name: str = "Gabor",
                    fix_year_2000: bool = True):
    """
    Main function to merge two GPX files.
    """
    register_namespaces()
    
    print(f"Reading file 1: {file1}")
    points1 = collect_track_points(file1)
    print(f"  Found {len(points1)} track points")
    if points1:
        print(f"  Date range: {min(p[0] for p in points1)} to {max(p[0] for p in points1)}")
    
    print(f"\nReading file 2: {file2}")
    points2 = collect_track_points(file2)
    print(f"  Found {len(points2)} track points")
    if points2:
        print(f"  Date range: {min(p[0] for p in points2)} to {max(p[0] for p in points2)}")
    
    # Combine all points
    all_points = points1 + points2
    print(f"\nTotal points to merge: {len(all_points)}")
    
    # Fix year 2000 timestamps
    if fix_year_2000:
        fixed = fix_year_2000_timestamps(all_points, new_year=2019)
        if fixed > 0:
            print(f"Fixed {fixed} timestamps (2000 -> 2019)")
    
    # Remove duplicates (same timestamp and location)
    seen = set()
    unique_points = []
    duplicates = 0
    for timestamp, trkpt in all_points:
        lat = trkpt.get('lat')
        lon = trkpt.get('lon')
        time_elem = trkpt.find('gpx:time', {'gpx': GPX_NS})
        time_str = time_elem.text if time_elem is not None else str(timestamp)
        
        key = (lat, lon, time_str)
        if key not in seen:
            seen.add(key)
            unique_points.append((timestamp, trkpt))
        else:
            duplicates += 1
    
    if duplicates > 0:
        print(f"Removed {duplicates} duplicate points")
    
    print(f"Unique points: {len(unique_points)}")
    
    # Create merged GPX content
    gpx_content = create_merged_gpx(unique_points, session_name, device_name)
    
    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(gpx_content)
    
    print(f"\nMerged GPX saved to: {output_file}")
    
    if unique_points:
        sorted_points = sorted(unique_points, key=lambda p: p[0])
        print(f"Final date range: {sorted_points[0][0]} to {sorted_points[-1][0]}")


def main():
    parser = argparse.ArgumentParser(
        description='Merge two GPX files while preserving complete PhoneTrack structure'
    )
    parser.add_argument('file1', help='First GPX file (typically the older export)')
    parser.add_argument('file2', help='Second GPX file (typically the newer export)')
    parser.add_argument('-o', '--output', default='merged.gpx', 
                        help='Output file path (default: merged.gpx)')
    parser.add_argument('-s', '--session', default='Pifi Mifi Day to Day',
                        help='Session name for the merged track')
    parser.add_argument('-d', '--device', default='Gabor',
                        help='Device name for the merged track')
    parser.add_argument('--no-fix-2000', action='store_true',
                        help='Do not fix year 2000 timestamps')
    
    args = parser.parse_args()
    
    # Validate input files exist
    if not Path(args.file1).exists():
        print(f"Error: File not found: {args.file1}")
        sys.exit(1)
    if not Path(args.file2).exists():
        print(f"Error: File not found: {args.file2}")
        sys.exit(1)
    
    merge_gpx_files(
        args.file1, 
        args.file2, 
        args.output, 
        args.session,
        args.device,
        fix_year_2000=not args.no_fix_2000
    )


if __name__ == '__main__':
    main()
