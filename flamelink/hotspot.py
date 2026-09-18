import re
import xml.etree.ElementTree as ET

from collections import defaultdict, Counter

def parse_frames(svg_path: str) -> list[dict]:
    tree = ET.parse(svg_path)
    root = tree.getroot()

    ns_match = re.match(r'\{.*\}', root.tag)
    ns = ns_match.group(0) if ns_match else ''

    def tag(name: str) -> str:
        return f"{ns}{name}"

    frames = []

    for g in root.iter(tag('g')):
        title_el = g.find(tag('title'))
        rect_el = g.find(tag('rect'))

        if title_el is None or rect_el is None or not title_el.text:
            continue

        name = title_el.text.split('(', 1)[0].strip()
        x = float(rect_el.get('x', '0').rstrip('%'))
        width = float(rect_el.get('width', '0').rstrip('%'))
        y = float(rect_el.get('y', '0').rstrip('%'))

        frames.append({
            'name': name,
            'x': x,
            'width': width,
            'y': y
        })
    
    return frames


def rank_hotspots(frames: list[dict]) -> list[dict]:
    levels = defaultdict(list)
    for frame in frames:
        levels[frame['y']].append(frame)

    depth_ordering = sorted(levels.items())

    for _, level_frames in depth_ordering:
        level_frames.sort(key=lambda f: f['x'])

    for i in range(len(depth_ordering)-1):
        _, level_frames = depth_ordering[i]
        _, next_level_frames = depth_ordering[i + 1]
        last_index = 0
        for frame in level_frames:
            x0 = frame['x']
            x1 = frame['x'] + frame['width']
            child_frames = []
            for child_frame in next_level_frames[last_index:]:
                if (child_frame['x'] >= x0 and
                    child_frame['x'] + child_frame['width'] <= x1):
                    child_frames.append(child_frame)
                    last_index += 1
                else:
                    break
            frame['children'] = child_frames

    self_times = Counter()
    for frame in frames:
        self_time = frame['width']
        for child in frame.get('children', []):
            self_time -= child['width']
        self_times[frame['name']] += self_time

    sorted_frames = sorted(self_times.items(), key=lambda item: item[1], reverse=True)
    sorted_frames = [{'name': name, 'self_time': self_time} for name, self_time in sorted_frames]
    return sorted_frames
