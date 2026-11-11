import argparse
import asyncio
import json
import sys
from rich.console import Console

from flamelink.display import render_report
from flamelink.hotspot import pyspy_hotspots
from flamelink.load import generate_load
from flamelink.profilers.errors import ProfilerError
from flamelink.profilers.pyspy import record as record_pyspy, ensure_sudo
from flamelink.profilers.clinicjs import record as record_clinicjs
from flamelink.report import build_report, load_report, ReportError
from flamelink.wsl import to_windows_path


async def record_with_load(record_fn, url: str, rps: int, duration_s: int) -> tuple[list[float], dict]:
    _, (times, errors) = await asyncio.gather(
        asyncio.to_thread(record_fn),
        generate_load(url, rps, duration_s)
    )
    return times, errors


def profile_with_load(record_fn, parse_hotspots, sampler: str, args) -> None:
    print(f"Profiling for {args.duration} seconds while sending {args.rps} RPS to {args.url}...")
    times, errors = asyncio.run(record_with_load(record_fn, args.url, args.rps, args.duration))
    print(f"Profiling completed. Data saved to {args.out}")
    print(f"Errors: {errors}")

    try:
        hotspots = parse_hotspots(args.out)
    except ValueError as e:
        print(f"Profile saved to {args.out}, but hotspots could not be extracted from it: {e}")
        sys.exit(1)
    report = build_report(args.url, args.duration, times, sampler=sampler, hotspots=hotspots)
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Report saved to {args.report}")


def main():
    parser = argparse.ArgumentParser(prog="flamelink", description="Flamelink CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    load_parser = subparsers.add_parser("load", help="Generate load on a target URL.")
    load_parser.add_argument("--url", type=str, required=True, help="Target URL to send requests to.")
    load_parser.add_argument("--rps", type=int, default=10, help="Requests per second.")
    load_parser.add_argument("--duration", type=int, default=10, help="Duration of the load test in seconds.")
    load_parser.add_argument("--output", type=str, help="Output file to save the report.")

    profile_parser = subparsers.add_parser("profile", help="Profile a Python process using py-spy.")
    profile_subparsers = profile_parser.add_subparsers(dest="target", required=True)

    python_parser = profile_subparsers.add_parser("python", help="Profile a running Python process.")
    python_parser.add_argument("--pid", type=int, required=True, help="PID of the Python process to profile.")
    python_parser.add_argument("--duration", type=int, default=10, help="Duration of the profiling in seconds.")
    python_parser.add_argument("--out", type=str, required=True, help="Output file to save the profiling data.")
    python_parser.add_argument("--url", type=str, help="Send load to this URL while profiling.")
    python_parser.add_argument("--rps", type=int, default=10, help="Requests per second when --url is specified.")
    python_parser.add_argument("--report", type=str, help="Write a combined latency + hotspot report to this file when --url is specified.")

    node_parser = profile_subparsers.add_parser("node", help="Profile a Node.js process.")
    node_parser.add_argument("--mode", type=str, choices=["flame", "doctor"], default="flame", help="Profiling mode (default: flame).")
    node_parser.add_argument("--duration", type=int, default=10, help="Duration of the profiling in seconds.")
    node_parser.add_argument("--out", type=str, required=True, help="Output file to save the profiling data.")
    node_parser.add_argument("target_command", nargs="+", metavar="-- COMMAND", help="Command to run, e.g. -- node app.js. Use -- to separate the command from the CLI arguments.")

    report_parser = subparsers.add_parser("report", help="Show a report file as a table or JSON.")
    report_parser.add_argument("path", type=str, help="Path to the report file (JSON).")
    report_parser.add_argument("--format", choices=["table", "json"], default="table", help="Output style: a table for the console or JSON for machine consumption (default: table).")

    args = parser.parse_args()

    if args.command == "profile" and args.target == "python":
        if args.report and not args.url:
            parser.error("--report requires --url to be specified.")
        if args.url and not args.report:
            parser.error("--url requires --report to be specified.")

    if args.command == "load":
        url = args.url
        rps = args.rps
        duration_s = args.duration
        output = args.output

        print(f"Generating load on {url} with {rps} RPS for {duration_s} seconds...")
        response_times, error_count = asyncio.run(generate_load(url, rps, duration_s))
        report = build_report(url, duration_s, response_times)
        report_json = json.dumps(report, indent=2)
        print("Load test completed.")
        print(f"Errors: {error_count}")
        if output:
            try:
                with open(output, "w") as f:
                    f.write(report_json)
                print(f"Report saved to {output}")
            except Exception as e:
                print(f"Error saving report to {output}: {e}")
                sys.exit(1)
        else:
            print(f"Report: \n{report_json}")
    elif args.command == "profile" and args.target == "python":
        pid = args.pid
        duration = args.duration
        out = args.out

        try:
            if args.url is None:
                print(f"Profiling Python process {pid} for {duration} seconds...")
                record_pyspy(pid, duration, out)
                print(f"Profiling completed. Data saved to {out}")
            else:
                ensure_sudo()
                profile_with_load(lambda: record_pyspy(pid, duration, out), pyspy_hotspots, "py-spy", args)
            windows_path = to_windows_path(out)
            if windows_path is not None:
                print(f"Windows path: {windows_path}")
        except ProfilerError as e:
            print(f"Error during profiling: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error during profiling: {e}")
            sys.exit(1)
    elif args.command == "profile" and args.target == "node":
        mode = args.mode
        duration = args.duration
        out = args.out
        target_command = args.target_command

        print(f"Profiling Node.js process for {duration} seconds...")
        try:
            record_clinicjs(command=target_command, duration=duration, output_path=out, mode=mode)
            print(f"Profiling completed. Data saved to {out}")
            windows_path = to_windows_path(out)
            if windows_path is not None:
                print(f"Windows path: {windows_path}")
        except ProfilerError as e:
            print(f"Error during profiling: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error during profiling: {e}")
            sys.exit(1)
    elif args.command == "report":
        try:
            report = load_report(args.path)
        except ReportError as e:
            print(f"Error loading report: {e}", file=sys.stderr)
            sys.exit(1)
        if args.format == "json":
            print(json.dumps(report, indent=2))
        else:
            render_report(report, Console())
    else:
        parser.error(f"Unknown command: {args.command} {getattr(args, 'target', '')}".strip())

if __name__ == "__main__":
    main()
