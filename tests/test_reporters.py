import json

import pytest
from jsonschema import Draft202012Validator, ValidationError

from flamelink.hotspot import pyspy_hotspots, clinic_hotspots
from flamelink.report import build_report, load_report, ReportError, SCHEMA

# format_checker makes "format": "date-time" on timestamp an actual check (needs rfc3339-validator)
REPORT_VALIDATOR = Draft202012Validator(SCHEMA, format_checker=Draft202012Validator.FORMAT_CHECKER)

HOTSPOTS_SCHEMA = {**SCHEMA["properties"]["hotspots"], "$defs": SCHEMA["$defs"]}
HOTSPOTS_VALIDATOR = Draft202012Validator(HOTSPOTS_SCHEMA)

# 10 samples: all -> main -> {fib -> fib (recursive), idle}
PYSPY_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" xmlns:fg="http://github.com/jonhoo/inferno">
    <g><title>all (10 samples, 100%)</title><rect x="0%" y="0" width="100%" fg:x="0" fg:w="10"/></g>
    <g><title>main (app.py:1) (10 samples, 100.00%)</title><rect x="0%" y="16" width="100%" fg:x="0" fg:w="10"/></g>
    <g><title>fib (app.py:5) (8 samples, 80.00%)</title><rect x="0%" y="32" width="80%" fg:x="0" fg:w="8"/></g>
    <g><title>fib (app.py:5) (6 samples, 60.00%)</title><rect x="0%" y="48" width="60%" fg:x="0" fg:w="6"/></g>
    <g><title>idle (app.py:9) (2 samples, 20.00%)</title><rect x="80%" y="32" width="20%" fg:x="8" fg:w="2"/></g>
</svg>
"""

# Same tree, but idle's x percentage is off by 0.0001, as py-spy's 4-decimal rounding can produce.
# By percentages idle ends at 100.0001%, past main's right edge, so a percentage-based parser
# would find no parent for it. The fg:x/fg:w sample counts are still exact.
PYSPY_SVG_ROUNDED = """\
<svg xmlns="http://www.w3.org/2000/svg" xmlns:fg="http://github.com/jonhoo/inferno">
    <g><title>all (10 samples, 100%)</title><rect x="0%" y="0" width="100%" fg:x="0" fg:w="10"/></g>
    <g><title>main (app.py:1) (10 samples, 100.00%)</title><rect x="0%" y="16" width="100%" fg:x="0" fg:w="10"/></g>
    <g><title>fib (app.py:5) (8 samples, 80.00%)</title><rect x="0%" y="32" width="80%" fg:x="0" fg:w="8"/></g>
    <g><title>fib (app.py:5) (6 samples, 60.00%)</title><rect x="0%" y="48" width="60%" fg:x="0" fg:w="6"/></g>
    <g><title>idle (app.py:9) (2 samples, 20.00%)</title><rect x="80.0001%" y="32" width="20%" fg:x="8" fg:w="2"/></g>
