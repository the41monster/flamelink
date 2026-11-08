import re
import json
import xml.etree.ElementTree as ET

from collections import defaultdict, Counter

# inferno's flamegraph attributes (fg:x, fg:w) live in this namespace
FG_NS = '{http://github.com/jonhoo/inferno}'
FG_X = f"{FG_NS}x"
FG_W = f"{FG_NS}w"
TITLE_RE = re.compile(r'^(?P<fn>.*?)(?: \((?P<file>.*):(?P<line>\d+)\))? \((?P<samples>[\d,]+) samples?, [\d.]+%\)$')


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
        fg_w = rect_el.get(FG_W)
        if fg_w is None:
            continue

        m = TITLE_RE.match(title_el.text)
        if m is None:
            raise ValueError(f"Unrecognized py-spy frame title: {title_el.text!r}")
        name = m.group('fn')
        file = m.group('file')
        line = int(m.group('line')) if m.group('line') else None
        fg_x = rect_el.get(FG_X)
        if fg_x is None:
            raise ValueError(f"Frame {name!r} has fg:w but no fg:x; the SVG is malformed")
        x = int(fg_x)
        width = int(fg_w)
        y = float(rect_el.get('y', '0').rstrip('%'))

        frames.append({
            'name': name,
            'file': file,
            'line': line,
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
        if last_index != len(next_level_frames):
            orphan = next_level_frames[last_index]
            raise ValueError(f"Frame {orphan['name']!r} at x={orphan['x']} has no parent frame")

    if not depth_ordering:
        return []

    self_times = Counter()
    total_times = Counter()

    roots = depth_ordering[0][1]
    stack = [(root, frozenset()) for root in roots]

    while stack:
        frame, keys_above = stack.pop()
        key = (frame['name'], frame['file'], frame['line'])
        children = frame.get('children', [])

        self_times[key] += frame['width'] - sum(child['width'] for child in children)

        if key not in keys_above:
            total_times[key] += frame['width']

        child_keys_above = keys_above | {key}
        for child in children:
            stack.append((child, child_keys_above))

    sorted_frames = sorted(self_times.items(), key=lambda item: item[1], reverse=True)
    sorted_frames = [
        {
            'name': name,
            'file': file,
            'line': line,
            'self_time': self_time,
            'total_time': total_times[(name, file, line)]
        }
        for (name, file, line), self_time in sorted_frames
    ]
    return sorted_frames


def read_clinic_report(html_path: str) -> str:
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return content


def parse_clinic_report(html_path: str) -> dict:
    content = read_clinic_report(html_path)
    marker = '"merged":{'
    idx = content.find(marker)
    if idx == -1:
        raise ValueError("Could not find the merged data in the clinic report.")

    start_idx = idx + len(marker) - 1
    depth = 0
    in_string = False
    escaped = False

    for i in range(start_idx, len(content)):
        ch = content[i]

        if in_string:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return json.loads(content[start_idx:i + 1])

    raise ValueError("Could not parse the merged data in the clinic report.")


def rank_clinic_hotspots(root: dict) -> list[dict]:
    self_times = Counter()
    stack = [root]
    while stack:
        node = stack.pop()
        self_times[(node["functionName"], node["fileName"], node["lineNumber"], node["category"], node["type"])] += node["onStackTop"]["base"]
        stack.extend(node.get("children", []))
    
    sorted_frames = sorted(self_times.items(), key=lambda item: item[1], reverse=True)
    sorted_frames = [{'name': name, 'file': file, 'line': line, 'category': category, 'type': type, 'self_time': self_time} for (name, file, line, category, type), self_time in sorted_frames]
    return sorted_frames
