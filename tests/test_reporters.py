import json
import importlib.resources
import pytest
from jsonschema import Draft202012Validator, ValidationError

SCHEMA = json.loads(
    (importlib.resources.files("flamelink") / "schemas" / "report.schema.json").read_text(encoding="utf-8")
)

HOTSPOTS_SCHEMA = {**SCHEMA["properties"]["hotspots"], "$defs": SCHEMA["$defs"]}
HOTSPOTS_VALIDATOR = Draft202012Validator(HOTSPOTS_SCHEMA)


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
