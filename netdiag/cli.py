"""Command line interface for an IT support diagnostic workflow."""

from __future__ import annotations

import argparse
import sys

from .analysis import analyze
from .local import inspect_local_network
from .probes import check_dns, check_https, check_ping, check_tcp, skipped_records
from .report import build_report, save_reports


def build_demo_data() -> tuple[dict, list[dict]]:
    """Documentation-only data; never performs network checks or reads device info."""
    network = {
        "os": "macOS (DEMO)", "hostname": "support-laptop.example",
        "interfaces": [
            {"name": "en0", "ipv4": ["192.0.2.10"], "ipv6": []},
            {"name": "lo0", "ipv4": ["127.0.0.1"], "ipv6": ["::1"]},
        ],
        "default_gateway": "192.0.2.1", "dns_servers": ["203.0.113.53"],
        "collection_errors": [],
    }
    tests = [
        {"name": "DNS resolution", "status": "PASS",
         "message": "Resolved example.com successfully", "duration_ms": 21.4,
         "details": {"domain": "example.com", "addresses": ["93.184.215.14"]}},
        {"name": "ICMP ping", "status": "WARN",
         "message": "No ping response from 1.1.1.1; ICMP might be blocked",
         "duration_ms": 3000, "details": {"host": "1.1.1.1"}},
        {"name": "TCP connectivity", "status": "PASS", "message": "Connected to example.com:443",
         "duration_ms": 42.1, "details": {"host": "example.com", "port": 443, "remote_ip": "93.184.215.14"}},
        {"name": "HTTPS availability", "status": "PASS", "message": "HTTPS returned HTTP 200",
         "duration_ms": 98.8, "details": {"url": "https://example.com/", "http_status": 200}},
    ]
    return network, tests


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="netdiag", description="Cross-platform network diagnostics with HTML and JSON reports"
    )
    parser.add_argument("--domain", default="example.com", help="DNS lookup domain (default: example.com)")
    parser.add_argument("--host", default="example.com", help="TCP target (default: example.com)")
    parser.add_argument("--port", type=int, default=443, help="TCP port (default: 443)")
    parser.add_argument("--ping-host", default="1.1.1.1", help="Ping target (default: 1.1.1.1)")
    parser.add_argument("--url", default="https://example.com/", help="HTTPS URL")
    parser.add_argument("--timeout", type=float, default=3.0, help="Timeout per network check in seconds")
    parser.add_argument("--output-dir", default="reports", help="Directory for JSON and HTML reports")
    parser.add_argument("--no-network", action="store_true", help="Collect local information without probing internet")
    parser.add_argument("--demo", action="store_true", help="Generate a safe simulated example report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be in range 1-65535")
    if not 0.1 <= args.timeout <= 60:
        parser.error("--timeout must be between 0.1 and 60 seconds")
    targets = {"dns_domain": args.domain, "ping_host": args.ping_host,
               "tcp_host": args.host, "tcp_port": args.port, "https_url": args.url}
    if args.demo:
        network, tests = build_demo_data()
    else:
        print("[1/2] Inspecting local network configuration...")
        network = inspect_local_network()
        if args.no_network:
            tests = skipped_records()
        else:
            print("[2/2] Running DNS, ICMP, TCP, and HTTPS probes...")
            tests = [
                check_dns(args.domain),
                check_ping(args.ping_host, args.timeout),
                check_tcp(args.host, args.port, args.timeout),
                check_https(args.url, args.timeout),
            ]
    summary = analyze(network, tests, demo=args.demo)
    report = build_report(network, tests, summary, targets)
    try:
        json_path, html_path = save_reports(report, args.output_dir,
                                           basename="demo_report" if args.demo else None)
    except OSError as exc:
        print(f"Could not save report: {exc}", file=sys.stderr)
        return 2

    print(f"\nNetwork Diagnostic Tool — {summary['overall_status']}")
    print("-" * 48)
    for test in tests:
        print(f"{test['status']:>4}  {test['name']}: {test['message']}")
    print("\nFindings:")
    for finding in summary["findings"]:
        print(f"  - {finding}")
    print(f"\nJSON report: {json_path}")
    print(f"HTML report: {html_path}")
    print("Privacy: review hostname and local IPs before sharing reports.")
    # A failed check is a diagnostic result, not a software execution error.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
