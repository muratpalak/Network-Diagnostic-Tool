"""Collect local IP addresses, default gateway, and configured DNS resolvers."""

from __future__ import annotations

import ipaddress
import json
import platform
import re
import socket
from pathlib import Path

from .utils import run_command

_IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_IPV6 = re.compile(r"(?<![\da-fA-F:])(?:[\da-fA-F]{0,4}:){2,}[\da-fA-F:.%]*(?![\da-fA-F:])")


def _valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value.split("%")[0])
        return True
    except ValueError:
        return False


def parse_macos_ifconfig(raw: str) -> list[dict]:
    """Parse only interface name and IPs, never MAC addresses."""
    interfaces: list[dict] = []
    current: dict | None = None
    for line in raw.splitlines():
        header = re.match(r"^([\w.:-]+):\s+flags=", line)
        if header:
            current = {"name": header.group(1), "ipv4": [], "ipv6": []}
            interfaces.append(current)
        if current is None:
            continue
        match4 = re.match(r"\s+inet\s+(\S+)", line)
        match6 = re.match(r"\s+inet6\s+(\S+)", line)
        if match4 and _valid_ip(match4.group(1)):
            current["ipv4"].append(match4.group(1))
            mask = re.search(r"\bnetmask\s+(0x[0-9a-fA-F]{8}|(?:\d{1,3}\.){3}\d{1,3})", line)
            if mask:
                try:
                    val = str(ipaddress.IPv4Address(int(mask.group(1), 16))) if mask.group(1).startswith('0x') else mask.group(1)
                    if _valid_ip(val):
                        current['subnet_mask'] = val
                except ValueError:
                    pass
        if match6 and _valid_ip(match6.group(1)):
            current["ipv6"].append(match6.group(1))
    return [i for i in interfaces if i["ipv4"] or i["ipv6"]]


def parse_linux_ip_json(raw: str) -> list[dict]:
    interfaces: list[dict] = []
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("Expected a list of network interfaces")
    for item in data:
        iface = {"name": str(item.get("ifname", "unknown")), "ipv4": [], "ipv6": []}
        for address in item.get("addr_info", []):
            value = str(address.get("local", ""))
            if not _valid_ip(value):
                continue
            if address.get("family") == "inet":
                iface["ipv4"].append(value)
                try:
                    prefix = int(address.get('prefixlen'))
                    iface['subnet_mask'] = str(ipaddress.IPv4Network(f'0.0.0.0/{prefix}').netmask)
                except (ValueError, TypeError):
                    pass
            elif address.get("family") == "inet6":
                iface["ipv6"].append(value)
        if iface["ipv4"] or iface["ipv6"]:
            interfaces.append(iface)
    return interfaces


def parse_windows_ipconfig(raw: str) -> list[dict]:
    """Best-effort parser across localized ipconfig variants."""
    interfaces: list[dict] = []
    current: dict | None = None
    for line in raw.splitlines():
        # Adapter section headings do not start with whitespace and end in a colon.
        if line and not line[0].isspace() and line.rstrip().endswith(":"):
            current = {"name": line.strip().rstrip(":"), "ipv4": [], "ipv6": []}
            interfaces.append(current)
        if current is None:
            continue
        if re.search(r"IPv4", line, flags=re.IGNORECASE):
            for value in _IPV4.findall(line):
                if _valid_ip(value) and value not in current["ipv4"]:
                    current["ipv4"].append(value)
        if re.search(r"Subnet Mask|Subnetzmaske|Alt Ağ Maskesi|Alt A[ğg] Maskesi", line, re.IGNORECASE):
            for candidate in _IPV4.findall(line):
                if _valid_ip(candidate):
                    current['subnet_mask'] = candidate
                    break
        if re.search(r"IPv6", line, flags=re.IGNORECASE):
            for value in _IPV6.findall(line):
                if _valid_ip(value) and value not in current["ipv6"]:
                    current["ipv6"].append(value)
    return [i for i in interfaces if i["ipv4"] or i["ipv6"]]


