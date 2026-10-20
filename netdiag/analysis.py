"""Translate diagnostic results into help-desk-friendly findings."""

from __future__ import annotations


def analyze(network: dict, tests: list[dict], demo: bool = False) -> dict:
    by_name = {entry["name"]: entry for entry in tests}
    findings: list[str] = []
    if network.get("collection_errors"):
        findings.append("Some local configuration details could not be collected. Check OS tools and permissions.")
    non_loopback_ipv4 = [address for interface in network.get("interfaces", [])
                         for address in interface.get("ipv4", [])
                         if not address.startswith("127.")]
    if not non_loopback_ipv4:
        findings.append("No non-loopback IPv4 address was detected. Check the network adapter or parser support.")
    if not network.get("default_gateway"):
        findings.append("Default gateway was not detected. Check the routing table if connectivity fails.")
    if not network.get("dns_servers"):
        findings.append("No configured DNS server was detected. Check the OS resolver configuration.")
    if by_name.get("DNS resolution", {}).get("status") == "FAIL":
        findings.append("DNS lookup failed. Verify DNS servers, VPN settings, and name resolution.")
    if by_name.get("TCP connectivity", {}).get("status") == "FAIL":
        findings.append("TCP connection failed. Check routing, firewall, proxy, and remote service port.")
    if by_name.get("HTTPS availability", {}).get("status") == "FAIL":
        findings.append("HTTPS failed. Check TLS certificates, proxy settings, and the destination service.")
    if by_name.get("HTTPS availability", {}).get("status") == "WARN":
        findings.append("HTTPS server is reachable but returned an application-level HTTP error.")
    if by_name.get("ICMP ping", {}).get("status") == "WARN":
        findings.append("Ping did not succeed. This alone does not confirm internet failure; ICMP may be filtered.")
    statuses = [test["status"] for test in tests]
    if "FAIL" in statuses:
        overall = "FAIL"
    elif "WARN" in statuses or network.get("collection_errors") or not non_loopback_ipv4:
        overall = "WARN"
    elif all(status == "SKIP" for status in statuses):
        overall = "INFO"
    else:
        overall = "PASS"
    if not findings:
        findings.append("No obvious problems found in the selected checks.")
    return {"overall_status": overall, "findings": findings, "demo": demo}
