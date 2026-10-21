# Verification matrix — Network Diagnostic Tool

| ID | Controlled stimulus | Expected outcome | Evidence |
| --- | --- | --- | --- |
| ND-01 | Successful mock DNS resolution | PASS for DNS | `tests/test_diagnostics.py::ProbeTests.test_dns_success` |
| ND-02 | Mock DNS lookup raises `OSError` | FAIL and troubleshooting hint | `tests/test_diagnostics.py::ProbeTests.test_dns_failure` |
| ND-03 | Ping non-response / command error | WARN, not conclusive internet failure | `tests/test_diagnostics.py::ProbeTests.test_ping_failure_is_warning` |
| ND-04 | TCP connect fails | FAIL and network/service hint | `tests/test_diagnostics.py::ProbeTests.test_tcp_failure` |
| ND-05 | Malformed host, credentials in URL, bad origin | Request rejected | `tests/test_dashboard.py::ValidationTests`, `HTTPTests` |
| ND-06 | Demo mode generates report | Synthetic HTML/JSON only; no live probes | `tests/test_diagnostics.py::ReportTests` |
| ND-07 | DNS fails, gateway and TCP status ambiguous | Separate findings with appropriate priority | `tests/test_recruiter_regressions.py` |
| ND-08 | Distinct Linux/macOS/Windows adapters | Parse correct local fields | `tests/test_diagnostics.py::ParserTests` |

Tests are offline/mock-based where indicated. A test file name is not a claim of having run the test in an actual company environment.

```bash
python3 -m unittest discover -s tests -v
python3 -m netdiag.dashboard --demo
```

**Manual review:** Open the demo, inspect the HTTP status and exported JSON/HTML, and check host/IP privacy. Record actual outcomes separately; do not present this guidance as a signed test report.