</svg>
"""

PYSPY_EXPECTED = [
    {"fn": "fib",  "file": "app.py", "line": 5, "self_pct": 80.0, "total_pct": 80.0},
    {"fn": "idle", "file": "app.py", "line": 9, "self_pct": 20.0, "total_pct": 20.0},
    {"fn": "main", "file": "app.py", "line": 1, "self_pct": 0.0,  "total_pct": 100.0},
]

# 10 samples: root -> (anonymous) -> {fib -> fib (recursive), [SHARED_LIB] -> syscall}
# Every node satisfies value == onStackTop.base + sum(children values), like real clinic data
CLINIC_HTML = """\
<html><script>var data = {"merged":{
  "value": 10, "onStackTop": {"base": 0}, "children": [
    {"functionName": "(anonymous)", "fileName": "./server.js", "lineNumber": 7,
     "value": 10, "onStackTop": {"base": 0}, "children": [
      {"functionName": "fib", "fileName": "./utils.js", "lineNumber": 1,
       "value": 7, "onStackTop": {"base": 2}, "children": [
        {"functionName": "fib", "fileName": "./utils.js", "lineNumber": 1,
         "value": 5, "onStackTop": {"base": 5}, "children": []}
      ]},
      {"functionName": "[SHARED_LIB]", "fileName": "/usr/bin/node", "lineNumber": null,
       "value": 3, "onStackTop": {"base": 2}, "children": [
        {"functionName": "syscall", "fileName": null, "lineNumber": null,
         "value": 1, "onStackTop": {"base": 1}, "children": []}
      ]}
    ]}
  ]
}}</script></html>
"""


def validate_report(report):
    REPORT_VALIDATOR.validate(report)  # Raises ValidationError if invalid


def validate_hotspots(rows):
    HOTSPOTS_VALIDATOR.validate(rows)  # Raises ValidationError if invalid


def test_validate_hotspots_accepts_valid_and_rejects_invalid():
    valid_rows = [
        {
            "fn": "fib",
            "file": "./utils.js",
            "line": 10,
            "self_pct": 50.0,
            "total_pct": 75.0
        },
        {
            "fn": "main",
            "file": "./server.js",
            "line": 5,
            "self_pct": 25.0,
            "total_pct": 100.0
        }
    ]

    # Each invalid row is paired with the schema keyword that should reject it
    invalid_rows = [
        ("maximum", {
            "fn": "fib",
            "file": "./utils.js",
            "line": 10,
            "self_pct": 50.0,
            "total_pct": 125.0
        }),
        ("required", {
            "fn": "main",
            "file": "./server.js",
            "self_pct": 25.0,
            "total_pct": 100.0
        }),
    ]

    # Validate valid rows (should not raise)
    validate_hotspots(valid_rows)

    # Validate invalid rows (should raise)
    for expected_validator, row in invalid_rows:
        with pytest.raises(ValidationError) as exc_info:
            validate_hotspots([row])
        assert exc_info.value.validator == expected_validator



def test_schema_file():
    Draft202012Validator.check_schema(SCHEMA)  # Raises SchemaError if invalid


def test_pyspy_hotspots_small_tree(tmp_path):
    svg_path = tmp_path / "profile.svg"
    svg_path.write_text(PYSPY_SVG)

    hotspots = pyspy_hotspots(str(svg_path))
    assert hotspots == PYSPY_EXPECTED
    validate_hotspots(hotspots)


def test_pyspy_hotspots_ignore_rounded_percentages(tmp_path):
    # Regression: parsing x/width percentages made self time sum to 591% on a real profile.
    svg_path = tmp_path / "profile.svg"
    svg_path.write_text(PYSPY_SVG_ROUNDED)

    hotspots = pyspy_hotspots(str(svg_path))
    assert hotspots == PYSPY_EXPECTED
    validate_hotspots(hotspots)


def test_clinic_hotspots_small_tree(tmp_path):
    html_path = tmp_path / "report.html"
    html_path.write_text(CLINIC_HTML)

    hotspots = clinic_hotspots(str(html_path))
    assert hotspots == [
        {"fn": "fib",  "file": "./utils.js", "line": 1, "self_pct": 70.0, "total_pct": 70.0},
        {"fn": "[SHARED_LIB]", "file": "/usr/bin/node", "line": None, "self_pct": 20.0, "total_pct": 30.0},
        {"fn": "syscall", "file": None, "line": None, "self_pct": 10.0, "total_pct": 10.0},
        {"fn": "(anonymous)", "file": "./server.js", "line": 7, "self_pct": 0.0, "total_pct": 100.0},
    ]
    validate_hotspots(hotspots)


def test_build_report_load_only():
    report = build_report(
        target="http://localhost:8000/fib",
        duration_s=10,
        times=[10.0, 20.0, 30.0]
    )
    validate_report(report)
    assert report["sampler"] is None
    assert report["hotspots"] == []
    assert report["p50_ms"] == 20.0
    assert report["p95_ms"] == 30.0
    assert report["p99_ms"] == 30.0


def test_build_report_no_successful_requests():
    report = build_report(
        target="http://localhost:8000/fib",
        duration_s=10,
        times=[]
    )
    validate_report(report)
    assert report["p50_ms"] is None
    assert report["p95_ms"] is None
    assert report["p99_ms"] is None


def test_build_report_with_pyspy_hotspots():
    report = build_report(
        target="http://localhost:8000/fib",
        duration_s=10,
        times=[10.0, 20.0, 30.0],
        sampler="py-spy",
        hotspots=PYSPY_EXPECTED
    )
    validate_report(report)
    assert report["sampler"] == "py-spy"
    assert report["hotspots"] == PYSPY_EXPECTED


def test_build_report_rejects_bad_timestamp():
    report = build_report(
        target="http://localhost:8000/fib",
        duration_s=10,
        times=[10.0, 20.0, 30.0]
    )
    report["timestamp"] = "not a timestamp"
    with pytest.raises(ValidationError) as exc_info:
        validate_report(report)
    assert exc_info.value.validator == "format"


def test_load_report_returns_valid_report(tmp_path):
    report = build_report(
        target="http://localhost:8000/fib",
        duration_s=10,
        times=[10.0, 20.0, 30.0],
        sampler="py-spy",
        hotspots=PYSPY_EXPECTED,
    )
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report))

    assert load_report(str(path)) == report


def test_load_report_missing_file(tmp_path):
    with pytest.raises(ReportError, match="Cannot read"):
        load_report(str(tmp_path / "missing.json"))


def test_load_report_not_json(tmp_path):
    path = tmp_path / "report.json"
    path.write_text("{not json")

    with pytest.raises(ReportError, match="Invalid JSON"):
        load_report(str(path))


def test_load_report_rejects_feature2_report(tmp_path):
    # The old load-report shape: target_url instead of target, no sampler or hotspots
    path = tmp_path / "report.json"
    path.write_text(json.dumps({
        "timestamp": "2026-09-16T12:00:00+00:00",
        "target_url": "http://localhost:8000/fib",
        "rps": 10,
        "duration_s": 10,
        "p50_ms": 20.0,
        "p95_ms": 30.0,
        "p99_ms": 30.0,
        "sample_count": 3,
        "errors": {},
    }))

    with pytest.raises(ReportError, match="not a valid flamelink report"):
        load_report(str(path))
