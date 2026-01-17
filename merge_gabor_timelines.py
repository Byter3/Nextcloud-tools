#!/usr/bin/env python3
"""Merge the earlier Gabor timeline into the new one."""

import xml.etree.ElementTree as ET
from datetime import datetime
import copy

GPX_NS = 'http://www.topografix.com/GPX/1/1'

def parse_timestamp(time_str):
    if 'Z' in time_str:
        return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    return datetime.fromisoformat(time_str)

def collect_track_points(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    points = []
    for trkpt in root.findall('.//{%s}trkpt' % GPX_NS):
        time_elem = trkpt.find('{%s}time' % GPX_NS)
        if time_elem is not None and time_elem.text:
            try:
                ts = parse_timestamp(time_elem.text)
                if ts.year == 2000:  # Skip year 2000 bug
                    continue
                points.append((ts, copy.deepcopy(trkpt)))
            except:
                pass
    return points

def write_gpx(points, output_path, session_name, username):
    export_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>',
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:gpxx="http://www.garmin.com/xmlschemas/GpxExtensions/v3" xmlns:wptx1="http://www.garmin.com/xmlschemas/WaypointExtension/v1" xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1" creator="PhoneTrack Timeline Merger" version="1.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd http://www.garmin.com/xmlschemas/GpxExtensions/v3 http://www8.garmin.com/xmlschemas/GpxExtensionsv3.xsd http://www.garmin.com/xmlschemas/WaypointExtension/v1 http://www8.garmin.com/xmlschemas/WaypointExtensionv1.xsd http://www.garmin.com/xmlschemas/TrackPointExtension/v1 http://www.garmin.com/xmlschemas/TrackPointExtensionv1.xsd">',
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

# File paths
earlier_file = 'GPXs/Pifi Mifi Day to Day_Gabor_TIMELINE.gpx'
new_file = 'GPXs/nextcloud/PhoneTrack_export/Timelines/Pifi Mifi DAY to DAY_Gabor_TIMELINE.gpx'

print(f'Reading earlier timeline: {earlier_file}')
earlier_points = collect_track_points(earlier_file)
print(f'  Points: {len(earlier_points)}')
if earlier_points:
    earlier_points.sort(key=lambda x: x[0])
    print(f'  Date range: {earlier_points[0][0]} to {earlier_points[-1][0]}')

print(f'\nReading new timeline: {new_file}')
new_points = collect_track_points(new_file)
print(f'  Points: {len(new_points)}')
if new_points:
    new_points.sort(key=lambda x: x[0])
    print(f'  Date range: {new_points[0][0]} to {new_points[-1][0]}')

# Combine
all_points = earlier_points + new_points
print(f'\nTotal before dedup: {len(all_points)}')

# Deduplicate
seen = set()
unique = []
for ts, pt in all_points:
    key = (pt.get('lat'), pt.get('lon'), ts.isoformat())
    if key not in seen:
        seen.add(key)
        unique.append((ts, pt))

print(f'After dedup: {len(unique)}')

# Sort
unique.sort(key=lambda x: x[0])

# Write
write_gpx(unique, new_file, 'Pifi Mifi DAY to DAY', 'Gabor')

print(f'\nUpdated: {new_file}')
print(f'Final date range: {unique[0][0]} to {unique[-1][0]}')
