from __future__ import annotations

import hashlib
import json
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from erasemap.audit import audit_subject
from erasemap.baselines import (
    AuditMethod,
    FlatChecklist,
    MethodDecision,
    ReceiptOnly,
    UntypedTraversal,
)
from erasemap.domain import ArtifactType, AuditStatus
from erasemap.generator import FaultKind, GeneratedCase, generate_case
from erasemap.metrics import AggregateReport, TrialOutcome, aggregate_outcomes
from erasemap.planning import greedy_plan

PROTOCOL_SCHEMA = "erasemap-benchmark-v1"


@dataclass(frozen=True, slots=True)
class BenchmarkProtocol:
    schema_version: str
    development_seeds: tuple[int, ...]
    holdout_seeds: tuple[int, ...]
    graph_sizes: tuple[int, ...]
    fault_matrix: tuple[tuple[str, ...], ...]
    methods: tuple[str, ...]
    bootstrap_seed: int
    bootstrap_samples: int
    primary_endpoint: str
    topology_families: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != PROTOCOL_SCHEMA:
            raise ValueError("unsupported benchmark schema")
        if not self.development_seeds or not self.holdout_seeds:
            raise ValueError("both development and holdout seeds are required")
        if not self.graph_sizes or any(size < 10 for size in self.graph_sizes):
            raise ValueError("graph sizes must be at least 10")
        if self.bootstrap_samples <= 0:
            raise ValueError("bootstrap samples must be positive")
        for faults in self.fault_matrix:
            for fault in faults:
                FaultKind(fault)

    def payload(self) -> dict[str, Any]:
        return {
            "bootstrap_samples": self.bootstrap_samples,
            "bootstrap_seed": self.bootstrap_seed,
            "development_seeds": list(self.development_seeds),
            "fault_matrix": [list(faults) for faults in self.fault_matrix],
            "graph_sizes": list(self.graph_sizes),
            "holdout_seeds": list(self.holdout_seeds),
            "methods": list(self.methods),
            "primary_endpoint": self.primary_endpoint,
            "schema_version": self.schema_version,
            "topology_families": list(self.topology_families),
        }


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    protocol_hash: str
    canonical_results: str
    trial_count: int
    failure_count: int


@dataclass(frozen=True, slots=True)
class EraseMapMethod:
    name: str = "erasemap"

    def assess(self, case: GeneratedCase, *, now_epoch: int) -> MethodDecision:
        result = audit_subject(case.graph, case.evidence, "subject-1", now_epoch)
        detected = {
            node_id for node_id, check in result.evidence_checks if not check.valid
        }
        detected.update(path.node_ids[-1] for path in result.residual_paths)
        return MethodDecision(result.status is AuditStatus.COMPLETE, frozenset(detected))


_ALLOWED_FIELDS = {
    "bootstrap_samples",
    "bootstrap_seed",
    "development_seeds",
    "fault_matrix",
    "graph_sizes",
    "holdout_seeds",
    "methods",
    "primary_endpoint",
    "schema_version",
    "topology_families",
}


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def load_protocol(path: str | Path) -> BenchmarkProtocol:
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ValueError("protocol must be a JSON object")
    unknown = set(raw) - _ALLOWED_FIELDS
    if unknown:
        raise ValueError(f"unknown field: {min(unknown)}")
    missing = _ALLOWED_FIELDS - set(raw)
    if missing:
        raise ValueError(f"missing field: {min(missing)}")
    return BenchmarkProtocol(
        schema_version=str(raw["schema_version"]),
        development_seeds=tuple(int(value) for value in raw["development_seeds"]),
        holdout_seeds=tuple(int(value) for value in raw["holdout_seeds"]),
        graph_sizes=tuple(int(value) for value in raw["graph_sizes"]),
        fault_matrix=tuple(tuple(str(fault) for fault in row) for row in raw["fault_matrix"]),
        methods=tuple(str(value) for value in raw["methods"]),
        bootstrap_seed=int(raw["bootstrap_seed"]),
        bootstrap_samples=int(raw["bootstrap_samples"]),
        primary_endpoint=str(raw["primary_endpoint"]),
        topology_families=tuple(str(value) for value in raw["topology_families"]),
    )


def _method(name: str) -> AuditMethod:
    if name == "erasemap":
        return EraseMapMethod()
    if name == "receipt-only":
        return ReceiptOnly()
    if name == "flat-checklist":
        return FlatChecklist(
            frozenset(
                {
                    ArtifactType.SOURCE_RECORD,
                    ArtifactType.BIOMETRIC_TEMPLATE,
                    ArtifactType.SEARCH_INDEX_ENTRY,
                }
            )
        )
    if name == "untyped-traversal":
        return UntypedTraversal()
    raise ValueError(f"unknown benchmark method: {name}")


def _revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, check=False, text=True
    )
    return result.stdout.strip() or "unknown"


def _is_dirty() -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, check=False, text=True
    )
    return bool(result.stdout.strip())


