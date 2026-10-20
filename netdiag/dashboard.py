"""Local-only, dependency-free desktop web dashboard for Network Diagnostic Tool.

Runs a loopback HTTP server, performs real system/network tests on explicit user
requests, and allows offline report downloads. Never modifies network settings.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import socket
import sys
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .analysis import analyze
from .cli import build_demo_data
from .local import inspect_local_network
from .probes import check_dns, check_https, check_ping, check_tcp
from .report import build_report, render_html
from .utils import run_command

ASSETS = Path(__file__).resolve().parent / 'dashboard_assets'
HOST = '127.0.0.1'
MAX_POST_BYTES = 8192
MAX_HISTORY = 50
HOST_RE = re.compile(r'^[A-Za-z0-9_.-]{1,253}$')


def validate_host(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError('Host must be a string')
    host = value.strip()
    if len(host) > 253 or not host or any(x in host for x in ('/', '\\', '@', '?', '#', ' ', '\r', '\n')):
        raise ValueError('Enter a valid hostname or IP address')
    bare = host.partition('%')[0]
    try:
        ipaddress.ip_address(bare)
        return host
    except ValueError:
        pass
    if not HOST_RE.fullmatch(host) or '..' in host or host.startswith('-'):
        raise ValueError('Enter a valid hostname or IP address')
    if any(not label or label.startswith('-') or label.endswith('-') for label in host.split('.')):
        raise ValueError('Invalid hostname label')
    return host


def validate_url(value: object) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError('Invalid HTTPS URL')
    parsed = urlparse(value.strip())
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('Enter an HTTPS URL without credentials or fragments')
    validate_host(parsed.hostname)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError('Invalid HTTPS port') from exc
    if port is not None and not (1 <= port <= 65535):
        raise ValueError('Invalid HTTPS port')
    return value.strip()


def trace_route(host: str, system: str | None = None) -> dict:
    import platform
    system = system or platform.system()
    begin = time.monotonic()
    if system == 'Windows':
        command = ['tracert', '-d', '-h', '8', '-w', '900', host]
    elif system == 'Darwin':
        command = ['traceroute', '-n', '-m', '8', '-w', '1', '-q', '1', host]
    elif system == 'Linux':
        command = ['traceroute', '-n', '-m', '8', '-w', '1', '-q', '1', host]
    else:
        return {'name': 'Trace route', 'status': 'SKIP', 'message': 'Not supported on this operating system', 'duration_ms': 0, 'details': {'host': host}}
    result = run_command(command, timeout=14)
    lines = [line.strip() for line in result['stdout'].splitlines() if line.strip()]
    # Some OS versions return a nonzero code despite producing useful hop output.
    useful = [line for line in lines if re.match(r'^\s*\d+\s+', line)]
    status = 'PASS' if result['ok'] and useful else 'WARN'
    return {
        'name': 'Trace route', 'status': status,
        'message': f'Traceroute to {host}: {len(useful)} hops reported' if useful else 'Traceroute did not return usable hops (it may be blocked or unavailable)',
        'duration_ms': round((time.monotonic() - begin) * 1000, 2),
        'details': {'host': host, 'hops': useful[:8], 'error': result['stderr'][:250] if not useful else ''},
    }


class AppState:
    def __init__(self, demo: bool = False):
        self.lock = threading.RLock()
        self.demo = demo
        if demo:
            net, examples = build_demo_data()
            self.network = net
            self.tests: dict[str, dict] = {'dns': examples[0], 'ping': examples[1], 'tcp:443': examples[2], 'https': examples[3]}
        else:
            self.network = inspect_local_network()
            self.tests = {}
        self.history: list[dict] = []
        self.updated_at = datetime.now(timezone.utc).isoformat(timespec='seconds')

    def refresh_network(self) -> None:
        self.network = inspect_local_network()
        self.updated_at = datetime.now(timezone.utc).isoformat(timespec='seconds')

    def snapshot(self) -> dict:
        with self.lock:
            tests = {key: dict(value) for key, value in self.tests.items()}
            network = json.loads(json.dumps(self.network))
            all_tests = list(tests.values())
            overview = analyze(network, all_tests, demo=self.demo) if all_tests else {'overall_status': 'INFO', 'findings': ['Run diagnostics to see results.'], 'demo': self.demo}
            return {'network': network, 'tests': tests, 'history': list(self.history), 'analysis': overview,
                    'demo': self.demo, 'updated_at': self.updated_at}

    def record(self, key: str, result: dict) -> None:
        with self.lock:
            self.tests[key] = result
            self.history.insert(0, {'kind': key, 'name': result['name'], 'status': result['status'],
                                    'target': result.get('details', {}).get('host') or result.get('details', {}).get('domain') or result.get('details', {}).get('url', ''),
                                    'time': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                                    'duration_ms': result.get('duration_ms')})
            self.history = self.history[:MAX_HISTORY]
            self.updated_at = datetime.now(timezone.utc).isoformat(timespec='seconds')

    def do(self, body: dict) -> dict:
        kind = str(body.get('kind', ''))
        if self.demo:
            raise ValueError('Demo mode is read-only. Restart without --demo for live tests.')
        timeout = body.get('timeout', 3)
        try:
            timeout = float(timeout)
        except (ValueError, TypeError) as exc:
            raise ValueError('Timeout must be a number') from exc
        if not 0.5 <= timeout <= 10:
            raise ValueError('Timeout must be between 0.5 and 10 seconds')
        if kind == 'refresh':
            with self.lock:
                self.refresh_network()
            return self.snapshot()
        if kind == 'dns':
            domain = validate_host(body.get('target', 'example.com'))
            result = check_dns(domain)
            self.record('dns', result)
        elif kind == 'ping':
            host = validate_host(body.get('target', '1.1.1.1'))
            result = check_ping(host, timeout)
            self.record('ping', result)
        elif kind == 'tcp':
            host = validate_host(body.get('target', 'example.com'))
            try:
                port = int(body.get('port', 443))
            except (ValueError, TypeError) as exc:
                raise ValueError('Port must be a number') from exc
            if not 1 <= port <= 65535:
                raise ValueError('Port must be between 1 and 65535')
            result = check_tcp(host, port, timeout)
            self.record(f'tcp:{port}', result)
        elif kind == 'ports':
            host = validate_host(body.get('target', 'example.com'))
            for port in (53, 80, 443):
                result = check_tcp('1.1.1.1' if host == 'example.com' and port == 53 else host, port, timeout)
                self.record(f'tcp:{port}', result)
        elif kind == 'https':
            url = validate_url(body.get('target', 'https://example.com/'))
            result = check_https(url, timeout)
            self.record('https', result)
        elif kind == 'trace':
            host = validate_host(body.get('target', '1.1.1.1'))
            result = trace_route(host)
            self.record('trace', result)
        elif kind == 'all':
            domain = validate_host(body.get('domain', 'example.com'))
            ping_host = validate_host(body.get('ping_host', '1.1.1.1'))
            tcp_host = validate_host(body.get('tcp_host', 'example.com'))
            https_url = validate_url(body.get('https_url', 'https://example.com/'))
            with self.lock:
                self.refresh_network()
            jobs = {
                'dns': lambda: check_dns(domain),
                'ping': lambda: check_ping(ping_host, timeout),
                'tcp:443': lambda: check_tcp(tcp_host, 443, timeout),
                'https': lambda: check_https(https_url, timeout),
            }
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = {key: pool.submit(job) for key, job in jobs.items()}
                for key, future in futures.items():
                    self.record(key, future.result())
        else:
            raise ValueError('Unknown diagnostic test')
        return self.snapshot()

    def get_report(self) -> dict:
        snapshot = self.snapshot()
        network = snapshot['network']
        tests = list(snapshot['tests'].values())
        summary = snapshot['analysis']
        targets = {key: value.get('details', {}) for key, value in snapshot['tests'].items()}
        return build_report(network, tests, summary, targets)


class RequestHandler(BaseHTTPRequestHandler):
    state: AppState
    server_version = 'NetDiagDesktop/2.0'

    def _headers(self, status: int, typ: str, length: int, filename: str | None = None) -> None:
        self.send_response(status)
        self.send_header('Content-Type', typ)
        self.send_header('Content-Length', str(length))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.send_header('Referrer-Policy', 'no-referrer')
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()

    def _write(self, status: int, content: bytes, typ: str, filename: str | None = None) -> None:
        self._headers(status, typ, len(content), filename)
        self.wfile.write(content)

    def _json(self, status: int, value: dict) -> None:
        self._write(status, json.dumps(value, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8')

    def _local_request(self) -> bool:
        host_header = self.headers.get('Host', '').lower()
        listen_port = self.server.server_address[1]
        return host_header in {f'127.0.0.1:{listen_port}', f'localhost:{listen_port}'}

    def do_GET(self) -> None:
        if not self._local_request():
            self._json(403, {'error': 'Loopback hostname required'})
            return
        path = self.path.split('?', 1)[0]
        if path == '/api/state':
            self._json(200, self.state.snapshot())
            return
        if path in ('/api/report.json', '/api/report.html'):
            report = self.state.get_report()
            now = datetime.now().strftime('%Y%m%d_%H%M%S')
            if path.endswith('.json'):
                self._write(200, json.dumps(report, indent=2, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8', f'network_report_{now}.json')
            else:
                self._write(200, render_html(report).encode('utf-8'), 'text/html; charset=utf-8', f'network_report_{now}.html')
            return
        static = {'/': ('index.html', 'text/html; charset=utf-8'),
                  '/assets/style.css': ('style.css', 'text/css; charset=utf-8'),
                  '/assets/app.js': ('app.js', 'text/javascript; charset=utf-8')}
        if path not in static:
            self._json(404, {'error': 'Not found'})
            return
        filename, mime = static[path]
        try:
            self._write(200, (ASSETS / filename).read_bytes(), mime)
        except OSError:
            self._json(500, {'error': 'Static asset unavailable'})

    def do_POST(self) -> None:
        if not self._local_request():
            self._json(403, {'error': 'Loopback hostname required'})
            return
        origin = self.headers.get('Origin')
        if origin not in (None, f'http://127.0.0.1:{self.server.server_address[1]}', f'http://localhost:{self.server.server_address[1]}'):
            self._json(403, {'error': 'Invalid origin'})
            return
        if self.path != '/api/test':
            self._json(404, {'error': 'Not found'})
            return
        if self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
            self._json(415, {'error': 'JSON request required'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_POST_BYTES:
                self._json(413, {'error': 'Invalid request size'})
                return
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('Expected JSON object')
            result = self.state.do(body)
            self._json(200, result)
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {'error': str(exc)})
        except Exception as exc:
            # Diagnostic failures should usually be represented inside a test result;
            # unexpected failures are deliberately summarized without a traceback.
            self._json(500, {'error': f'Diagnostic failed: {type(exc).__name__}'})

    def log_message(self, format: str, *args: object) -> None:
        if self.path not in ('/api/state',):
            print('[dashboard]', format % args)


def make_server(demo: bool = False, port: int = 0) -> ThreadingHTTPServer:
    state = AppState(demo=demo)
    class Handler(RequestHandler):
        pass
    Handler.state = state
    server = ThreadingHTTPServer((HOST, port), Handler)
    server.daemon_threads = True
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Local desktop dashboard for network diagnostics')
    parser.add_argument('--demo', action='store_true', help='Show simulated sample data (no live tests)')
    parser.add_argument('--no-browser', action='store_true', help='Do not automatically open a browser')
    parser.add_argument('--port', type=int, default=0, help='Local port (default: choose free port)')
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error('--port must be between 0 and 65535')
    server = make_server(args.demo, args.port)
    url = f'http://{HOST}:{server.server_address[1]}/'
    print(f'\nNetwork Diagnostic Tool Desktop v2.0\nDashboard: {url}')
    print('All diagnostics run locally. No network settings will be changed.')
    if args.demo:
        print('DEMO MODE: displayed values are simulated; no live tests run.')
    print('Press Ctrl+C in this window to stop the application.\n')
    if not args.no_browser:
        threading.Timer(0.65, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print('\nClosing dashboard...')
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
