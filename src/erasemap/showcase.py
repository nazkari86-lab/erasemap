# ruff: noqa: E501, RUF001
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any

from erasemap.audit import audit_subject
from erasemap.codec import graph_from_json

SCHEMA_VERSION = "erasemap-jury-showcase-v1"


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _require_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label}: expected {expected!r}, received {actual!r}")


def build_showcase(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    example_path = root / "examples/five_branch_system.json"
    stress_path = root / "benchmark/results/pcug-mechanism-stress-v1.json"
    systems_path = root / "benchmark/results/measured-multiservice-v1-summary.json"
    formal_path = root / "formal/conformance-v1.json"

    graph = graph_from_json(example_path.read_text())
    audit = audit_subject(graph, {}, "subject-1", now_epoch=100)
    _require_equal(audit.status.value, "INCOMPLETE", "live example verdict")
    shortest_path = list(audit.shortest_path.node_ids) if audit.shortest_path else None
    _require_equal(shortest_path, ["source", "template"], "live example shortest path")

    stress = _load_object(stress_path)
    _require_equal(stress.get("trials"), 100, "mechanism stress trial count")
    _require_equal(stress.get("truth_noncomplete"), 75, "mechanism stress non-complete count")
    _require_equal(stress.get("pcug_false_complete"), 0, "PCUG false-complete count")
    _require_equal(stress.get("typed_node_false_complete"), 75, "typed baseline failures")

    systems = _load_object(systems_path)
    _require_equal(systems.get("decision"), "PASS", "measured multi-service decision")
    _require_equal(systems.get("holdout_pairs"), 20, "measured holdout pair count")
    _require_equal(systems.get("complete_rate"), 1.0, "measured completion rate")
    _require_equal(
        systems.get("maximum_retained_data_loss_rate"),
        0.0,
        "measured retained-data loss",
    )

    formal = _load_object(formal_path)
    _require_equal(formal.get("ordering_runs"), 3072, "formal conformance run count")
    _require_equal(formal.get("mismatches"), 0, "formal conformance mismatches")

    source_hashes = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (example_path, stress_path, systems_path, formal_path)
    }
    speedup = float(systems["paired_speedup_geometric_mean"])
    speedup_ci = [float(value) for value in systems["paired_speedup_bootstrap_ci95"]]
    bytes_reduction = float(systems["bytes_reduction"])

    return {
        "schema_version": SCHEMA_VERSION,
        "question": "После запроса на удаление какая зарегистрированная копия или производная всё ещё пригодна к использованию?",
        "live_audit": {
            "status": audit.status.value,
            "shortest_residual_path": shortest_path,
            "interpretation": "Исходная запись помечена удалённой, но активный биометрический шаблон остаётся достижим.",
        },
        "evidence": {
            "mechanism_stress": {
                "scope": "PROJECT_AUTHORED_DEVELOPMENT",
                "cases": int(stress["trials"]),
                "noncomplete_cases": int(stress["truth_noncomplete"]),
                "pcug_false_complete": int(stress["pcug_false_complete"]),
                "typed_node_false_complete": int(stress["typed_node_false_complete"]),
            },
            "measured_multiservice": {
                "scope": "LOCAL_REAL_PROCESSES_SYNTHETIC_IDENTITIES",
                "decision": str(systems["decision"]),
                "holdout_pairs": int(systems["holdout_pairs"]),
                "complete_rate": float(systems["complete_rate"]),
                "speedup_geometric_mean": speedup,
                "speedup_ci95": speedup_ci,
                "bytes_reduction": bytes_reduction,
                "retained_data_loss_rate": float(systems["maximum_retained_data_loss_rate"]),
            },
            "formal_conformance": {
                "scope": "BOUNDED_EXECUTABLE_CONFORMANCE",
                "runs": int(formal["ordering_runs"]),
                "mismatches": int(formal["mismatches"]),
                "records_sha256": str(formal["records_sha256"]),
            },
        },
        "claim_boundary": {
            "supported": "EraSeMap объединяет зарегистрированные физические артефакты, request-scoped влияние на модель, обязательные verifier-каналы, replay, контрпримеры и минимальную remediation в одном fail-closed контракте.",
            "not_supported": "Не заявляются production-внедрение в FaceID/eGov и завершённый независимый hidden challenge.",
            "independence_score": 7.8,
        },
        "source_sha256": source_hashes,
    }