def _report_payload(report: AggregateReport) -> dict[str, Any]:
    return {
        "exact_node_recall": report.exact_node_recall,
        "false_alarm_rate": report.false_alarm_rate,
        "false_complete_rate": report.false_complete_rate,
        "false_negative": report.false_negative,
        "false_positive": report.false_positive,
        "intervals": {
            key: list(value) if value is not None else None
            for key, value in report.intervals.items()
        },
        "mean_remediation_cost": report.mean_remediation_cost,
        "mean_runtime_ms": report.mean_runtime_ms,
        "positive_trials": report.positive_trials,
        "precision": report.precision,
        "recall": report.recall,
        "trials": report.trials,
        "true_negative": report.true_negative,
        "true_positive": report.true_positive,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(_canonical_json(payload) + "\n")


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.write_text("".join(_canonical_json(record) + "\n" for record in records))


def run_protocol(
    protocol: BenchmarkProtocol,
    *,
    output_dir: str | Path,
    split: str = "development",
) -> BenchmarkReport:
    if split not in {"development", "holdout"}:
        raise ValueError("split must be development or holdout")
    if split == "holdout" and _is_dirty():
        raise RuntimeError("holdout requires a clean working tree")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    protocol_json = _canonical_json(protocol.payload())
    protocol_hash = "sha256:" + hashlib.sha256(protocol_json.encode()).hexdigest()
    revision = _revision()
    if split == "holdout":
        lock = output / "holdout.lock.json"
        if lock.exists():
            raise RuntimeError("holdout lock already exists")
        _write_json(lock, {"code_revision": revision, "protocol_hash": protocol_hash})

    seeds = (
        protocol.development_seeds if split == "development" else protocol.holdout_seeds
    )
    trial_records: list[dict[str, Any]] = []
    canonical_records: list[dict[str, Any]] = []
    failure_records: list[dict[str, Any]] = []
    outcomes: dict[str, list[TrialOutcome]] = {name: [] for name in protocol.methods}
    for seed in seeds:
        for size in protocol.graph_sizes:
            for fault_names in protocol.fault_matrix:
                try:
                    faults = tuple(FaultKind(name) for name in fault_names)
                    case = generate_case(seed=seed, node_count=size, faults=faults)
                except Exception as error:  # benchmark failures must be recorded
                    failure_records.append(
                        {
                            "error": f"{type(error).__name__}: {error}",
                            "faults": list(fault_names),
                            "method": None,
                            "node_count": size,
                            "seed": seed,
                        }
                    )
                    continue
                for method_name in protocol.methods:
                    try:
                        method = _method(method_name)
                        started = time.perf_counter_ns()
                        decision = method.assess(case, now_epoch=100)
                        runtime_ms = (time.perf_counter_ns() - started) / 1_000_000
                        plan = greedy_plan(decision.detected_artifact_ids, case.actions)
                        semantic = {
                            "declared_complete": decision.declared_complete,
                            "detected_artifact_ids": sorted(decision.detected_artifact_ids),
                            "faults": list(fault_names),
                            "method": method_name,
                            "node_count": size,
                            "remediation_cost": plan.total_cost,
                            "seed": seed,
                            "truth_artifact_ids": sorted(case.truth.residual_artifact_ids),
                            "truth_positive": case.truth.has_prohibited_residual,
                        }
                        canonical_records.append(semantic)
                        trial_records.append({**semantic, "runtime_ms": runtime_ms})
                        outcomes[method_name].append(
                            TrialOutcome(
                                case.truth.has_prohibited_residual,
                                decision.declared_complete,
                                runtime_ms,
                                float(plan.total_cost),
                                case.truth.residual_artifact_ids,
                                decision.detected_artifact_ids,
                            )
                        )
                    except Exception as error:  # benchmark failures must be recorded
                        failure_records.append(
                            {
                                "error": f"{type(error).__name__}: {error}",
                                "faults": list(fault_names),
                                "method": method_name,
                                "node_count": size,
                                "seed": seed,
                            }
                        )

    summaries = {
        name: _report_payload(
            aggregate_outcomes(
                values,
                bootstrap_seed=protocol.bootstrap_seed,
                bootstrap_samples=protocol.bootstrap_samples,
            )
        )
        for name, values in outcomes.items()
        if values
    }
    manifest = {
        "code_revision": revision,
        "dirty": _is_dirty(),
        "primary_endpoint": protocol.primary_endpoint,
        "protocol_hash": protocol_hash,
        "split": split,
    }
    _write_json(output / "manifest.json", manifest)
    _write_jsonl(output / "trials.jsonl", trial_records)
    _write_json(output / "summary.json", summaries)
    _write_jsonl(output / "failures.jsonl", failure_records)
    canonical_results = _canonical_json(canonical_records)
    return BenchmarkReport(
        protocol_hash,
        canonical_results,
        len(trial_records),
        len(failure_records),
    )
