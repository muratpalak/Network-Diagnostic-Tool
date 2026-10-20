'use strict';
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '—').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const icon = name => `<svg aria-hidden="true"><use href="#i-${name}"></use></svg>`;
const fmt = n => typeof n === 'number' && isFinite(n) ? `${Math.round(n * 10) / 10} ms` : '—';
const statusClass = s => s === 'PASS' ? 'pass' : s === 'WARN' ? 'warn' : s === 'FAIL' ? 'fail' : 'pending';
const statusText = s => s === 'PASS' ? 'Success' : s === 'WARN' ? 'Warning' : s === 'FAIL' ? 'Failed' : 'Not tested';
let data = null;
let busy = false;
let pingSamples = [];
let toastTimer = 0;
let lastChartKey = '';
let ipFamily = 'ipv4';

function toast(message, error = false) {
  const node = $('toast');
  node.textContent = message;
  node.className = `toast visible${error ? ' error' : ''}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.className = 'toast', 4500);
}
async function getState() {
  const response = await fetch('/api/state', {cache:'no-store'});
  if (!response.ok) throw Error(`Server error: ${response.status}`);
  return response.json();
}
async function load() {
  try { render(await getState()); }
  catch (error) { toast(`Cannot reach the local app: ${error.message}`, true); }
}
async function invoke(request, label) {
  if (busy) return;
  busy = true;
  document.querySelectorAll('button[data-test],#run-all,#refresh-btn,#test-all-ports,.port-row').forEach(b => b.disabled = true);
  const button = request.kind === 'all' ? $('run-all') : document.querySelector(`button[data-test="${request.kind}"]`);
  const originalText = button?.textContent;
  if (button) button.textContent = 'Running...';
  toast(`${label} in progress...`);
  try {
    const response = await fetch('/api/test', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({...request, timeout: 3})
    });
    const payload = await response.json();
    if (!response.ok) throw Error(payload.error || `HTTP ${response.status}`);
    if (request.kind === 'ping' || request.kind === 'all') {
      const r = payload.tests.ping;
      // Ping RTT is only usable when returned by the OS, not just command duration.
      const sample = r?.details?.icmp_rtt_ms;
      if (r?.status === 'PASS' && typeof sample === 'number' && Number.isFinite(sample)) {
        pingSamples.push(sample);
        pingSamples = pingSamples.slice(-28);
      }
    }
    render(payload);
    toast(`${label} completed. See the live results.`);
  } catch (error) {
    toast(error.message || 'The test could not be completed', true);
  } finally {
    busy = false;
    document.querySelectorAll('button[data-test],#run-all,#refresh-btn,#test-all-ports,.port-row').forEach(b => b.disabled = Boolean(data?.demo));
    if (button && originalText != null && !button.querySelector('svg')) button.textContent = originalText;
    if (button && originalText != null && button === $('run-all')) button.innerHTML = `${icon('activity')} Run all checks`;
  }
}
function primaryIPv4(net) {
  for (const iface of net.interfaces || []) for (const a of iface.ipv4 || []) {
    if (!a.startsWith('127.') && a !== '0.0.0.0') return a;
  }
  return null;
}
function primaryIPv6(net) {
  for (const iface of net.interfaces || []) for (const a of iface.ipv6 || []) {
    if (a !== '::1' && !a.startsWith('fe80:')) return a;
  }
  return (net.interfaces || []).flatMap(x => x.ipv6 || []).find(x => x !== '::1') || null;
}
function summary(id, text, type) {
  const node = $(id); node.textContent = text; node.className = `metric-value status-pair ${type || ''}`;
}
function render(state) {
  data = state;
  $('demo-banner').hidden = !state.demo;
  const net = state.network || {};
  $('local-ip').textContent = primaryIPv4(net) || 'Not detected';
  $('gateway').textContent = net.default_gateway || 'Not detected';
  const dns = state.tests.dns;
  summary('dns-status', dns ? (dns.status === 'PASS' ? '● Healthy' : dns.status === 'WARN' ? '● Warning' : '● Lookup failed') : 'Not tested', dns ? (dns.status === 'PASS' ? 'ok' : 'bad') : '');
  const https = state.tests.https;
  summary('internet-status', https ? (https.status === 'PASS' ? '● Reachable' : https.status === 'WARN' ? '● HTTP warning' : '● Test failed') : 'Not tested', https ? (https.status === 'PASS' ? 'ok' : https.status === 'WARN' ? 'warn' : 'bad') : '');
  $('last-updated').textContent = (state.demo ? 'Simulated data · ' : 'Last update · ') + new Date(state.updated_at).toLocaleTimeString();
  renderInterfaces(net);
  renderIp(net);
  renderDns(dns, net);
  renderPing(state.tests.ping);
  renderPorts(state.tests);
  renderHttps(https);
  renderTrace(state.tests.trace);
  renderFindings(state);
  renderActivity(state.history);
  if (state.demo) document.querySelectorAll('button[data-test],#run-all,#refresh-btn,#test-all-ports,.port-row').forEach(b => b.disabled = true);
}
function renderInterfaces(net) {
  const interfaces = (net.interfaces || []);
  if (!interfaces.length) { $('interface-list').innerHTML = '<p class="placeholder">No interface IPs detected by this operating system.</p>'; return; }
  $('interface-list').innerHTML = interfaces.map(it => {
    const loop = /^(lo\d*|loopback)/i.test(it.name);
    const list = [...(it.ipv4 || []), ...(it.ipv6 || [])];
    const addr = list.find(x => !x.startsWith('127.') && x !== '::1') || list[0] || '—';
    return `<div class="interface-row"><span class="interface-icon${loop?' loop':''}">${icon(loop ? 'monitor' : 'network')}</span><div class="iface-content"><b>${esc(it.name)}</b><span class="iface-status${loop?' loopstatus':''}">${loop?'Loopback':'IP assigned'}</span><small title="${esc(list.join(', '))}">${esc(addr)}</small></div>${icon('arrow')}</div>`;
  }).join('');
}
function row(label, value) {
  const str = Array.isArray(value) ? value.join(', ') : value;
  const safe = str == null || str === '' ? 'Not collected' : String(str);
  return `<div class="data-row"><span>${esc(label)}</span><b title="${esc(safe)}">${esc(safe)}</b><button class="copy-btn" type="button" data-copy="${esc(safe)}" aria-label="Copy ${esc(label)}" title="Copy ${esc(label)}">${icon('copy')}</button></div>`;
}
function renderIp(net) {
  const addr = ipFamily === 'ipv4' ? primaryIPv4(net) : primaryIPv6(net);
  $('ip-fields').innerHTML = [
    row(ipFamily === 'ipv4' ? 'IPv4 address' : 'IPv6 address', addr || 'Not detected'),
    ...(ipFamily === 'ipv4' ? [row('Subnet mask', (net.interfaces || []).find(it => (it.ipv4 || []).includes(addr))?.subnet_mask || 'Not collected')] : []),
    row('Default gateway', net.default_gateway || 'Not detected'),
    row('DNS server(s)', (net.dns_servers || []).length ? net.dns_servers : 'Not detected'),
    row('Hostname', net.hostname || 'Not detected')
  ].join('');
}
function renderDns(test, net) {
  const elem = $('dns-result');
  if (!test) {
    elem.innerHTML = '<span class="soft-status">Not tested</span><span class="result-meta">—</span>';
  } else {
    const status = test.status;
    elem.innerHTML = `<span class="soft-status ${status === 'PASS'?'good':status==='FAIL'?'fail':'warn'}">${status === 'PASS' ? '✓ Resolved successfully' : status === 'FAIL' ? '✕ Lookup failed' : '⚠ Check result'}</span><span class="result-meta">${fmt(test.duration_ms)}</span>`;
  }
  const details = test?.details || {};
  $('dns-details').innerHTML = [
    ['Domain', details.domain || '—'], ['Resolved IPs', details.addresses?.join(', ') || '—'],
    ['DNS server(s)', (net.dns_servers || []).join(', ') || '—'], ['Response time', test ? fmt(test.duration_ms) : '—']
  ].map(([key, val]) => `<div><span>${esc(key)}</span><b title="${esc(val)}">${esc(val)}</b></div>`).join('');
}
function renderPing(test) {
  const points = pingSamples;
  $('ping-latest').textContent = points.length ? fmt(points[points.length - 1]) : '—';
  $('ping-min').textContent = points.length ? fmt(Math.min(...points)) : '—';
  $('ping-max').textContent = points.length ? fmt(Math.max(...points)) : '—';
  $('ping-count').textContent = points.length;
  const empty = $('chart-empty');
  empty.hidden = points.length > 0;
  $('ping-note').textContent = test ? `${test.status}: ${test.message}` : 'Ping can be blocked without an internet outage.';
  if (points.length) {
    const max = Math.max(10, ...points) * 1.2;
    const coords = points.map((n, i) => [points.length === 1 ? 215 : 7 + (i / (points.length - 1)) * 416, 103 - (n / max) * 88]);
    const path = coords.map(([x,y], i) => `${i ? 'L':'M'} ${x.toFixed(2)} ${y.toFixed(2)}`).join(' ');
    $('ping-line').setAttribute('d', points.length > 1 ? path : `${path} l 0.1 0`);
    $('ping-area').setAttribute('d', points.length > 1 ? `${path} L ${coords[coords.length - 1][0]} 112 L ${coords[0][0]} 112 Z` : '');
  } else { $('ping-line').setAttribute('d',''); $('ping-area').setAttribute('d',''); }
}
function renderPorts(tests) {
  for (const port of [53,80,443]) {
    const elem = $(`port-${port}`);
    const test = tests[`tcp:${port}`];
    elem.className = `state-chip ${statusClass(test?.status)}`;
    elem.textContent = !test ? 'Not tested' : test.status === 'PASS' ? `Open · ${fmt(test.duration_ms)}` : test.status === 'FAIL' ? 'Not reachable' : statusText(test.status);
    elem.title = test?.message || 'Click to test this port';
  }
}
function renderHttps(test) {
  const orb = $('https-orb');
  orb.className = `success-orb ${statusClass(test?.status)}`;
  $('https-orb-label').textContent = test?.status === 'PASS' ? 'Success' : test?.status === 'WARN' ? 'Warning' : test?.status === 'FAIL' ? 'Failed' : 'Untested';
  const details = test?.details || {};
  // A verified HTTPS response implies a TLS handshake; no separate certificate expiry audit is performed.
  const rows = [
    ['HTTP status', details.http_status || '—'], ['TLS connection', details.tls_verified === true ? 'Verified HTTPS' : 'Not confirmed'],
    ['Response time', test ? fmt(test.duration_ms) : '—'], ['Result', statusText(test?.status)]
  ];
  $('https-details').innerHTML = rows.map(([l,v]) => `<div><span>${esc(l)}</span><b>${esc(v)}</b></div>`).join('');
}
function renderTrace(test) {
  if (!test) { $('trace-results').innerHTML = '<p class="placeholder">Run trace to inspect intermediate hops.</p>'; return; }
  const hops = test.details?.hops || [];
  $('trace-results').innerHTML = hops.length ? hops.map((line,i)=>`<div class="route-hop"><span>${i+1}</span><b>${esc(line)}</b></div>`).join('') : `<p class="placeholder">${esc(test.message)} ${esc(test.details?.error || '')}</p>`;
}
function renderFindings(state) {
  const records = Object.values(state.tests || {});
  const items = [];
  if (!records.length) {
    items.push(['neutral', 'i', 'Ready for diagnostics', 'Run all checks to generate recommendations.']);
  } else {
    const anyFailed = records.some(r=>r.status==='FAIL');
    const anyWarn = records.some(r=>r.status==='WARN');
    if (!anyFailed && !anyWarn) items.push(['pass','✓','No failed tests detected','The tests you ran returned successful results.']);
    if (anyFailed) items.push(['fail','!','Some checks failed','See the test cards for targets and failure details.']);
    if (anyWarn) items.push(['warn','!','Warning detected','An ICMP failure alone does not mean internet is down.']);
    (state.analysis?.findings || []).slice(0,3).forEach(f=> items.push(['neutral','i','Diagnostic finding',f]));
  }
  $('findings').innerHTML = items.slice(0,5).map(([cl,symbol,title,desc])=>`<div class="finding"><span class="finding-mark ${cl}">${esc(symbol)}</span><div><b>${esc(title)}</b><small>${esc(desc)}</small></div></div>`).join('');
}
function renderActivity(history) {
  if (!history?.length) { $('activity-list').innerHTML = '<p class="placeholder">No tests run in this session.</p>'; return; }
  $('activity-list').innerHTML = history.slice(0,12).map(rec=>{
    const label = rec.kind.startsWith('tcp') ? 'TCP Port Test' : rec.kind === 'dns' ? 'DNS Lookup' : rec.kind === 'https' ? 'HTTPS Test' : rec.kind === 'ping' ? 'Ping Test' : 'Trace Route';
    const time = new Date(rec.time).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
    return `<div class="activity-row"><span class="time-icon">${icon(rec.kind==='dns'?'database':rec.kind==='ping'?'activity':rec.kind==='https'?'lock':'link')}</span><div class="activity-main"><b>${esc(label)} · ${esc(time)}</b><small>${esc(rec.target || '')}</small></div><span class="state-chip ${statusClass(rec.status)}">${statusText(rec.status)}</span></div>`;
  }).join('');
}

function setup() {
  document.querySelectorAll('button[data-test]').forEach(btn=>btn.addEventListener('click',()=>{
    const kind = btn.dataset.test;
    const targetId = {dns:'dns-target',ping:'ping-target',https:'https-target',trace:'trace-target'}[kind];
    invoke({kind,target:$(targetId).value.trim()}, `${kind.toUpperCase()} test`);
  }));
  $('run-all').addEventListener('click',()=>invoke({kind:'all',domain:$('dns-target').value.trim(),ping_host:$('ping-target').value.trim(),tcp_host:$('tcp-host').value.trim(),https_url:$('https-target').value.trim()},'Full diagnostic scan'));
  $('refresh-btn').addEventListener('click',()=>invoke({kind:'refresh'},'Local configuration refresh'));
  $('test-all-ports').addEventListener('click',()=>invoke({kind:'ports',target:$('tcp-host').value.trim()},'TCP port checks'));
  document.querySelectorAll('.port-row').forEach(btn=>btn.addEventListener('click',()=>{
    const port = Number(btn.dataset.port);
    const host = $('tcp-host').value.trim();
    invoke({kind:'tcp',target:port===53 && host==='example.com'?'1.1.1.1':host,port}, `TCP ${port} test`);
  }));
  for (const family of ['ipv4','ipv6']) $(`tab-${family}`).addEventListener('click',()=>{
    ipFamily=family;
    for(const id of ['ipv4','ipv6']) {const node=$(`tab-${id}`);node.classList.toggle('selected',id===family);node.setAttribute('aria-pressed',String(id===family));}
    if(data) renderIp(data.network);
  });
  document.addEventListener('click', event=>{
    const node=event.target.closest('[data-copy]');
    if (node) {
      if (navigator.clipboard?.writeText) navigator.clipboard.writeText(node.dataset.copy).then(()=>toast('Copied to clipboard')).catch(()=>toast('Clipboard unavailable',true));
      else toast('Clipboard unavailable in this browser',true);
    }
  });
  document.querySelectorAll('.nav-link').forEach(btn=>btn.addEventListener('click',()=>{
    document.querySelectorAll('.nav-link').forEach(node=>node.classList.remove('selected'));
    btn.classList.add('selected');
    $(btn.dataset.jump)?.scrollIntoView({behavior:'smooth',block:'start'});
    $('sidebar').classList.remove('open');
  }));
  $('mobile-open').addEventListener('click',()=>$('sidebar').classList.add('open'));
  $('mobile-close').addEventListener('click',()=>$('sidebar').classList.remove('open'));
  $('search').addEventListener('input',event=>{
    const term = event.target.value.trim().toLowerCase();
    document.querySelectorAll('.dashboard-grid .panel').forEach(panel=>panel.classList.toggle('hide-by-search',!!term && !`${panel.dataset.search} ${panel.textContent}`.toLowerCase().includes(term)));
  });
  document.addEventListener('keydown',event=>{
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase()==='k') {event.preventDefault();$('search').focus();}
    if (event.key==='Escape') {$('search').blur();$('sidebar').classList.remove('open');}
  });
  // Auto-refresh is intentionally view-only: it does not send network traffic.
  setInterval(()=>{if($('auto-refresh').checked && !busy) load();},15000);
  load();
}
setup();
