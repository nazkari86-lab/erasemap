# ruff: noqa: E501
"""Self-contained local API and dashboard for the synthetic bank control plane."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from erasemap.bank_control_plane import SyntheticBankControlPlane


def render_control_plane_html(manifest: dict[str, Any]) -> str:
    """Render the dashboard; it calls only same-origin localhost API endpoints."""
    embedded = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
    template = r"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Orda Bank — EraSeMap Control Plane</title>
<style>
:root{--bg:#070d18;--pane:#101d30;--pane2:#13243a;--line:#233955;--text:#f1f6ff;--muted:#90a4bf;--blue:#57a6ff;--purple:#a384ff;--cyan:#62e0d0;--red:#ff6d82;--amber:#ffc96b;--green:#69df9d;--shadow:0 18px 45px #0007}*{box-sizing:border-box}body{margin:0;background:radial-gradient(850px 540px at 8% -10%,#183968 0,transparent 62%),var(--bg);color:var(--text);font:14px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,sans-serif}button,input{font:inherit}.shell{max-width:1600px;margin:auto;padding:24px}.top{display:flex;justify-content:space-between;align-items:center;gap:18px;padding:4px 0 20px}.brand{display:flex;gap:13px;align-items:center}.logo{width:42px;height:42px;display:grid;place-items:center;border-radius:14px;background:linear-gradient(135deg,var(--blue),var(--purple));font-size:21px;box-shadow:var(--shadow)}.eyebrow{color:var(--cyan);font-size:10px;font-weight:850;letter-spacing:.14em;text-transform:uppercase}.brand h1{font-size:20px;margin:2px 0 0;letter-spacing:-.5px}.pills{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.pill{border:1px solid var(--line);border-radius:999px;padding:7px 10px;font-size:11px;font-weight:760;color:var(--muted)}.pill.live{border-color:#348f74;color:var(--green);background:#69df9d0d}.pill.demo{border-color:#a77d2e;color:var(--amber);background:#ffc96b0b}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}.metric,.card{background:linear-gradient(145deg,#13243af2,#0d1829f2);border:1px solid var(--line);border-radius:17px;box-shadow:var(--shadow)}.metric{padding:15px}.metric b{display:block;font-size:24px;letter-spacing:-.7px}.metric span{display:block;font-size:11px;color:var(--muted);margin-top:2px}.layout{display:grid;grid-template-columns:285px minmax(500px,1fr) 345px;gap:16px}.card{overflow:hidden}.side-head{padding:16px;border-bottom:1px solid var(--line)}.side-head h2,.main-head h2{margin:2px 0 0;font-size:17px;letter-spacing:-.35px}.search{display:flex;gap:8px;margin-top:12px}.search input{min-width:0;width:100%;padding:10px 11px;color:var(--text);background:#091424;border:1px solid #28425f;border-radius:10px;outline:none}.search input:focus{border-color:var(--blue)}.customer-list{height:640px;overflow:auto;padding:8px}.customer{width:100%;padding:11px;border:1px solid transparent;border-radius:11px;background:transparent;color:var(--text);text-align:left;cursor:pointer;margin-bottom:3px}.customer:hover,.customer.selected{background:#1a314e;border-color:#315479}.customer strong{display:block;font-size:12px}.customer small{display:block;color:var(--muted);margin-top:2px}.customer .mini{float:right;font-size:9px;font-weight:800;border-radius:999px;padding:3px 5px;background:#ffffff10;color:var(--muted)}.main{padding:20px}.main-head{display:flex;justify-content:space-between;gap:15px;align-items:flex-start}.customer-title{display:flex;align-items:center;gap:11px}.avatar{width:42px;height:42px;border-radius:50%;display:grid;place-items:center;background:linear-gradient(135deg,#ffd0a1,#e9957e);color:#3c201c;font-weight:900}.customer-title small{color:var(--muted);display:block}.verdict{border-radius:999px;padding:7px 10px;font-weight:850;font-size:11px;white-space:nowrap}.verdict.COMPLETE{background:#69df9d1c;color:var(--green);border:1px solid #319063}.verdict.INCOMPLETE{background:#ff6d821b;color:var(--red);border:1px solid #a94356}.verdict.UNVERIFIED,.verdict.NOT_REQUESTED{background:#ffc96b18;color:var(--amber);border:1px solid #967130}.reason{margin:16px 0;padding:13px 14px;border-left:3px solid var(--blue);color:#c4d3e5;background:#091525;border-radius:8px;font-size:12px}.topology{position:relative;min-height:338px;padding:15px;display:grid;grid-template-columns:repeat(3,1fr);gap:12px;background:linear-gradient(90deg,#ffffff04 1px,transparent 1px),linear-gradient(#ffffff04 1px,transparent 1px);background-size:35px 35px;border-radius:14px}.artifact{position:relative;padding:13px;border-radius:13px;border:1px solid #2c4664;background:#102238;min-height:124px;transition:.28s}.artifact:before{content:"";position:absolute;inset:0;border-radius:13px;opacity:.12;background:var(--tone);pointer-events:none}.artifact .conn{font-size:10px;font-weight:850;letter-spacing:.09em;color:var(--tone);text-transform:uppercase}.artifact strong{display:block;margin-top:8px;font-size:13px}.artifact small{display:block;color:var(--muted);font-size:10px;margin-top:3px}.state{display:inline-block;margin-top:12px;padding:4px 6px;border-radius:999px;background:#ffffff0c;color:var(--tone);font-size:9px;font-weight:900;letter-spacing:.08em}.artifact.ACTIVE{--tone:var(--red);border-color:#9a4257}.artifact.ERASED{--tone:var(--green);border-color:#397d60}.artifact.LATENT{--tone:var(--amber);border-color:#98793b}.artifact.UNVERIFIED{--tone:#a9b7c7;border-style:dashed}.detail-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:14px;margin-top:15px}.subcard{padding:14px;border:1px solid var(--line);border-radius:13px;background:#0a1626}.subcard h3{font-size:12px;margin:0 0 8px}.plan-row,.event{padding:8px 0;border-bottom:1px solid #ffffff0d;font-size:11px}.plan-row:last-child,.event:last-child{border:0}.connector{padding:13px 15px;border-bottom:1px solid var(--line);display:flex;gap:10px;align-items:flex-start}.connector:last-child{border:0}.connector-dot{width:9px;height:9px;border-radius:50%;margin-top:5px;box-shadow:0 0 12px currentColor}.connector strong{font-size:12px;display:block}.connector small{font-size:10px;color:var(--muted);display:block;margin-top:2px}.connector span{margin-left:auto;font-size:9px;color:var(--green);font-weight:900}.action-card{padding:16px;border-top:1px solid var(--line)}.action-card h3{margin:0 0 6px;font-size:14px}.action-card p{margin:0 0 11px;color:var(--muted);font-size:11px}.action{width:100%;padding:12px;border:1px solid #3c66a0;border-radius:11px;color:white;background:linear-gradient(110deg,#276bc4,#7b5bdc);font-weight:800;text-align:left;cursor:pointer}.action:disabled{opacity:.35;cursor:not-allowed}.footer{margin-top:16px;padding:12px 14px;border-left:3px solid var(--amber);border-radius:7px;background:#ffc96b0d;color:#d4c291;font-size:11px}.empty{padding:16px;color:var(--muted);font-size:12px}@media(max-width:1120px){.layout{grid-template-columns:260px 1fr}.right{grid-column:1/-1;display:grid;grid-template-columns:1fr 1fr}.right .action-card{border-top:0;border-left:1px solid var(--line)}}@media(max-width:760px){.shell{padding:14px}.metrics{grid-template-columns:1fr 1fr}.layout{grid-template-columns:1fr}.customer-list{height:240px}.right{display:block}.right .action-card{border-top:1px solid var(--line);border-left:0}.top{align-items:flex-start}.top .pills{display:none}.topology{grid-template-columns:1fr 1fr}.detail-grid{grid-template-columns:1fr}}
</style>
<style>
body{overflow-x:hidden}.shell,.layout>*,.metrics>*,.brand,.brand>div,.customer-title,.customer-title>div{min-width:0}.brand h1,.metric span,.customer-title small,.reason,.footer{overflow-wrap:anywhere}
@media(max-width:480px){.shell{width:100%;padding:12px}.brand h1{font-size:17px;line-height:1.15}.logo{width:40px;min-width:40px}.metrics{gap:8px}.metric{padding:12px}.metric span{font-size:10px}.main{padding:14px}.main-head{flex-wrap:wrap}.verdict{margin-left:53px}.topology{grid-template-columns:1fr}.customer-title{align-items:flex-start}.customer-title small{font-size:10px}}
</style></head><body><main class="shell"><header class="top"><div class="brand"><div class="logo">◈</div><div><div class="eyebrow">EraSeMap connector pack v1</div><h1>Orda Bank · Synthetic KYC Control Plane</h1></div></div><div class="pills"><span class="pill live">● LOCAL API CONNECTED</span><span class="pill demo">SYNTHETIC · NO REAL DATA</span></div></header><section class="metrics" id="metrics"></section><section class="layout"><aside class="card"><div class="side-head"><div class="eyebrow">Customer registry</div><h2>512 synthetic clients</h2><div class="search"><input id="search" placeholder="Search ID or client…"></div></div><div class="customer-list" id="customers"></div></aside><section class="card main"><div class="main-head"><div class="customer-title"><div class="avatar" id="avatar">AS</div><div><div class="eyebrow">Deletion request workspace</div><h2 id="customerName">Loading…</h2><small id="customerMeta"></small></div></div><div class="verdict NOT_REQUESTED" id="verdict">NOT_REQUESTED</div></div><div class="reason" id="reason"></div><div class="topology" id="artifacts"></div><div class="detail-grid"><div class="subcard"><h3>Exact plan / dry run</h3><div id="plan"></div></div><div class="subcard"><h3>Evidence event log</h3><div id="events"></div></div></div></section><aside class="card right"><div class="side-head"><div class="eyebrow">Registered connectors</div><h2>Scope & health</h2></div><div id="connectors"></div><div class="action-card"><h3 id="actionTitle">Loading control…</h3><p id="actionDescription"></p><button class="action" id="action" disabled>Loading…</button></div></aside></section><footer class="footer" id="boundary"></footer></main><script>const initial=__MANIFEST__;let currentId=initial.demo_customer_id;let overview=initial;let current=null;const $=s=>document.querySelector(s);const api=(path,options={})=>fetch(path,options).then(async r=>{const body=await r.json();if(!r.ok)throw new Error(body.error||'Request failed');return body});function statusTone(status){return status==='COMPLETE'?'COMPLETE':status==='INCOMPLETE'?'INCOMPLETE':'UNVERIFIED'}function initials(name){return name.split(' ').filter(Boolean).slice(0,2).map(x=>x[0]).join('').toUpperCase()}function esc(v){return String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}function renderMetrics(){const counts=overview.request_counts||{};$('#metrics').innerHTML=`<div class="metric"><b>${overview.customer_count}</b><span>Synthetic customers</span></div><div class="metric"><b>${overview.registered_artifact_count.toLocaleString()}</b><span>Registered artifacts</span></div><div class="metric"><b>${overview.connectors.length}</b><span>Connector contracts</span></div><div class="metric"><b>${counts.VERIFIED||0}</b><span>Replay-verified requests</span></div>`}function renderConnectors(){$('#connectors').innerHTML=overview.connectors.map(c=>`<div class="connector"><i class="connector-dot" style="color:${c.color};background:${c.color}"></i><div><strong>${esc(c.name)}</strong><small>${esc(c.artifact_label)} · ${esc(c.methods.join(' · '))}</small></div><span>READY</span></div>`).join('')}function renderCustomerList(items){const root=$('#customers');root.innerHTML=items.length?items.map(c=>`<button class="customer ${c.customer_id===currentId?'selected':''}" data-id="${esc(c.customer_id)}"><span class="mini">${esc(c.stage)}</span><strong>${esc(c.display_name)}</strong><small>${esc(c.customer_id)} · ${esc(c.account_alias)}</small></button>`).join(''):'<div class="empty">No synthetic customer matches.</div>';root.querySelectorAll('.customer').forEach(b=>b.onclick=()=>selectCustomer(b.dataset.id))}function renderCurrent(){if(!current)return;const c=current.customer,v=current.verdict;$('#avatar').textContent=initials(c.display_name);$('#customerName').textContent=c.display_name;$('#customerMeta').textContent=`${c.customer_id} · ${c.account_alias} · ${c.risk_tier} risk · ${current.retained_customer_count} retained customers protected`;const verdict=$('#verdict');verdict.className=`verdict ${statusTone(v.status)}`;verdict.textContent=v.status;$('#reason').textContent=v.reason;$('#artifacts').innerHTML=current.artifacts.map(a=>`<article class="artifact ${a.state}"><div class="conn">${esc(a.connector_id)}</div><strong>${esc(a.label)}</strong><small>${esc(a.kind)}</small><span class="state">${esc(a.state)}</span></article>`).join('');$('#plan').innerHTML=current.dry_run.length?current.dry_run.map(x=>`<div class="plan-row"><b>${esc(x.connector)}</b> · ${esc(x.action)} <span style="float:right;color:var(--cyan);font-size:9px">${esc(x.status)}</span></div>`).join(''):'<div class="empty">No additional action is planned.</div>';$('#events').innerHTML=current.event_log.length?current.event_log.map(e=>`<div class="event">${esc(e)}</div>`).join(''):'<div class="empty">No action has been executed. Start with a dry-run request.</div>';const action=$('#action'),next=current.next_action;$('#actionTitle').textContent=next?'Approval-required action':'Synthetic certificate issued';$('#actionDescription').textContent=next?`Dry run is visible. Confirm the next controlled operation: ${current.next_action_label}.`:'All six registered channels passed the synthetic replay. A topology change would invalidate this certificate.';action.disabled=!next;action.textContent=next?current.next_action_label:'Lifecycle verified';action.onclick=next?()=>executeAction(next):null}async function selectCustomer(id){currentId=id;current=await api(`/api/customers/${encodeURIComponent(id)}`);renderCurrent();const items=await api('/api/customers?limit=80');renderCustomerList(items.customers)}async function executeAction(action){try{current=await api(`/api/customers/${encodeURIComponent(currentId)}/actions/${action}`,{method:'POST'});renderCurrent();overview=await api('/api/overview');renderMetrics();const items=await api('/api/customers?limit=80');renderCustomerList(items.customers)}catch(error){$('#reason').textContent=`Safe refusal: ${error.message}`}}let searchTimer;$('#search').oninput=e=>{clearTimeout(searchTimer);searchTimer=setTimeout(async()=>{const items=await api(`/api/customers?limit=80&query=${encodeURIComponent(e.target.value)}`);renderCustomerList(items.customers)},150)};async function boot(){try{overview=await api('/api/overview');renderMetrics();renderConnectors();$('#boundary').textContent=overview.claim_boundary;const items=await api('/api/customers?limit=80');renderCustomerList(items.customers);await selectCustomer(currentId)}catch(error){$('#reason').textContent=`Local control-plane unavailable: ${error.message}`}}boot();</script></body></html>"""
    return template.replace("__MANIFEST__", embedded)


