import argparse
import asyncio
import json

from flamelink.load import generate_load
from flamelink.report import build_report


def main():
    parser = argparse.ArgumentParser(description="Generate load on a target URL.")
    parser.add_argument("--url", type=str, help="Target URL to send requests to.")
    parser.add_argument("--rps", type=int, default=10, help="Requests per second.")
    parser.add_argument("--duration", type=int, default=10, help="Duration of the load test in seconds.")
    parser.add_argument("--output", type=str, help="Output file to save the report.")

    args = parser.parse_args()

    url = args.url
    rps = args.rps
    duration_s = args.duration

    print(f"Generating load on {url} with {rps} RPS for {duration_s} seconds...")

    response_times, error_count = asyncio.run(generate_load(url, rps, duration_s))

    report = build_report(url, rps, duration_s, response_times, error_count)
    report = json.dumps(report, indent=2)

    print("Load test completed.")
    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"Report saved to {args.output}")
    else:
        print(f"Report: \n{report}")

if __name__ == "__main__":
    main()
