# ruff: noqa: E501
"""Standalone, honest visual simulation for an EraSeMap jury demonstration.

This module deliberately does not call a bank, a biometric platform, or an
identity provider.  It is a deterministic synthetic scenario which makes the
otherwise invisible recurrence risk observable during a live presentation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "erasemap-synthetic-bank-demo-v1"


def build_synthetic_bank_demo() -> dict[str, Any]:
    """Return the frozen display scenario used by the local interactive demo."""
    return {
        "schema_version": SCHEMA_VERSION,
        "system_name": "Orda Bank — Synthetic KYC Sandbox",
        "scope": "Synthetic visual demonstration. No bank, eGov, Face ID, or real biometric data is connected.",
        "customer": {"name": "Amina S.", "customer_id": "KZ-DEMO-042", "request_id": "ER-2026-042"},
        "nodes": [
            {"id": "record", "label": "KYC profile", "kind": "Customer record", "stage": "erased"},
            {"id": "template", "label": "Face template", "kind": "Biometric derivative", "stage": "active"},
            {"id": "index", "label": "Vector search", "kind": "Identity lookup", "stage": "erased"},
            {"id": "cache", "label": "Auth cache", "kind": "Fast login", "stage": "erased"},
            {"id": "backup", "label": "Encrypted backup", "kind": "Recovery copy", "stage": "latent"},
            {"id": "model", "label": "Fraud-model channel", "kind": "Model influence", "stage": "unverified"},
        ],
        "steps": [
            {
                "id": "request",
                "title": "Deletion request accepted",
                "short": "Request received",
                "description": "The bank receives Amina's request to erase her KYC biometric data.",
            },
            {
                "id": "delete",
                "title": "Ordinary deletion runs",
                "short": "Delete visible copies",
                "description": "The profile, cache and vector index report deletion. A dashboard could falsely stop here.",
            },
            {
                "id": "recur",
                "title": "A hidden recovery path is observed",
                "short": "Simulate 24 h",
                "description": "The nightly disaster-recovery workflow restores the biometric template from an encrypted backup.",
            },
            {
                "id": "discover",
                "title": "GhostGraph localizes the cause",
                "short": "Run safe probes",
                "description": "Three bounded synthetic probes distinguish backup restore from cache warming, retry replay and index rebuild.",
            },
            {
                "id": "remediate",
                "title": "Exact deletion cut is replayed",
                "short": "Close recovery path",
                "description": "Disable the restoration job, erase the subject backup snapshot, invalidate the face template and verify each artifact.",
            },
            {
                "id": "verify",
                "title": "Evidence-bound result",
                "short": "Verify certificate",
                "description": "The visual simulator returns COMPLETE only for this registered synthetic topology and its declared evidence window.",
            },
        ],
        "claim_boundary": "The interface demonstrates the decision logic on a project-authored synthetic scenario. It is not evidence that any bank, eGov, Face ID, or production biometric system was tested.",
    }


def render_synthetic_bank_demo_html(scenario: dict[str, Any]) -> str:
    """Render one self-contained interactive page without network dependencies."""
    encoded = json.dumps(scenario, ensure_ascii=False, separators=(",", ":"))
    template = r"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Orda Bank — EraSeMap synthetic demo</title>
  <style>
    :root{--bg:#07101d;--panel:#0d1b2c;--line:#243851;--ink:#f3f7fb;--muted:#9aabc0;--blue:#50a7ff;--cyan:#65e6d0;--danger:#ff657a;--warning:#ffca70;--ok:#66df99;--shadow:0 20px 60px #0005}
    *{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at 12% 5%,#12345b 0,transparent 32%),var(--bg);color:var(--ink);font:15px/1.45 Inter,ui-sans-serif,system-ui,-apple-system,sans-serif}
    button{font:inherit;cursor:pointer} .app{max-width:1440px;margin:auto;padding:28px 28px 42px}.top{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:22px}.brand{display:flex;align-items:center;gap:14px}.mark{width:42px;height:42px;display:grid;place-items:center;border-radius:13px;background:linear-gradient(135deg,var(--blue),#8075ff);box-shadow:var(--shadow);font-size:22px}.eyebrow{font-size:11px;color:var(--cyan);font-weight:800;letter-spacing:.12em;text-transform:uppercase}.brand h1{margin:1px 0 0;font-size:19px;letter-spacing:-.3px}.demo{color:var(--warning);border:1px solid #b48238;padding:7px 10px;border-radius:999px;font-weight:700;font-size:12px}
    .customer{display:flex;align-items:center;gap:12px;padding:16px 18px;background:#0d1b2ce6;border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);margin-bottom:20px}.avatar{width:38px;height:38px;border-radius:50%;display:grid;place-items:center;background:#f0b48e;color:#472719;font-weight:900}.customer strong{display:block}.customer small{display:block;color:var(--muted)}.request{margin-left:auto;color:var(--muted);font-family:ui-monospace,SFMono-Regular,monospace;font-size:12px}
    .layout{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(330px,.9fr);gap:20px}.panel{background:linear-gradient(145deg,#102238ee,#0c1829ee);border:1px solid var(--line);box-shadow:var(--shadow);border-radius:20px}.map{padding:20px;min-height:570px;position:relative;overflow:hidden}.panel-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.panel h2{margin:3px 0 0;font-size:20px;letter-spacing:-.4px}.legend{font-size:11px;color:var(--muted);display:flex;gap:10px;flex-wrap:wrap;justify-content:flex-end}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px}.active{background:var(--danger)}.erased{background:var(--ok)}.latent{background:var(--warning)}.unverified{background:var(--muted)}
    .graph{height:455px;position:relative;margin-top:24px;background:linear-gradient(90deg,#ffffff05 1px,transparent 1px),linear-gradient(#ffffff05 1px,transparent 1px);background-size:32px 32px;border-radius:16px}.edge{position:absolute;height:2px;background:#35516e;transform-origin:left center;opacity:.8;transition:.45s}.edge.hot{background:var(--danger);box-shadow:0 0 14px var(--danger);height:3px}.edge.safe{background:var(--ok)}.node{position:absolute;width:142px;min-height:80px;border-radius:14px;padding:12px;border:1px solid #38516d;background:#12263e;transition:.4s;z-index:2}.node .icon{font-size:19px;display:block;margin-bottom:3px}.node strong{display:block;font-size:13px}.node small{display:block;color:var(--muted);font-size:10px;margin-top:3px}.node .state{margin-top:7px;font-size:10px;font-weight:800;letter-spacing:.07em}.node.active-node{border-color:var(--danger);box-shadow:0 0 0 1px #ff657a44,0 0 25px #ff657a24}.node.erased-node{opacity:.62;border-color:#347a61}.node.latent-node{border-color:var(--warning);box-shadow:0 0 24px #ffca7014}.node.unverified-node{border-style:dashed;opacity:.8}.node.n-record{left:5%;top:42%}.node.n-template{left:43%;top:12%}.node.n-index{left:43%;top:42%}.node.n-cache{left:43%;top:72%}.node.n-backup{left:76%;top:27%}.node.n-model{left:76%;top:62%}
    .verdict{margin-top:12px;padding:14px 16px;border-radius:13px;background:#091726;border:1px solid var(--line);display:flex;align-items:center;gap:12px}.verdict-mark{font-weight:900;font-size:17px}.verdict strong{display:block}.verdict small{color:var(--muted)}.verdict.incomplete .verdict-mark{color:var(--danger)}.verdict.unverified .verdict-mark{color:var(--warning)}.verdict.complete .verdict-mark{color:var(--ok)}
    .side{display:grid;gap:20px}.timeline{padding:20px}.step{display:flex;gap:12px;padding:10px 0;border-left:2px solid #334a63;margin-left:7px;padding-left:20px;position:relative;color:var(--muted);transition:.3s}.step:before{content:"";position:absolute;left:-7px;top:15px;width:11px;height:11px;border-radius:50%;background:#334a63}.step.current{color:var(--ink);border-left-color:var(--blue)}.step.current:before{background:var(--blue);box-shadow:0 0 0 5px #50a7ff24}.step.done{color:#d5e5f4}.step.done:before{background:var(--ok)}.step b{display:block;font-size:13px}.step span{font-size:11px}.controls{padding:20px}.controls h3,.evidence h3{margin:0 0 11px;font-size:15px}.controls p,.evidence p{color:var(--muted);font-size:12px;margin:0 0 14px}.actions{display:grid;gap:8px}.actions button{border:1px solid #365270;border-radius:11px;background:#122a45;color:var(--ink);padding:11px 12px;text-align:left;transition:.2s}.actions button:hover:not(:disabled){border-color:var(--blue);transform:translateY(-1px)}.actions button:disabled{opacity:.38;cursor:not-allowed}.actions button.primary{background:linear-gradient(120deg,#1a6cc0,#6958d6);border-color:#5f8ed2;font-weight:800}.actions button .num{display:inline-grid;place-items:center;width:19px;height:19px;border-radius:50%;background:#ffffff19;margin-right:8px;font-size:11px}.evidence{padding:20px}.probe{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #ffffff0e;font-size:12px}.probe:last-child{border:0}.tag{font-size:10px;padding:4px 6px;border-radius:999px;font-weight:800}.tag.wait{color:var(--muted);background:#ffffff10}.tag.pass{color:#062817;background:var(--ok)}.tag.hit{color:#3b0611;background:var(--danger)}.certificate{margin-top:14px;padding:13px;border:1px dashed #4c7ca9;border-radius:12px;background:#0a1a2b}.certificate b{font-size:12px}.hash{font:10px ui-monospace,monospace;color:var(--muted);margin-top:4px;word-break:break-all}.footer{margin-top:20px;padding:13px 16px;border-left:3px solid var(--warning);background:#2f251633;color:#d7c496;font-size:12px;border-radius:8px}
    @media(max-width:900px){.layout{grid-template-columns:1fr}.map{min-height:590px}.top{align-items:flex-start}.demo{white-space:nowrap}.request{display:none}}@media(max-width:560px){.app{padding:16px}.map{padding:15px}.node{width:112px;padding:9px}.node strong{font-size:11px}.node .icon{font-size:16px}.graph{transform:scale(.9);transform-origin:top left;width:111%;margin-bottom:-42px}.customer{align-items:flex-start}.legend{display:none}}
  </style>
</head>
<body>
  <main class="app">
    <header class="top"><div class="brand"><div class="mark">◈</div><div><div class="eyebrow">EraSeMap live demonstration</div><h1 id="systemName"></h1></div></div><div class="demo">SYNTHETIC · NO REAL DATA</div></header>
    <section class="customer"><div class="avatar">AS</div><div><strong id="customerName"></strong><small>Biometric KYC deletion request · visual sandbox</small></div><div class="request" id="requestId"></div></section>
    <section class="layout">
      <section class="panel map"><div class="panel-head"><div><div class="eyebrow">Registered data topology</div><h2>Where can Amina's biometric data return?</h2></div><div class="legend"><span><i class="dot active"></i>active</span><span><i class="dot erased"></i>erased</span><span><i class="dot latent"></i>latent risk</span><span><i class="dot unverified"></i>unverified</span></div></div>
        <div class="graph" id="graph"><div class="edge e-record-template"></div><div class="edge e-record-index"></div><div class="edge e-record-cache"></div><div class="edge e-record-backup"></div><div class="edge e-record-model"></div></div>
        <div class="verdict incomplete" id="verdict"><div class="verdict-mark">●</div><div><strong>INCOMPLETE</strong><small>Face template is still a reachable active biometric derivative.</small></div></div>
      </section>
      <aside class="side"><section class="panel timeline"><div class="eyebrow">Visible story</div><h2>Deletion, recurrence, proof</h2><div id="steps"></div></section>
      <section class="panel controls"><h3 id="actionTitle">Start the synthetic case</h3><p id="actionDescription">Choose a step; the system map will update in real time.</p><div class="actions" id="actions"></div></section>
      <section class="panel evidence"><h3>Evidence & active probes</h3><p id="evidenceText">No probe has run. The system must not claim COMPLETE yet.</p><div id="probes"></div><div class="certificate" id="certificate"><b>Certificate: NOT ISSUED</b><div class="hash">A certificate appears only after remediation and replay verification.</div></div></section></aside>
    </section>
    <div class="footer" id="boundary"></div>
  </main>
  <script>
    const scenario=__SCENARIO__;
    const state={stage:0,probes:0};
    const nodePositions={record:[8,50],template:[48,21],index:[48,50],cache:[48,80],backup:[81,35],model:[81,69]};
    const icons={record:'▣',template:'◉',index:'⌕',cache:'ϟ',backup:'▤',model:'∿'};
    const graph=document.querySelector('#graph');
    document.querySelector('#systemName').textContent=scenario.system_name;
    document.querySelector('#customerName').textContent=`${scenario.customer.name} · ${scenario.customer.customer_id}`;
    document.querySelector('#requestId').textContent=scenario.customer.request_id;
    document.querySelector('#boundary').textContent=scenario.claim_boundary;
    for(const node of scenario.nodes){const el=document.createElement('div');el.id=`node-${node.id}`;el.className=`node n-${node.id}`;el.innerHTML=`<span class="icon">${icons[node.id]}</span><strong>${node.label}</strong><small>${node.kind}</small><div class="state"></div>`;graph.append(el)}
    function edge(name,a,b){const el=document.querySelector('.e-'+name);const [x1,y1]=nodePositions[a], [x2,y2]=nodePositions[b];const dx=x2-x1,dy=y2-y1;el.style.left=`${x1+12}%`;el.style.top=`${y1}%`;el.style.width=`${Math.hypot(dx,dy)}%`;el.style.transform=`rotate(${Math.atan2(dy,dx)*180/Math.PI}deg)`}
    edge('record-template','record','template');edge('record-index','record','index');edge('record-cache','record','cache');edge('record-backup','record','backup');edge('record-model','record','model');
    function nodeStates(){if(state.stage===0)return {record:'active',template:'active',index:'active',cache:'active',backup:'active',model:'active'};if(state.stage===1)return {record:'erased',template:'erased',index:'erased',cache:'erased',backup:'latent',model:'unverified'};if(state.stage===2||state.stage===3)return {record:'erased',template:'active',index:'erased',cache:'erased',backup:'active',model:'unverified'};return {record:'erased',template:'erased',index:'erased',cache:'erased',backup:'erased',model:'erased'}}
    function verdict(){if(state.stage===0)return ['INCOMPLETE','Deletion has not started; biometric artifacts are active.','incomplete'];if(state.stage===1)return ['UNVERIFIED','Visible copies are gone, but the future recovery path and model channel still require evidence.','unverified'];if(state.stage===2)return ['INCOMPLETE','A scheduled recovery made the face template active again.','incomplete'];if(state.stage===3)return ['INCOMPLETE','Cause identified: backup restore. Exact remediation has not yet been replayed.','incomplete'];return ['COMPLETE','All registered synthetic paths were replay-checked. The result expires if this topology or evidence changes.','complete']}
    function renderNodes(){const states=nodeStates();for(const [id,status] of Object.entries(states)){const el=document.querySelector(`#node-${id}`);el.className=`node n-${id} ${status}-node`;el.querySelector('.state').textContent=status.toUpperCase()}for(const edgeEl of document.querySelectorAll('.edge'))edgeEl.className='edge';if(state.stage>=2&&state.stage<4){document.querySelector('.e-record-backup').classList.add('hot');document.querySelector('.e-record-template').classList.add('hot')}if(state.stage>=4){for(const edgeEl of document.querySelectorAll('.edge'))edgeEl.classList.add('safe')}}
    function renderSteps(){const parent=document.querySelector('#steps');parent.innerHTML='';scenario.steps.forEach((step,index)=>{const el=document.createElement('div');el.className=`step ${index<state.stage?'done':''} ${index===state.stage?'current':''}`;el.innerHTML=`<div><b>${index+1}. ${step.short}</b><span>${step.description}</span></div>`;parent.append(el)})}
    function renderControls(){const title=document.querySelector('#actionTitle'),description=document.querySelector('#actionDescription'),actions=document.querySelector('#actions');const step=scenario.steps[Math.min(state.stage,scenario.steps.length-1)];title.textContent=step.title;description.textContent=step.description;actions.innerHTML='';const labels=['Accept deletion request','Delete visible copies','Simulate scheduled restore','Run 3 GhostGraph probes','Apply exact deletion cut','Replay and verify certificate'];labels.forEach((label,index)=>{const btn=document.createElement('button');btn.innerHTML=`<span class="num">${index+1}</span>${label}`;btn.disabled=index!==state.stage;btn.className=index===state.stage?'primary':'';btn.onclick=()=>{state.stage=Math.min(index+1,5);if(index===3)state.probes=3;render()};actions.append(btn)})}
    function renderEvidence(){const text=document.querySelector('#evidenceText'),probes=document.querySelector('#probes'),certificate=document.querySelector('#certificate');const rows=[['P1 · controlled restore window',state.probes>=1?'PASS':'WAIT'],['P2 · cache-warming discriminator',state.probes>=2?'PASS':'WAIT'],['P3 · retry-replay discriminator',state.probes>=3?'BACKUP RESTORE':'WAIT']];if(state.stage<3)text.textContent='No active conclusion before a recurrence is observed and the bounded probes are completed.';else if(state.stage===3)text.textContent='Three safe probes select Backup restore from the declared synthetic candidate catalogue.';else text.textContent='Replay records, artifact commitments and the declared topology satisfy the synthetic certificate contract.';probes.innerHTML=rows.map(([label,status])=>`<div class="probe"><span>${label}</span><b class="tag ${status==='WAIT'?'wait':status==='BACKUP RESTORE'?'hit':'pass'}">${status}</b></div>`).join('');certificate.innerHTML=state.stage>=5?'<b style="color:var(--ok)">✓ Certificate: COMPLETE</b><div class="hash">synthetic-proof: b34e7f… · replay 6/6 · topology v1 · expires on drift</div>':'<b>Certificate: NOT ISSUED</b><div class="hash">A certificate appears only after remediation and replay verification.</div>'}
    function renderVerdict(){const [title,message,kind]=verdict();const el=document.querySelector('#verdict');el.className=`verdict ${kind}`;el.innerHTML=`<div class="verdict-mark">${kind==='complete'?'✓':'●'}</div><div><strong>${title}</strong><small>${message}</small></div>`}
    function render(){renderNodes();renderSteps();renderControls();renderEvidence();renderVerdict()}render();
  </script>
</body></html>"""
    return template.replace("__SCENARIO__", encoded)


def write_synthetic_bank_demo(output_dir: str | Path) -> dict[str, Any]:
    """Write a portable, double-clickable synthetic bank demo."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    scenario = build_synthetic_bank_demo()
    (output / "scenario.json").write_text(
        json.dumps(scenario, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    (output / "index.html").write_text(render_synthetic_bank_demo_html(scenario))
    return scenario