def write_control_plane_demo(
    output_dir: str | Path, *, customer_count: int = 512
) -> dict[str, Any]:
    """Write assets for the local dashboard and return its manifest."""
    plane = SyntheticBankControlPlane(customer_count=customer_count)
    manifest = plane.manifest()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(render_control_plane_html(manifest))
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    (output / "README.txt").write_text(
        "Run: erasemap bank-control-plane serve --port 8765\n"
        "Then open: http://127.0.0.1:8765\n"
        "This is a local synthetic demo; no real customer or bank is connected.\n"
    )
    return manifest


def make_control_plane_server(
    plane: SyntheticBankControlPlane, *, host: str = "127.0.0.1", port: int = 8765
) -> ThreadingHTTPServer:
    """Create a loopback HTTP server exposing only synthetic local data."""
    page = render_control_plane_html(plane.manifest()).encode()

    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

        def _send_page(self) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(page)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_page()
                return
            if parsed.path == "/api/overview":
                self._send_json(plane.overview())
                return
            if parsed.path == "/api/customers":
                values = parse_qs(parsed.query)
                query = values.get("query", [""])[0]
                raw_limit = values.get("limit", ["80"])[0]
                try:
                    self._send_json({"customers": plane.list_customers(query=query, limit=int(raw_limit))})
                except ValueError as error:
                    self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            prefix = "/api/customers/"
            if parsed.path.startswith(prefix):
                customer_id = unquote(parsed.path.removeprefix(prefix))
                try:
                    self._send_json(plane.customer_snapshot(customer_id))
                except ValueError as error:
                    self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
                return
            self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            prefix = "/api/customers/"
            suffix = "/actions/"
            if not self.path.startswith(prefix) or suffix not in self.path:
                self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            customer_id, action = self.path.removeprefix(prefix).split(suffix, maxsplit=1)
            try:
                self._send_json(plane.execute_action(unquote(customer_id), unquote(action)))
            except ValueError as error:
                self._send_json({"error": str(error)}, HTTPStatus.CONFLICT)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return ThreadingHTTPServer((host, port), Handler)


def serve_control_plane(
    *, customer_count: int = 512, host: str = "127.0.0.1", port: int = 8765
) -> None:
    """Serve the interactive synthetic control plane until interrupted."""
    server = make_control_plane_server(
        SyntheticBankControlPlane(customer_count=customer_count), host=host, port=port
    )
    try:
        server.serve_forever()
    finally:
        server.server_close()
