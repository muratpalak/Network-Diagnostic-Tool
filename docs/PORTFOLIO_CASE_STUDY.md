# Network Diagnostic Tool — Portfolio Case Study

**Repository:** https://github.com/muratpalak/Network-Diagnostic-Tool  
**Status:** Local demonstration / portfolio project  
**Technical focus:** Python · DNS · TCP/IP · Cross-platform  
**Automated workflow:** [GitHub Actions](https://github.com/muratpalak/Network-Diagnostic-Tool/actions/workflows/tests.yml)

## Context and problem

This project explores **network troubleshooting and structured diagnostics** through a reproducible portfolio exercise. Its examples are not represented as an employer deployment or production customer implementation.

## Implemented capabilities

- DNS lookups, ICMP reachability, TCP connection attempts and HTTPS checks
- System network interface and gateway inspection
- HTML/JSON report generation
- Local-only browser dashboard and request validation

## Reproducible review

Read the repository [README](../README.md) for supported platforms and installation prerequisites. Where the necessary runtime tools are installed, reproduce the checks using:

```bash
python3 -m unittest discover -s tests -v
```

The associated CI workflow provides evidence of the configured automated checks; it is **not** a guarantee of full feature coverage, security accreditation or production availability.

## Boundaries and honest limitations

Local workstation network checks; simulated demo mode; not an enterprise monitoring agent.

## Relevance to IT roles

First-level / second-level troubleshooting, incident documentation, connectivity analysis.

## Deutsche Kurzfassung

**Projekt:** Lokale Netzwerkanalyse mit DNS-, Ping-, TCP- und HTTPS-Prüfungen sowie HTML-/JSON-Berichten.  
**Schwerpunkt:** Network troubleshooting and structured diagnostics.  
**Nachweis:** Quellcode, Installationsanleitung, definierte Tests und GitHub-Actions-Protokolle.  
**Einordnung:** Portfolio-/Demonstrationsprojekt; keine Behauptung eines Produktiveinsatzes.
