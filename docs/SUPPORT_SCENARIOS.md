# Network Diagnostic Tool — troubleshooting scenarios

**Scope:** fictional first-/second-level support examples, not actual customer incidents. Live probes require your explicit action and network access; the app never changes network settings.

## Scenario 1 — A website is unavailable

**Symptom:** The browser cannot open a work site although Wi-Fi appears connected.

**Structured checks:**
1. **Local state:** inspect network interfaces, local IP address, default gateway and configured DNS servers.
2. **DNS:** resolve an authorized test hostname and record success/failure.
3. **ICMP:** ping an allowed target. A timeout is *not proof* of an outage; ICMP may be blocked.
4. **TCP:** test connectivity to a relevant port such as HTTPS `443`.
5. **HTTPS:** request a permitted HTTPS target and capture the response/status.
6. **Report:** export HTML/JSON results and redact hostnames and private IPs before sharing.

**Example interpretation:** DNS failure but working IP-level reachability suggests checking resolver settings or DNS infrastructure. TCP success with an HTTPS failure suggests inspecting TLS, endpoint or proxy behavior. These are hypotheses to validate, not definitive fault diagnoses.

**Safe reproducible demo (no live probes):**

```bash
python3 -m netdiag --demo --output-dir reports
python3 -m netdiag.dashboard --demo
```

**Evidence:** [`tests/test_diagnostics.py`](../tests/test_diagnostics.py) checks DNS/TCP/ping handling, OS-specific parsing and reporting. [`tests/test_dashboard.py`](../tests/test_dashboard.py) checks demo pages, API validation, security restrictions and report responses. Run `python3 -m unittest discover -s tests -v`.

## Scenario 2 — Connectivity passes but the application still fails

**Symptom:** DNS resolves, the target TCP port is reachable, but the user still cannot complete a workflow.

**Support response:** document which network layers have been checked, record timings/statuses and escalate application-layer investigation rather than claiming a network fix. Verify the outcome with a real application transaction after any authorized change.

## Kurzfassung / Türkçe özet

**DE:** Zwei simulierte Netzwerkfälle zeigen systematische Eingrenzung mit DNS, Ping, TCP und HTTPS sowie nachvollziehbare Offline-Berichte; ein Ping-Timeout ist kein eindeutiger Ausfallnachweis.

**TR:** İki örnek vaka DNS, ping, TCP ve HTTPS kontrolleriyle katmanlı ağ teşhisini ve raporlamayı gösterir. Ping yanıtı gelmemesi tek başına bağlantı arızası kanıtı değildir.

**Privacy:** Never upload an unredacted report containing device names, internal IP addresses or private hosts.
