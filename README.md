# Network Diagnostic Tool

[![Network Diagnostic Tests](https://github.com/muratpalak/Network-Diagnostic-Tool/actions/workflows/tests.yml/badge.svg)](https://github.com/muratpalak/Network-Diagnostic-Tool/actions/workflows/tests.yml)

**Cross-platform local network troubleshooting and reporting for IT Support.** Python · DNS · Ping · TCP · HTTPS · HTML/JSON reporting. No third-party runtime dependencies; requires Python 3.10+.

> **Portfolio and educational project.** All network checks are initiated by the user. The application does not modify network settings. Report files can include local hostnames and IP addresses: review before sharing.

**Deutsch:** Plattformübergreifende, lokal ausgeführte Netzwerkanalyse mit DNS-, Ping-, TCP- und HTTPS-Prüfungen sowie HTML-/JSON-Berichten. Dieses Projekt ist eine Demonstration für IT-Support-Aufgaben.

**Türkçe:** [Kurulum ve kullanım kılavuzu](README_TR.md) · **Case study:** [EN + DE](docs/PORTFOLIO_CASE_STUDY.md)

## What it demonstrates

- DNS resolution, ICMP ping, TCP port checks and HTTPS availability tests.
- Local network interface, DNS server and gateway discovery (OS-specific capabilities).
- Local-only browser dashboard at `127.0.0.1` and command-line access.
- Offline JSON and HTML report generation.
- Mocked unit tests and dashboard integration tests on Ubuntu, Windows and macOS.

## Quick start

After cloning the repository, open a terminal in the repository root.

**macOS:** double-click `Start-Network-Diagnostic-Tool.command`, or run:

```bash
bash Start-Network-Diagnostic-Tool.command
```

**Windows:** run `Start-Network-Diagnostic-Tool.bat` (Python 3 installed), or:

```powershell
py -3 -m netdiag.dashboard
```

**Linux:** `bash start-linux.sh`.

**Any OS:**

```bash
python3 -m netdiag.dashboard
```

A browser window will open at a local URL shown in the terminal. Use **Control+C** to stop the server.

For a fully simulated preview (no real network checks):

```bash
python3 -m netdiag.dashboard --demo
```

Command-line diagnostics:

```bash
python3 -m netdiag --domain example.com --host example.com --port 443 --ping-host 1.1.1.1 --url https://example.com/
```

Generate fictional offline reports:

```bash
python3 -m netdiag --demo --output-dir reports
```

## Technical layout

| File / directory | Responsibility |
|---|---|
| `netdiag/dashboard.py` | Local-only HTTP interface, state, API and validation |
| `netdiag/local.py` | OS-specific network configuration inspection |
| `netdiag/probes.py` | DNS, ping, TCP and HTTPS diagnostics |
| `netdiag/analysis.py` | Diagnostic result evaluation |
| `netdiag/report.py` | Standalone offline HTML and JSON export |
| `netdiag/dashboard_assets/` | Dashboard UI files |
| `tests/` | Unit tests and offline HTTP integration tests |

## Tests

```bash
python3 -m unittest discover -s tests -v
```

[GitHub Actions](https://github.com/muratpalak/Network-Diagnostic-Tool/actions/workflows/tests.yml) runs the automated suite on Linux, Windows and macOS.

## Security & limitations

- Designed for local use. Do not publish or expose the dashboard to the Internet.
- Demo values are fictional; CI tests do not establish production readiness.
- Network commands can be blocked or behave differently under firewalls, OS permissions and corporate policies.
- Remove hostnames, private IP addresses and target details from shared exports when necessary.
- This project is not an enterprise monitoring platform or security vulnerability scanner.

**License:** MIT (see [LICENSE](LICENSE)).
