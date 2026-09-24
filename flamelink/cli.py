import argparse
import asyncio
import json
import sys

from flamelink.load import generate_load
from flamelink.report import build_report
from flamelink.profilers.pyspy import record, ProfilerError
from flamelink.profilers.clinicjs import record as record_clinicjs
from flamelink.wsl import to_windows_path


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

    node_parser = profile_subparsers.add_parser("node", help="Profile a running Node.js process.")
    node_parser.add_argument("--mode", type=str, choices=["flame", "doctor"], default="flame", help="Profiling mode (default: flame).")
    node_parser.add_argument("--duration", type=int, default=10, help="Duration of the profiling in seconds.")
    node_parser.add_argument("--out", type=str, required=True, help="Output file to save the profiling data.")
    node_parser.add_argument("target_command", nargs="+", help="Command to run the Node.js application")

    args = parser.parse_args()

    if args.command == "load":
        url = args.url
        rps = args.rps
        duration_s = args.duration
        output = args.output

        print(f"Generating load on {url} with {rps} RPS for {duration_s} seconds...")
        response_times, error_count = asyncio.run(generate_load(url, rps, duration_s))
        report = build_report(url, rps, duration_s, response_times, error_count)
        report_json = json.dumps(report, indent=2)
        print("Load test completed.")
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

        print(f"Profiling Python process with PID {pid} for {duration} seconds...")
        try:
            record(pid, duration, out)
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
            print(f"Error during profiling: {e}")
            sys.exit(1)
    else:
        parser.error(f"Unknown command: {args.command} {getattr(args, 'target', '')}".strip())

if __name__ == "__main__":
    main()
