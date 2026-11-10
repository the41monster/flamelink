import json
import importlib.resources
import pytest
from jsonschema import Draft202012Validator, ValidationError

from flamelink.hotspot import pyspy_hotspots

SCHEMA = json.loads(
    (importlib.resources.files("flamelink") / "schemas" / "report.schema.json").read_text(encoding="utf-8")
)

HOTSPOTS_SCHEMA = {**SCHEMA["properties"]["hotspots"], "$defs": SCHEMA["$defs"]}
HOTSPOTS_VALIDATOR = Draft202012Validator(HOTSPOTS_SCHEMA)

# 10 samples: all -> main -> {fib -> fib (recursive), idle}
PYSPY_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" xmlns:fg="http://github.com/jonhoo/inferno">
    <g><title>all (10 samples, 100%)</title><rect x="0%" y="0" width="100%" fg:x="0" fg:w="10"/></g>
    <g><title>main (app.py:1) (10 samples, 100.00%)</title><rect x="0%" y="16" width="100%" fg:x="0" fg:w="10"/></g>
    <g><title>fib (app.py:5) (8 samples, 80.00%)</title><rect x="0%" y="32" width="80%" fg:x="0" fg:w="8"/></g>
    <g><title>fib (app.py:5) (6 samples, 60.00%)</title><rect x="0%" y="48" width="60%" fg:x="0" fg:w="6"/></g>
    <g><title>idle (app.py:9) (2 samples, 20.00%)</title><rect x="0%" y="32" width="20%" fg:x="8" fg:w="2"/></g>
</svg>
"""


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
    assert hotspots == [
        {"fn": "fib",  "file": "app.py", "line": 5, "self_pct": 80.0, "total_pct": 80.0},
        {"fn": "idle", "file": "app.py", "line": 9, "self_pct": 20.0, "total_pct": 20.0},
        {"fn": "main", "file": "app.py", "line": 1, "self_pct": 0.0,  "total_pct": 100.0},
    ]
    validate_hotspots(hotspots)
