from flamelink.load import calculate_percentiles
from datetime import datetime, timezone


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
