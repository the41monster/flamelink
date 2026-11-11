from rich.console import Console
from rich.table import Table
from rich.markup import escape

DEFAULT_TOP = 20


def format_location(file: str | None, line: int | None) -> str:
    if file is None:
        return "N/A"
    if line is not None:
        return f"{file}:{line}"
    return file


def format_ms(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def render_report(report: dict, console: Console) -> None:
    # Summary
    console.print(f"[bold]Report for {escape(report['target'])}[/bold]")
    console.print(f"Duration: {report['duration_s']} seconds")
    console.print(f"Sampler: {escape(report['sampler'] or 'N/A')}")
    console.print(f"Timestamp: {escape(report['timestamp'])}")
    console.print(f"p50 (ms): {format_ms(report['p50_ms'])}")
    console.print(f"p95 (ms): {format_ms(report['p95_ms'])}")
    console.print(f"p99 (ms): {format_ms(report['p99_ms'])}")

    # Hotspots
    if not report["hotspots"]:
        console.print("\nNo profiling data (load-only run)")
        return

    # Display hotspots
    table = Table(title="Hotspots")
    table.add_column("Function", style="cyan", no_wrap=True)
    table.add_column("Location", style="magenta")
    table.add_column("Self %", justify="right")
    table.add_column("Total %", justify="right")

    for hotspot in report["hotspots"][:DEFAULT_TOP]:
        table.add_row(
            escape(hotspot["fn"]),
            escape(format_location(hotspot["file"], hotspot["line"])),
            f"{hotspot['self_pct']:.2f}",
            f"{hotspot['total_pct']:.2f}",
        )
    console.print(table)
    if len(report["hotspots"]) > DEFAULT_TOP:
        console.print(f"Showing top {DEFAULT_TOP} of {len(report['hotspots'])} functions")