def render_showcase_html(report: dict[str, Any]) -> str:
    live = report["live_audit"]
    evidence = report["evidence"]
    mechanism = evidence["mechanism_stress"]
    systems = evidence["measured_multiservice"]
    formal = evidence["formal_conformance"]
    boundary = report["claim_boundary"]
    embedded = html.escape(json.dumps(report, ensure_ascii=False, sort_keys=True))
    path_text = " → ".join(live["shortest_residual_path"])
    return f"""<!doctype html>
<html lang=\"ru\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
  <title>EraSeMap — проверяемая демонстрация</title>
  <style>
    :root {{ color-scheme: light; --ink:#101114; --muted:#62666d; --line:#d9dce1;
      --paper:#f6f7f8; --accent:#e8532f; --ok:#087f5b; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:white; font:18px/1.45 Inter,Arial,sans-serif; }}
    main {{ max-width:1160px; margin:auto; padding:56px 32px 72px; }}
    h1 {{ max-width:900px; margin:18px 0 16px; font-size:58px; line-height:1.02; letter-spacing:-2px; }}
    h2 {{ margin:0 0 18px; font-size:32px; }}
    .eyebrow {{ color:var(--accent); font-size:14px; font-weight:800; letter-spacing:.12em; text-transform:uppercase; }}
    .lead {{ max-width:800px; color:var(--muted); font-size:24px; }}
    .path {{ margin:42px 0; padding:30px; background:var(--paper); border-left:7px solid var(--accent); }}
    .path strong {{ display:block; margin-bottom:10px; font-size:16px; text-transform:uppercase; }}
    .path span {{ font-size:36px; font-weight:750; }}
    .grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:20px; margin:30px 0 52px; }}
    article {{ min-height:220px; padding:26px; border:1px solid var(--line); }}
    .metric {{ margin:18px 0 4px; font-size:48px; font-weight:800; letter-spacing:-1.5px; }}
    .scope {{ color:var(--muted); font-size:13px; overflow-wrap:anywhere; }}
    .boundary {{ display:grid; grid-template-columns:1fr 1fr; gap:30px; padding-top:38px; border-top:2px solid var(--ink); }}
    .supported {{ color:var(--ok); }} .unsupported {{ color:var(--accent); }}
    details {{ margin-top:40px; }} pre {{ overflow:auto; padding:20px; background:var(--paper); font-size:12px; }}
    @media (max-width:820px) {{ h1{{font-size:42px}} .grid,.boundary{{grid-template-columns:1fr}} }}
  </style>
</head>
<body><main>
  <div class=\"eyebrow\">Proof-carrying unlearning graph</div>
  <h1>Удалить запись недостаточно.</h1>
  <p class=\"lead\">EraSeMap отвечает на проверяемый вопрос: какая зарегистрированная копия или производная всё ещё может использовать данные человека?</p>
  <section class=\"path\" aria-label=\"Кратчайший остаточный путь\">
    <strong>Live audit: {html.escape(live["status"])}</strong><span>{html.escape(path_text)}</span>
    <p>{html.escape(live["interpretation"])}</p>
  </section>
  <h2>Три разных уровня доказательств</h2>
  <section class=\"grid\">
    <article><div class=\"eyebrow\">Механизм</div><div class=\"metric\">0 / {mechanism["noncomplete_cases"]}</div>
      <p>ложных COMPLETE у PCUG против {mechanism["typed_node_false_complete"]} / {mechanism["noncomplete_cases"]} у node-only typed audit.</p>
      <div class=\"scope\">{html.escape(mechanism["scope"])}</div></article>
    <article><div class=\"eyebrow\">Реальные процессы</div><div class=\"metric\">{systems["speedup_geometric_mean"]:.2f}×</div>
      <p>геометрическое ускорение; {systems["bytes_reduction"]:.2%} меньше записанных bytes, completion {systems["complete_rate"]:.0%}.</p>
      <div class=\"scope\">{html.escape(systems["scope"])}</div></article>
    <article><div class=\"eyebrow\">Формальная связь</div><div class=\"metric\">{formal["runs"]} / {formal["runs"]}</div>
      <p>совпадений production exact CDC с exhaustive oracle; mismatches: {formal["mismatches"]}.</p>
      <div class=\"scope\">{html.escape(formal["scope"])}</div></article>
  </section>
  <section class=\"boundary\">
    <div><h2 class=\"supported\">Что доказано</h2><p>{html.escape(boundary["supported"])}</p></div>
    <div><h2 class=\"unsupported\">Что не заявляется</h2><p>{html.escape(boundary["not_supported"])}</p>
      <p><strong>Независимость: {boundary["independence_score"]}/10</strong> до внешнего hidden challenge.</p></div>
  </section>
  <details><summary>Машиночитаемый отчёт и SHA-256 источников</summary><pre>{embedded}</pre></details>
</main></body></html>"""


def write_showcase(repo_root: str | Path, output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report = build_showcase(repo_root)
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    (output / "index.html").write_text(render_showcase_html(report))
    return report
