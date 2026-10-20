"""Fast tests: no actual internet or system configuration changes are required."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from netdiag.analysis import analyze
from netdiag.cli import build_demo_data, main
from netdiag.local import (
    parse_dns_servers, parse_gateway, parse_linux_ip_json,
    parse_macos_ifconfig, parse_windows_ipconfig,
)
from netdiag.probes import check_dns, check_ping, check_tcp
from netdiag.report import build_report, render_html, save_reports


class ParserTests(unittest.TestCase):
    def test_macos_ifconfig(self):
        raw = """lo0: flags=8049<UP> mtu 16384
\tinet 127.0.0.1 netmask 0xff000000
\tinet6 ::1 prefixlen 128
 en0: flags=8863<UP> mtu 1500
""".replace(" en0:", "en0:") + "\tether aa:bb:cc:dd:ee:ff\n\tinet 192.168.1.25 netmask 0xffffff00\n"
        interfaces = parse_macos_ifconfig(raw)
        self.assertEqual(interfaces[1]["name"], "en0")
        self.assertEqual(interfaces[1]["ipv4"], ["192.168.1.25"])
        self.assertNotIn("aa:bb:cc:dd:ee:ff", str(interfaces))

    def test_linux_ip_json(self):
        raw = json.dumps([{"ifname": "eth0", "addr_info": [
            {"family": "inet", "local": "10.0.0.9"},
            {"family": "inet6", "local": "2001:db8::1"}
        ]}])
        self.assertEqual(parse_linux_ip_json(raw)[0]["ipv6"], ["2001:db8::1"])

    def test_windows_ipv4(self):
        raw = "Ethernet adapter Ethernet:\n   IPv4 Address. . . : 192.168.0.10(Preferred)\n"
        self.assertEqual(parse_windows_ipconfig(raw)[0]["ipv4"], ["192.168.0.10"])

    def test_gateway_on_three_systems(self):
        self.assertEqual(parse_gateway("   gateway: 192.168.1.1\n", "Darwin"), "192.168.1.1")
        self.assertEqual(parse_gateway("default via 10.0.0.1 dev eth0", "Linux"), "10.0.0.1")
        self.assertEqual(parse_gateway("0.0.0.0  0.0.0.0  172.16.0.1  172.16.0.15  25", "Windows"), "172.16.0.1")

    def test_dns_mac_and_linux(self):
        mac = "nameserver[0] : 1.1.1.1\nnameserver[1] : 1.1.1.1\nnameserver[2] : 8.8.8.8"
        self.assertEqual(parse_dns_servers(mac, "Darwin"), ["1.1.1.1", "8.8.8.8"])
        self.assertEqual(parse_dns_servers("nameserver 127.0.0.53\n", "Linux"), ["127.0.0.53"])


class ProbeTests(unittest.TestCase):
    @patch("netdiag.probes.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("203.0.113.7", 0))])
    def test_dns_success(self, _):
        self.assertEqual(check_dns("example.com")["status"], "PASS")

    @patch("netdiag.probes.socket.getaddrinfo", side_effect=OSError("DNS unavailable"))
    def test_dns_failure(self, _):
        self.assertEqual(check_dns("unknown.invalid")["status"], "FAIL")

    @patch("netdiag.probes.socket.create_connection", side_effect=OSError("port closed"))
    def test_tcp_failure(self, _):
        self.assertEqual(check_tcp("localhost", 12345, 0.1)["status"], "FAIL")

    @patch("netdiag.probes.run_command")
    def test_ping_failure_is_warning(self, mocked):
        mocked.return_value = {"ok": False, "stdout": "", "stderr": "timeout", "elapsed_ms": 1200.0}
        self.assertEqual(check_ping("1.1.1.1", 1, system="Linux")["status"], "WARN")


class ReportTests(unittest.TestCase):
    def test_demo_no_real_device_information(self):
        network, tests = build_demo_data()
        summary = analyze(network, tests, demo=True)
        self.assertEqual(summary["overall_status"], "WARN")
        self.assertIn("DEMO DATA", render_html(build_report(network, tests, summary, {})))

    def test_escape_html(self):
        network, tests = build_demo_data()
        network["hostname"] = '<img src=x onerror="alert(1)">'
        report = build_report(network, tests, analyze(network, tests), {})
        html = render_html(report)
        self.assertIn("&lt;img", html)
        self.assertNotIn('<img src=x onerror="alert(1)">', html)

    def test_save_files(self):
        network, tests = build_demo_data()
        report = build_report(network, tests, analyze(network, tests), {})
        with tempfile.TemporaryDirectory() as directory:
            json_path, html_path = save_reports(report, directory)
            self.assertTrue(json_path.exists())
            self.assertTrue(html_path.exists())
            self.assertEqual(json.loads(json_path.read_text())["tool"], "Network Diagnostic Tool")

    def test_cli_demo(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(main(["--demo", "--output-dir", directory]), 0)
            self.assertTrue((Path(directory) / "demo_report.html").exists())


if __name__ == "__main__":
    unittest.main()
