"""Write portable JSON and fully offline HTML reports."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path


def build_report(network: dict, tests: list[dict], analysis: dict, targets: dict,
                 timestamp: str | None = None) -> dict:
    return {
        "schema_version": "1.0",
        "generated_at_utc": timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": "Network Diagnostic Tool",
        "tool_version": "1.0.0",
        "targets": targets,
        "network": network,
        "tests": tests,
        "analysis": analysis,
        "privacy_note": "This report may contain private IP addresses and hostname. Review before sharing.",
    }


def _safe(value: object) -> str:
    return escape(str(value), quote=True)


def render_html(report: dict) -> str:
    status = report["analysis"]["overall_status"]
    demo = report["analysis"].get("demo", False)
    network = report["network"]
    tests = report["tests"]
    addresses = []
    for interface in network.get("interfaces", []):
        for family in ("ipv4", "ipv6"):
            for address in interface.get(family, []):
                addresses.append(
                    "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                        _safe(interface.get("name", "—")), _safe(family.upper()), _safe(address)
                    )
                )
    rows = "\n".join(addresses) or '<tr><td colspan="3" class="muted">No IP addresses detected</td></tr>'

    cards = []
    for test in tests:
        duration = "—" if test.get("duration_ms") is None else f"{test['duration_ms']} ms"
        details = test.get("details", {})
        detail_lines = " ".join(f"<span>{_safe(k)}: <b>{_safe(v)}</b></span>"
                                for k, v in details.items())
        cards.append(
            '<article class="test"><div class="test-head"><h3>{name}</h3>'
            '<span class="chip {state}">{state}</span></div>'
            '<p>{message}</p><div class="meta"><span>Duration: {duration}</span>{details}</div></article>'.format(
                name=_safe(test["name"]), state=_safe(test["status"].lower()),
                message=_safe(test["message"]), duration=_safe(duration), details=detail_lines,
            )
        )
    finding_items = "\n".join(f"<li>{_safe(item)}</li>" for item in report["analysis"]["findings"])
    dns_servers = ", ".join(network.get("dns_servers", [])) or "Not detected"
    demo_banner = '<div class="demo">DEMO DATA · This is a simulated report, not a live diagnostic.</div>' if demo else ""
    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Network Diagnostic Report</title>
<style>
:root{{color-scheme:light;--ink:#17243a;--muted:#657188;--line:#dce4ef;--blue:#3169e2;--bg:#f5f8fd}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}}
.wrap{{max-width:990px;margin:auto;padding:36px 24px 70px}}header{{background:linear-gradient(115deg,#11213e,#214b90);border-radius:18px;color:#fff;padding:34px 38px}}
.eyebrow{{font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#c4d6fa;font-weight:700}}
h1{{font-size:30px;letter-spacing:-.7px;margin:12px 0 6px}}header p{{margin:0;color:#d9e4f8}}.hero{{display:flex;flex-wrap:wrap;gap:16px;align-items:center;justify-content:space-between}}
.chip{{display:inline-block;border-radius:100px;padding:5px 12px;font-size:11px;font-weight:800;letter-spacing:.9px}}
.chip.pass{{background:#d9f8e7;color:#126541}}.chip.warn{{background:#fff1d1;color:#895603}}.chip.fail{{background:#ffe0e0;color:#952828}}.chip.skip,.chip.info{{background:#e5eaf3;color:#56657d}}
header .chip{{font-size:13px;padding:10px 18px}}.demo{{margin-top:18px;background:#fff2c8;border:1px solid #e6d18b;border-radius:10px;padding:11px 16px;font-weight:700;color:#735400}}
section{{margin-top:27px}}.section-title{{font-size:18px;margin:0 0 13px;letter-spacing:-.3px}}.panel,.test{{background:#fff;border:1px solid var(--line);border-radius:13px;padding:23px;box-shadow:0 3px 17px rgba(18,39,80,.03)}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:13px}}.metric{{background:white;border:1px solid var(--line);border-radius:12px;padding:17px 19px;min-width:0}}
.metric-label{{font-size:11px;font-weight:800;color:var(--muted);text-transform:uppercase;letter-spacing:.7px}}.metric-value{{font-size:16px;overflow-wrap:anywhere;font-weight:700;margin-top:5px}}
.tests{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px}}.test h3{{margin:0;font-size:16px}}.test p{{margin:13px 0;color:#344054;overflow-wrap:anywhere}}.test-head{{display:flex;justify-content:space-between;gap:12px;align-items:center}}.meta{{display:flex;flex-wrap:wrap;gap:9px;color:var(--muted);font-size:12px}}.meta span{{background:#f2f5fa;padding:3px 7px;border-radius:5px;overflow-wrap:anywhere}}
table{{width:100%;border-collapse:collapse}}th{{text-align:left;font-size:12px;letter-spacing:.6px;text-transform:uppercase;color:var(--muted)}}td,th{{padding:10px;border-bottom:1px solid var(--line)}}tr:last-child td{{border-bottom:0}}td{{overflow-wrap:anywhere}}ul{{padding-left:22px}}li{{margin:7px 0}}.muted,footer{{color:var(--muted)}}footer{{margin-top:24px;font-size:12px}}
@media(max-width:620px){{.tests{{grid-template-columns:1fr}}.wrap{{padding:16px 12px 45px}}header{{padding:24px}}h1{{font-size:24px}}}}@media print{{body{{background:#fff}}.wrap{{padding:0}}.panel,.test,.metric{{box-shadow:none}}header{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
</style></head><body><main class="wrap">
<header><div class="eyebrow">IT Support / Diagnostics</div><div class="hero"><div><h1>Network Diagnostic Report</h1><p>Generated: {generated}</p></div><span class="chip {overall_class}">{overall}</span></div></header>
{demo_banner}
<section><h2 class="section-title">System overview</h2><div class="metrics">
<div class="metric"><div class="metric-label">Device / hostname</div><div class="metric-value">{hostname}</div></div>
<div class="metric"><div class="metric-label">Operating system</div><div class="metric-value">{os}</div></div>
<div class="metric"><div class="metric-label">Default gateway</div><div class="metric-value">{gateway}</div></div>
<div class="metric"><div class="metric-label">DNS servers</div><div class="metric-value">{dns}</div></div>
</div></section>
<section><h2 class="section-title">Connectivity checks</h2><div class="tests">{cards}</div></section>
<section><h2 class="section-title">Network interfaces</h2><div class="panel"><table><thead><tr><th>Interface</th><th>Type</th><th>IP address</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<section><h2 class="section-title">Findings and next steps</h2><div class="panel"><ul>{findings}</ul></div></section>
<footer>Network Diagnostic Tool v1.0 · {privacy}</footer>
</main></body></html>""".format(
        generated=_safe(report["generated_at_utc"]),
        overall=_safe(status), overall_class=_safe(status.lower()),
        demo_banner=demo_banner, hostname=_safe(network.get("hostname", "Unknown")),
        os=_safe(network.get("os", "Unknown")),
        gateway=_safe(network.get("default_gateway") or "Not detected"),
        dns=_safe(dns_servers), cards="\n".join(cards), rows=rows,
        findings=finding_items, privacy=_safe(report["privacy_note"]),
    )


def save_reports(report: dict, output_dir: str | Path, basename: str | None = None) -> tuple[Path, Path]:
    directory = Path(output_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    if basename is None:
        basename = datetime.now(timezone.utc).strftime("network_report_%Y%m%d_%H%M%S_%f")
    json_path = directory / f"{basename}.json"
    html_path = directory / f"{basename}.html"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    html_path.write_text(render_html(report), encoding="utf-8")
    return json_path.resolve(), html_path.resolve()
