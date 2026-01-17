#!/usr/bin/env python3
"""
Merge daily GPX exports into the main timeline file.
Preserves full PhoneTrack structure and removes duplicates.
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
import copy
import glob

GPX_NS = 'http://www.topografix.com/GPX/1/1'

def parse_timestamp(time_str):
    if 'Z' in time_str:
        return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    return datetime.fromisoformat(time_str)

def collect_track_points(file_path):
    """Collect all track points from a GPX file."""
    tree = ET.parse(file_path)
    root = tree.getroot()
    points = []
    for trkpt in root.findall('.//{%s}trkpt' % GPX_NS):
        time_elem = trkpt.find('{%s}time' % GPX_NS)
        if time_elem is not None and time_elem.text:
            try:
                ts = parse_timestamp(time_elem.text)
                points.append((ts, copy.deepcopy(trkpt)))
            except:
                pass
    return points

def write_gpx(points, output_path):
    """Write points to a GPX file with full PhoneTrack structure."""
    export_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>',
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:gpxx="http://www.garmin.com/xmlschemas/GpxExtensions/v3" xmlns:wptx1="http://www.garmin.com/xmlschemas/WaypointExtension/v1" xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1" creator="PhoneTrack Nextcloud app 0.9.1" version="1.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd http://www.garmin.com/xmlschemas/GpxExtensions/v3 http://www8.garmin.com/xmlschemas/GpxExtensionsv3.xsd http://www.garmin.com/xmlschemas/WaypointExtension/v1 http://www8.garmin.com/xmlschemas/WaypointExtensionv1.xsd http://www.garmin.com/xmlschemas/TrackPointExtension/v1 http://www.garmin.com/xmlschemas/TrackPointExtensionv1.xsd">',
        '<metadata>',
        f' <time>{export_time}</time>',
        ' <name>Pifi Mifi Day to Day</name>',
        '</metadata>',
        '<trk>',
        ' <name>Gabor</name>',
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

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


# Main script
timeline_file = 'GPXs/Pifi Mifi Day to Day_Gabor_TIMELINE.gpx'
daily_folder = 'GPXs/sources/daily exports'

# Read existing timeline
print(f'Reading timeline: {timeline_file}')
all_points = collect_track_points(timeline_file)
print(f'  Found {len(all_points)} track points')
if all_points:
    all_points.sort(key=lambda x: x[0])
    print(f'  Date range: {all_points[0][0]} to {all_points[-1][0]}')

# Read all daily exports
daily_files = sorted(glob.glob(f'{daily_folder}/*.gpx'))
print(f'\nFound {len(daily_files)} daily export files:')

for daily_file in daily_files:
    points = collect_track_points(daily_file)
    print(f'  {Path(daily_file).name}: {len(points)} points')
    all_points.extend(points)

print(f'\nTotal points before dedup: {len(all_points)}')

# Remove duplicates
seen = set()
unique = []
for ts, pt in all_points:
    key = (pt.get('lat'), pt.get('lon'), ts.isoformat())
    if key not in seen:
        seen.add(key)
        unique.append((ts, pt))

print(f'After dedup: {len(unique)}')

# Sort by time
unique.sort(key=lambda x: x[0])

# Write output
write_gpx(unique, timeline_file)

print(f'\nUpdated: {timeline_file}')
print(f'Final date range: {unique[0][0]} to {unique[-1][0]}')
