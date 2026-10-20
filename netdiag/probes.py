"""Network probes: DNS, ICMP ping, TCP connection, and HTTPS response."""

from __future__ import annotations

import math
import platform
import re
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

from .utils import run_command


def _record(name: str, status: str, message: str, duration_ms: float | None = None,
            details: dict | None = None) -> dict:
    return {
        "name": name,
        "status": status,
        "message": message,
        "duration_ms": duration_ms,
        "details": details or {},
    }


def check_dns(domain: str) -> dict:
    start = time.monotonic()
    try:
        addresses = sorted({
            entry[4][0]
            for entry in socket.getaddrinfo(domain, None, type=socket.SOCK_STREAM)
        })
        elapsed = round((time.monotonic() - start) * 1000, 2)
        if not addresses:
            return _record("DNS resolution", "FAIL", f"No IP addresses returned for {domain}", elapsed)
        return _record("DNS resolution", "PASS", f"Resolved {domain} successfully", elapsed,
                       {"domain": domain, "addresses": addresses[:20]})
    except (socket.gaierror, OSError, UnicodeError) as exc:
        return _record("DNS resolution", "FAIL", f"Cannot resolve {domain}: {exc}",
                       round((time.monotonic() - start) * 1000, 2), {"domain": domain})


def check_tcp(host: str, port: int, timeout: float) -> dict:
    start = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout) as connection:
            remote = connection.getpeername()[0]
        return _record("TCP connectivity", "PASS", f"Connected to {host}:{port}",
                       round((time.monotonic() - start) * 1000, 2),
                       {"host": host, "port": port, "remote_ip": remote})
    except (socket.timeout, OSError, UnicodeError) as exc:
        return _record("TCP connectivity", "FAIL", f"Cannot connect to {host}:{port}: {exc}",
                       round((time.monotonic() - start) * 1000, 2),
                       {"host": host, "port": port})


def check_https(url: str, timeout: float) -> dict:
    start = time.monotonic()
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return _record("HTTPS availability", "FAIL", "A valid https:// URL is required", 0,
                       {"url": url})
    request = urllib.request.Request(
        url, method="GET", headers={"User-Agent": "NetworkDiagnosticTool/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            # Read at most 1 byte; the goal is availability, not page download.
            response.read(1)
            code = response.status
            final_url = response.geturl()
        elapsed = round((time.monotonic() - start) * 1000, 2)
        tls_verified = urlparse(final_url).scheme == "https"
        status = "PASS" if 200 <= code < 400 and tls_verified else "WARN"
        message = f"HTTPS returned HTTP {code}" if tls_verified else "Request redirected away from HTTPS"
        return _record("HTTPS availability", status, message,
                       elapsed, {"url": url, "http_status": code, "tls_verified": tls_verified, "final_url": final_url})
    except urllib.error.HTTPError as exc:
        return _record("HTTPS availability", "WARN", f"Server responded with HTTP {exc.code}",
                       round((time.monotonic() - start) * 1000, 2),
                       {"url": url, "http_status": exc.code})
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return _record("HTTPS availability", "FAIL", f"HTTPS request failed: {exc}",
                       round((time.monotonic() - start) * 1000, 2), {"url": url})


def check_ping(host: str, timeout: float, system: str | None = None) -> dict:
    system = system or platform.system()
    # Use the overall subprocess timeout across OSes to avoid differing ping flags.
    if system == "Windows":
        command = ["ping", "-n", "1", "-w", str(max(1, math.ceil(timeout * 1000))), host]
    else:
        command = ["ping", "-c", "1", host]
    result = run_command(command, timeout=timeout + 0.5)
    match = re.search(r"\btime\s*[=<]\s*([0-9]+(?:[.,][0-9]+)?)\s*ms", result["stdout"], re.IGNORECASE)
    latency = float(match.group(1).replace(",", ".")) if match else None
    if result["ok"]:
        return _record("ICMP ping", "PASS", f"Ping successful: {host}",
                       latency if latency is not None else result["elapsed_ms"],
                       {"host": host, "icmp_rtt_ms": latency})
    # A blocked ICMP reply is not equivalent to an internet outage.
    return _record("ICMP ping", "WARN", f"No ping response from {host}; ICMP might be blocked",
                   result["elapsed_ms"], {"host": host, "reason": result["stderr"][:180]})


def skipped_records() -> list[dict]:
    return [_record(name, "SKIP", "Network probes disabled (--no-network)")
            for name in ("DNS resolution", "ICMP ping", "TCP connectivity", "HTTPS availability")]
