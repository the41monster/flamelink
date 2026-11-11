import json
from datetime import datetime, timezone
from importlib.resources import files
from jsonschema import Draft202012Validator, ValidationError

from flamelink.load import calculate_percentiles

SCHEMA = json.loads(
    (files("flamelink") / "schemas" / "report.schema.json").read_text(encoding="utf-8")
)
SCHEMA_VALIDATOR = Draft202012Validator(SCHEMA)


class ReportError(Exception):
    """Custom exception for report-related errors."""
    pass


def build_report(target: str, duration_s: int, times: list[float], sampler: str | None = None, hotspots: list[dict] | None = None) -> dict:
    percentiles = calculate_percentiles(times)
    hotspots = hotspots if hotspots is not None else []
    report = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "target": target,
        "duration_s": duration_s,
        "sampler": sampler,
        "p50_ms": percentiles["p50"],
        "p95_ms": percentiles["p95"],
        "p99_ms": percentiles["p99"],
        "hotspots": hotspots
    }
    return report


def load_report(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            report = json.load(f)
    except json.JSONDecodeError as e:
        raise ReportError(f"Invalid JSON in report file {path} at line {e.lineno}, column {e.colno}. Error: {e.msg}") from e
    except OSError as e:
        raise ReportError(f"Cannot read report file {path}: {e.strerror}") from e
    try:
        SCHEMA_VALIDATOR.validate(report)
    except ValidationError as e:
        raise ReportError(f"{path} is not a valid flamelink report: {e.message} (at {e.json_path})") from e
    return report
