#!/usr/bin/env python3
"""Remove year 2000 entries from the merged GPX file."""

import xml.etree.ElementTree as ET
from datetime import datetime
import copy

GPX_NS = 'http://www.topografix.com/GPX/1/1'

def parse_timestamp(time_str):
    if 'Z' in time_str:
        return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    return datetime.fromisoformat(time_str)

def collect_track_points(file_path, skip_year_2000=False):
    tree = ET.parse(file_path)
    root = tree.getroot()
    points = []
    skipped = 0
    for trkpt in root.findall('.//{%s}trkpt' % GPX_NS):
        time_elem = trkpt.find('{%s}time' % GPX_NS)
        if time_elem is not None and time_elem.text:
            try:
                ts = parse_timestamp(time_elem.text)
                if skip_year_2000 and ts.year == 2000:
                    skipped += 1
                    continue
                points.append((ts, copy.deepcopy(trkpt)))
            except:
                pass
    return points, skipped

print('Reading file 1 (skipping year 2000 entries)...')
points1, skipped1 = collect_track_points('GPXs/sources/DAYtoDAY_AG_Phone.gpx', skip_year_2000=True)
print(f'  Found {len(points1)} track points (skipped {skipped1} year 2000 entries)')

print('Reading file 2...')
points2, _ = collect_track_points('GPXs/sources/Pifi Mifi Day to Day_Gabor.gpx')
print(f'  Found {len(points2)} track points')

all_points = points1 + points2
print(f'Total: {len(all_points)}')

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

# Build output
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

for ts, pt in unique:
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

with open('GPXs/Pifi Mifi Day to Day_Gabor_TIMELINE.gpx', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print(f'\nSaved to GPXs/Pifi Mifi Day to Day_Gabor_TIMELINE.gpx')
print(f'Date range: {unique[0][0]} to {unique[-1][0]}')