def parse_gateway(raw: str, system: str) -> str | None:
    if system == "Darwin":
        match = re.search(r"^\s*gateway:\s*(\S+)", raw, flags=re.MULTILINE)
        return match.group(1) if match and _valid_ip(match.group(1)) else None
    if system == "Linux":
        match = re.search(r"\bdefault\s+via\s+(\S+)", raw)
        return match.group(1) if match and _valid_ip(match.group(1)) else None
    if system == "Windows":
        for line in raw.splitlines():
            columns = line.split()
            if len(columns) >= 4 and columns[0] == "0.0.0.0" and columns[1] == "0.0.0.0":
                return columns[2] if _valid_ip(columns[2]) else None
    return None


def parse_dns_servers(raw: str, system: str) -> list[str]:
    servers: list[str] = []
    if system == "Darwin":
        entries = re.findall(r"nameserver\[\d+\]\s*:\s*(\S+)", raw)
    elif system == "Linux":
        entries = re.findall(r"^\s*nameserver\s+(\S+)", raw, flags=re.MULTILINE)
    else:
        # Windows ipconfig /all uses different labels across languages.
        # Extract only the DNS Servers field and its continuation IP-only lines.
        entries = []
        collecting = False
        for line in raw.splitlines():
            if re.search(r"DNS[- ](?:Servers|Server|server|sunucuları|sunucusu)\b", line, re.IGNORECASE):
                collecting = True
                entries.extend(_IPV4.findall(line))
                continue
            if collecting and line.startswith(" ") and ":" not in line:
                stripped = line.strip()
                if _valid_ip(stripped):
                    entries.append(stripped)
                    continue
            collecting = False
    for entry in entries:
        candidate = entry.strip(" ,").split("%")[0]
        if _valid_ip(candidate) and candidate not in servers:
            servers.append(candidate)
    return servers[:12]


def inspect_local_network(system: str | None = None) -> dict:
    system = system or platform.system()
    hostname = socket.gethostname()
    errors: list[str] = []
    interfaces: list[dict] = []
    if system == "Darwin":
        result = run_command(["ifconfig", "-a"])
        interfaces = parse_macos_ifconfig(result["stdout"])
    elif system == "Windows":
        result = run_command(["ipconfig", "/all"])
        interfaces = parse_windows_ipconfig(result["stdout"])
    elif system == "Linux":
        result = run_command(["ip", "-j", "address", "show"])
        if result["ok"]:
            try:
                interfaces = parse_linux_ip_json(result["stdout"])
            except (ValueError, KeyError, TypeError) as exc:
                errors.append(f"Cannot parse ip command output: {exc}")
        else:
            # Fallback on systems with ifconfig but no iproute2.
            fallback = run_command(["ifconfig", "-a"])
            if fallback["ok"]:
                interfaces = parse_macos_ifconfig(fallback["stdout"])
                result = fallback
    else:
        result = {"ok": False, "stderr": f"Unsupported OS: {system}"}
    if not result["ok"]:
        errors.append(f"IP information unavailable: {result['stderr']}")

    route_commands = {
        "Darwin": ["route", "-n", "get", "default"],
        "Linux": ["ip", "route", "show", "default"],
        "Windows": ["route", "print", "-4"],
    }
    route_result = run_command(route_commands[system]) if system in route_commands else {"ok": False, "stdout": ""}
    gateway = parse_gateway(route_result["stdout"], system)

    if system == "Darwin":
        dns_result = run_command(["scutil", "--dns"])
        dns_servers = parse_dns_servers(dns_result["stdout"], system)
    elif system == "Windows":
        dns_servers = parse_dns_servers(result.get("stdout", ""), system)
    elif system == "Linux":
        try:
            dns_servers = parse_dns_servers(Path("/etc/resolv.conf").read_text(encoding="utf-8"), system)
        except OSError as exc:
            dns_servers = []
            errors.append(f"DNS configuration unavailable: {exc}")
    else:
        dns_servers = []

    return {
        "os": system,
        "hostname": hostname,
        "interfaces": interfaces,
        "default_gateway": gateway,
        "dns_servers": dns_servers,
        "collection_errors": errors,
    }
