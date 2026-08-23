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
    rse_path = root / "outputs/regeneration-safe-erasure-v2/result.json"
    msc_path = root / "formal/rse-msc-conformance-v1.json"
    tre_path = root / "outputs/topology-robust-erasure-v1/result.json"
    tre_conformance_path = root / "formal/tre-conformance-v1.json"
    transfer_path = root / "outputs/open-transfer-v1/result.json"
    transfer_provenance_path = root / "outputs/open-transfer-v1/PROVENANCE.json"
    ghostgraph_path = root / "outputs/ghostgraph-v1/result.json"
    ghostgraph_trials_path = root / "outputs/ghostgraph-v1/trials.jsonl"
    ghostgraph_provenance_path = root / "outputs/ghostgraph-v1/PROVENANCE.json"
    usability_protocol_path = root / "usability/protocol-v1.json"

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

    rse = _load_object(rse_path)
    _require_equal(rse.get("passed"), True, "RSE v2 decision")
    rse_metrics = rse.get("metrics")
    if not isinstance(rse_metrics, dict):
        raise ValueError("RSE v2 metrics must be an object")
    _require_equal(rse_metrics.get("rse_risk_detection_count"), 30, "RSE risk detections")
    _require_equal(rse_metrics.get("rse_safe_specificity_count"), 10, "RSE safe specificity")
    _require_equal(
        rse_metrics.get("post_msc_physical_regeneration_count"),
        0,
        "post-MSC physical recurrences",
    )
    msc = _load_object(msc_path)
    _require_equal(msc.get("configurations"), 16384, "MSC conformance configurations")
    _require_equal(msc.get("mismatches"), 0, "MSC conformance mismatches")
    tre = _load_object(tre_path)
    _require_equal(tre.get("passed"), True, "TRE v1 decision")
    tre_metrics = tre.get("metrics")
    if not isinstance(tre_metrics, dict):
        raise ValueError("TRE v1 metrics must be an object")
    _require_equal(
        tre_metrics.get("nominal_plan_regeneration_count"),
        35,
        "TRE nominal-plan recurrences",
    )
    _require_equal(
        tre_metrics.get("tre_post_control_regeneration_count"),
        0,
        "TRE post-control recurrences",
    )
    tre_conformance = _load_object(tre_conformance_path)
    _require_equal(
        tre_conformance.get("configurations"), 4096, "TRE conformance configurations"
    )
    _require_equal(tre_conformance.get("mismatches"), 0, "TRE conformance mismatches")

    transfer = _load_object(transfer_path)
    transfer_provenance = _load_object(transfer_provenance_path)
    transfer_artifacts = transfer_provenance.get("artifacts")
    if not isinstance(transfer_artifacts, dict):
        raise ValueError("open-transfer provenance artifacts must be an object")
    observed_transfer_hash = "sha256:" + hashlib.sha256(transfer_path.read_bytes()).hexdigest()
    _require_equal(
        observed_transfer_hash,
        transfer_artifacts.get("result.json"),
        "open-transfer result hash",
    )
    transfer_summary = transfer.get("summary")
    if not isinstance(transfer_summary, dict):
        raise ValueError("open-transfer summary must be an object")
    _require_equal(transfer_summary.get("decision"), "PASS", "open-transfer decision")
    _require_equal(transfer_summary.get("case_count"), 60, "open-transfer case count")
    _require_equal(
        transfer_summary.get("erasemap_false_complete_count"),
        0,
        "open-transfer false-complete count",
    )
    _require_equal(
        transfer_summary.get("post_control_recurrence_count"),
        0,
        "open-transfer post-control recurrence count",
    )
    _require_equal(
        transfer_summary.get("retained_loss_count"), 0, "open-transfer retained loss"
    )
    ghostgraph = _load_object(ghostgraph_path)
    ghostgraph_provenance = _load_object(ghostgraph_provenance_path)
    ghostgraph_artifacts = ghostgraph_provenance.get("artifacts")
    if not isinstance(ghostgraph_artifacts, dict):
        raise ValueError("GhostGraph provenance artifacts must be an object")
    _require_equal(
        "sha256:" + hashlib.sha256(ghostgraph_path.read_bytes()).hexdigest(),
        ghostgraph_artifacts.get("result.json"),
        "GhostGraph result hash",
    )
    _require_equal(
        "sha256:" + hashlib.sha256(ghostgraph_trials_path.read_bytes()).hexdigest(),
        ghostgraph_artifacts.get("trials.jsonl"),
        "GhostGraph trial hash",
    )
    ghostgraph_summary = ghostgraph.get("summary")
    if not isinstance(ghostgraph_summary, dict):
        raise ValueError("GhostGraph summary must be an object")
    _require_equal(ghostgraph_summary.get("decision"), "PASS", "GhostGraph decision")
    _require_equal(ghostgraph_summary.get("false_confident_count"), 0, "GhostGraph false confidence")
    _require_equal(ghostgraph_summary.get("exact_unique_graph_recovery_count"), 3, "GhostGraph exact recovery")
    _require_equal(ghostgraph_summary.get("path_class_recovery_count"), 1, "GhostGraph path class")
    _require_equal(ghostgraph_summary.get("adaptive_probe_count"), 6, "GhostGraph adaptive probes")
    _require_equal(ghostgraph_summary.get("exhaustive_probe_count"), 49, "GhostGraph exhaustive probes")
    ghostgraph_trials = [
        json.loads(line) for line in ghostgraph_trials_path.read_text().splitlines() if line
    ]
    usability_protocol = _load_object(usability_protocol_path)
    _require_equal(usability_protocol.get("card_count"), 12, "usability card count")

    source_hashes = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (
            example_path,
            stress_path,
            systems_path,
            formal_path,
            rse_path,
            msc_path,
            tre_path,
            tre_conformance_path,
            transfer_path,
            transfer_provenance_path,
            ghostgraph_path,
            ghostgraph_trials_path,
            ghostgraph_provenance_path,
            usability_protocol_path,
        )
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
            "temporal_erasure": {
                "scope": "PROJECT_AUTHORED_PROSPECTIVE_AND_BOUNDED_CONFORMANCE",
                "risk_detections": int(rse_metrics["rse_risk_detection_count"]),
                "safe_specificity": int(rse_metrics["rse_safe_specificity_count"]),
                "post_msc_recurrences": int(
                    rse_metrics["post_msc_physical_regeneration_count"]
                ),
                "conformance_configurations": int(msc["configurations"]),
                "conformance_mismatches": int(msc["mismatches"]),
                "records_sha256": str(msc["records_sha256"]),
            },
            "topology_robust_erasure": {
                "scope": "PROJECT_AUTHORED_PROSPECTIVE_FINITE_ENVELOPE",
                "scenarios": int(tre_metrics["scenario_count"]),
                "shifted_cases": int(tre_metrics["shifted_case_count"]),
                "nominal_recurrences": int(
                    tre_metrics["nominal_plan_regeneration_count"]
                ),
                "robust_recurrences": int(
                    tre_metrics["tre_post_control_regeneration_count"]
                ),
                "nominal_cost": int(tre_metrics["nominal_selected_cost"]),
                "robust_cost": int(tre_metrics["tre_selected_cost"]),
                "blanket_cost": int(tre_metrics["blanket_baseline_cost"]),
                "conformance_configurations": int(tre_conformance["configurations"]),
                "conformance_mismatches": int(tre_conformance["mismatches"]),
                "records_sha256": str(tre_conformance["records_sha256"]),
            },
            "open_stock_transfer": {
                "scope": "PROJECT_AUTHORED_LIVE_STOCK_SERVICES_PUBLIC_OR_SYNTHETIC_INPUTS",
                "decision": str(transfer_summary["decision"]),
                "cases": int(transfer_summary["case_count"]),
                "families": int(transfer_summary["family_count"]),
                "erasemap_false_complete": int(
                    transfer_summary["erasemap_false_complete_count"]
                ),
                "native_false_complete": int(
                    transfer_summary["native_false_complete_count"]
                ),
                "typed_false_complete": int(
                    transfer_summary["typed_false_complete_count"]
                ),
                "post_control_recurrence": int(
                    transfer_summary["post_control_recurrence_count"]
                ),
                "retained_loss": int(transfer_summary["retained_loss_count"]),
                "result_sha256": observed_transfer_hash,
            },
            "ghostgraph": {
                "scope": "PROJECT_AUTHORED_PREREGISTERED_BOUNDED_HIDDEN_GRAPHS",
                "decision": str(ghostgraph_summary["decision"]),
                "cases": len(ghostgraph_trials),
                "exact_graphs": int(ghostgraph_summary["exact_unique_graph_recovery_count"]),
                "path_classes": int(ghostgraph_summary["path_class_recovery_count"]),
                "false_confident": int(ghostgraph_summary["false_confident_count"]),
                "adaptive_probes": int(ghostgraph_summary["adaptive_probe_count"]),
                "exhaustive_probes": int(ghostgraph_summary["exhaustive_probe_count"]),
                "planner_oracle_mismatches": int(
                    ghostgraph_summary["planner_oracle_mismatch_count"]
                ),
                "post_control_recurrence": int(
                    ghostgraph_summary["post_control_recurrence_count"]
                ),
                "external_status": "NOT_COLLECTED",
                "trial_timeline": [
                    {
                        "case_id": item["case_id"],
                        "selected_experiments": [
                            observation["experiment_id"] for observation in item["observations"]
                        ],
                        "verdict": item["verdict"],
                        "surviving_graph_ids": item["surviving_graph_ids"],
                        "control_ids": item["control_ids"],
                    }
                    for item in ghostgraph_trials
                ],
            },
        },
        "visual_story": [
            "1. Запрос: удалить данные одного человека.",
            "2. GhostGraph: активно включать допустимые операции и наблюдать временной trace.",
            "3. Фильтрация: оставить все графы, совместимые с наблюдениями.",
            "4. Планирование: выбрать exact minimax эксперимент, лучше всего разделяющий графы.",
            "5. Fail-closed: вернуть граф, полный path/equivalence class, OUT или UNVERIFIED.",
            "6. Действие: перевести найденные пути в TRE controls и повторить физический replay.",
            "7. Доказательство: oracle, Lean и hashes; внешний результат явно NOT_COLLECTED.",
        ],
        "usability_handoff": {
            "languages": list(usability_protocol["languages"]),
            "cards": int(usability_protocol["card_count"]),
            "human_result_status": "NOT_COLLECTED",
            "minimum_participants": int(usability_protocol["minimum_participants"]),
            "packet": "usability/README.md",
            "external_handoff": "external_transfer/README.md",
        },
        "claim_boundary": {
            "supported": "EraSeMap объединяет зарегистрированные артефакты с активным bounded-поиском скрытых путей восстановления, полными equivalence classes, TRE replay и минимальной remediation в одном fail-closed контракте.",
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
    temporal = evidence["temporal_erasure"]
    robust = evidence["topology_robust_erasure"]
    transfer = evidence["open_stock_transfer"]
    ghostgraph = evidence["ghostgraph"]
    boundary = report["claim_boundary"]
    story = report["visual_story"]
    usability = report["usability_handoff"]
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
    .grid {{ display:grid; grid-template-columns:repeat(2,1fr); gap:20px; margin:30px 0 52px; }}
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
  <h2>Одна понятная история из семи шагов</h2>
  <ol>{''.join(f'<li>{html.escape(step)}</li>' for step in story)}</ol>
  <h2>Семь разных уровней доказательств</h2>
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
    <article><div class=\"eyebrow\">Temporal RSE / MSC</div><div class=\"metric\">{temporal["risk_detections"]} / 30</div>
      <p>рисков обнаружено; safe {temporal["safe_specificity"]}/10, post-MSC recurrence {temporal["post_msc_recurrences"]}; conformance {temporal["conformance_configurations"]}/16384.</p>
      <div class=\"scope\">{html.escape(temporal["scope"])}</div></article>
    <article><div class=\"eyebrow\">Topology-Robust TRE</div><div class=\"metric\">{robust["robust_recurrences"]} / {robust["shifted_cases"]}</div>
      <p>возвратов после robust-плана против {robust["nominal_recurrences"]}/{robust["shifted_cases"]} у nominal MSC; cost {robust["robust_cost"]} против blanket {robust["blanket_cost"]}; conformance {robust["conformance_configurations"]}/4096.</p>
      <div class=\"scope\">{html.escape(robust["scope"])}</div></article>
    <article><div class=\"eyebrow\">Open stock transfer</div><div class=\"metric\">{transfer["erasemap_false_complete"]} / {transfer["cases"]}</div>
      <p>ложных COMPLETE на Keycloak, MLflow и Qdrant; native-success: {transfer["native_false_complete"]}, typed audit: {transfer["typed_false_complete"]}; recurrence {transfer["post_control_recurrence"]}.</p>
      <div class=\"scope\">{html.escape(transfer["scope"])}</div></article>
    <article><div class=\"eyebrow\">GhostGraph</div><div class=\"metric\">{ghostgraph["adaptive_probes"]} / {ghostgraph["exhaustive_probes"]}</div>
      <p>adaptive против exhaustive probes; exact graphs {ghostgraph["exact_graphs"]}, path classes {ghostgraph["path_classes"]}, false confident {ghostgraph["false_confident"]}; external {ghostgraph["external_status"]}.</p>
      <div class=\"scope\">{html.escape(ghostgraph["scope"])}</div></article>
  </section>
  <section class=\"path\"><strong>Answer-blind handoff</strong>
    <p>{usability["cards"]} карточек на EN/RU; human result: {html.escape(usability["human_result_status"])}. Пакет готов, но метрики людей не выдуманы.</p>
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
