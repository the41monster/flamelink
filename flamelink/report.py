from flamelink.load import calculate_percentiles
from datetime import datetime, timezone


def build_report(target_url: str, rps: int, duration_s: int, times: list[float], errors: int) -> dict:
    percentiles = calculate_percentiles(times)
    report = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "target_url": target_url,
        "rps": rps,
        "duration_s": duration_s,
        "p50_ms": percentiles["p50"],
        "p95_ms": percentiles["p95"],
        "p99_ms": percentiles["p99"],
        "sample_count": len(times),
        "errors": errors
    }
    return report
