from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from erasemap.cdc import evaluate_actions, exact_cdc, greedy_cdc
from erasemap.multiview_verifier import compose_channels, unknown_channel, upper_bound_channel
from erasemap.pcug_adapters import adapter_names, build_adapter_case
from erasemap.pcug_domain import (
    CDCAction,
    CDCPlan,
    CDCProtocol,
    EdgeKind,
    EdgeState,
    PCUGGraph,
    PCUGVerdict,
    SolverStatus,
)

PROTOCOL_SCHEMA = "erasemap-pcug-protocol-v1"


@dataclass(frozen=True, slots=True)
class PCUGBenchmarkProtocol:
    schema_version: str
    development_seeds: tuple[int, ...]
    adapters: tuple[str, ...]
    faults: tuple[str, ...]
    audit_methods: tuple[str, ...]
    planning_methods: tuple[str, ...]
    primary_endpoint: str
    bootstrap_seed: int
    bootstrap_samples: int
    holdout_committed: bool
    holdout_seeds: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.schema_version != PROTOCOL_SCHEMA:
            raise ValueError("unsupported PCUG benchmark schema")
        if not self.development_seeds or len(self.development_seeds) != len(
            set(self.development_seeds)
        ):
            raise ValueError("unique development seeds are required")
        if not self.adapters or any(name not in adapter_names() for name in self.adapters):
            raise ValueError("unknown or empty adapter set")
        if not self.faults or not self.audit_methods or not self.planning_methods:
            raise ValueError("fault and method sets cannot be empty")
        if self.primary_endpoint != "false_complete_rate":
            raise ValueError("unsupported primary endpoint")
        if self.bootstrap_samples <= 0:
            raise ValueError("bootstrap samples must be positive")
        if self.holdout_committed != bool(self.holdout_seeds):
            raise ValueError("holdout commitment and seeds disagree")


@dataclass(frozen=True, slots=True)
class BenchmarkRecord:
    task: str
    seed: int
    adapter: str
    fault: str
    method: str
    truth_verdict: str
    verdict: str
    false_complete: bool
    cost: int
    action_ids: tuple[str, ...]
    active_path_count: int
    unknown_constraint_count: int
    exception: str


@dataclass(frozen=True, slots=True)
class BenchmarkMetric:
    trials: int
    truth_noncomplete: int
    false_complete: int
    detected_noncomplete: int
    false_complete_rate: float | None
    noncomplete_recall: float | None
    false_complete_wilson95: tuple[float, float] | None
    mean_cost: float


@dataclass(frozen=True, slots=True)
class PCUGBenchmarkRun:
    protocol_hash: str
    split: str
    records: tuple[BenchmarkRecord, ...]
    metrics: Mapping[str, BenchmarkMetric]
    exception_count: int


_PROTOCOL_FIELDS = frozenset(
    {
        "adapters",
        "audit_methods",
        "bootstrap_samples",
        "bootstrap_seed",
        "development_seeds",
        "faults",
        "holdout",
        "planning_methods",
        "primary_endpoint",
        "schema_version",
    }
)
_HOLDOUT_FIELDS = frozenset({"committed", "seeds"})


def _object(value: object, location: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{location} must be an object")
    return cast(Mapping[str, Any], value)


def _fields(payload: Mapping[str, Any], expected: frozenset[str], location: str) -> None:
    extras = sorted(set(payload) - expected)
    if extras:
        raise ValueError(f"unknown field at {location}: {extras[0]}")
    missing = sorted(expected - set(payload))
    if missing:
        raise ValueError(f"missing field at {location}: {missing[0]}")


def _strings(value: object, location: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{location} must be an array of strings")
    return tuple(cast(list[str], value))


def _integers(value: object, location: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in value
    ):
        raise ValueError(f"{location} must be an array of integers")
    return tuple(cast(list[int], value))


def _integer(value: object, location: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{location} must be an integer")
    return value


def load_pcug_protocol(path: str | Path) -> PCUGBenchmarkProtocol:
    try:
        decoded: object = json.loads(Path(path).read_text())
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid PCUG protocol JSON: {error.msg}") from error
    payload = _object(decoded, "protocol")
    _fields(payload, _PROTOCOL_FIELDS, "protocol")
    holdout = _object(payload["holdout"], "protocol.holdout")
    _fields(holdout, _HOLDOUT_FIELDS, "protocol.holdout")
    committed = holdout["committed"]
    if not isinstance(committed, bool):
        raise ValueError("protocol.holdout.committed must be a boolean")
    return PCUGBenchmarkProtocol(
        schema_version=str(payload["schema_version"]),
        development_seeds=_integers(payload["development_seeds"], "development_seeds"),
        adapters=_strings(payload["adapters"], "adapters"),
        faults=_strings(payload["faults"], "faults"),
        audit_methods=_strings(payload["audit_methods"], "audit_methods"),
        planning_methods=_strings(payload["planning_methods"], "planning_methods"),
        primary_endpoint=str(payload["primary_endpoint"]),
        bootstrap_seed=_integer(payload["bootstrap_seed"], "bootstrap_seed"),
        bootstrap_samples=_integer(payload["bootstrap_samples"], "bootstrap_samples"),
        holdout_committed=committed,
        holdout_seeds=_integers(holdout["seeds"], "holdout.seeds"),
    )


def _replace_node_state(graph: PCUGGraph, node_id: str, state: EdgeState) -> PCUGGraph:
    nodes = tuple(
        replace(
            node,
            state=state,
            active_sink=node.active_sink or (node.id == "backup" and state is EdgeState.ACTIVE),
            evidence_id="",
        )
        if node.id == node_id
        else node
        for node in graph.nodes
    )
    return PCUGGraph(nodes, graph.edges, graph.channel_results)


def _fault_state(
    adapter: str, seed: int, fault: str
) -> tuple[PCUGGraph, CDCProtocol, tuple[str, ...]]:
    case = build_adapter_case(adapter, seed=seed)
    action_map = {action.id: action for action in case.actions}
    complete_actions = tuple(action_map.values())
    complete = evaluate_actions(case.graph, case.protocol, complete_actions).graph
    protocol = case.protocol
    applied = tuple(sorted(action_map))
    if fault == "none":
        return complete, protocol, applied
    if fault == "source_only":
        graph = evaluate_actions(case.graph, protocol, (action_map["erase-source"],)).graph
        return graph, protocol, ("erase-source",)
    if fault == "stale_index":
        return _replace_node_state(complete, "index", EdgeState.ACTIVE), protocol, applied
    if fault == "live_backup":
        return _replace_node_state(complete, "backup", EdgeState.ACTIVE), protocol, applied
    if fault == "artifact_displacement":
        return _replace_node_state(complete, "cache", EdgeState.ACTIVE), protocol, applied
    if fault in {"unknown_model", "compound"}:
        edges = tuple(
            replace(edge, state=EdgeState.UNKNOWN, evidence_id="")
            if edge.kind is EdgeKind.INFLUENCE
            else edge
            for edge in complete.edges
        )
        channels = tuple(
            unknown_channel(
                "identity_lira",
                threshold=channel.threshold,
                evidence_id="",
                stratum=channel.stratum,
            )
            if channel.name == "identity_lira"
            else channel
            for channel in complete.channel_results
        )
        graph = PCUGGraph(complete.nodes, edges, channels)
        if fault == "compound":
            graph = _replace_node_state(graph, "backup", EdgeState.ACTIVE)
        return graph, protocol, applied
    if fault == "single_view_evasion":
        recovery = upper_bound_channel(
            "representation_recovery",
            value=0.18,
            upper_bound=0.25,
            threshold=0.10,
            evidence_id="hidden-probe-v1",
        )
        graph = PCUGGraph(complete.nodes, complete.edges, (*complete.channel_results, recovery))
        protocol = replace(
            protocol,
            mandatory_channels=protocol.mandatory_channels | {"representation_recovery"},
        )
        return graph, protocol, applied
    raise ValueError(f"unknown PCUG fault: {fault}")


def _node_verdict(graph: PCUGGraph, node_ids: frozenset[str]) -> PCUGVerdict:
    states = tuple(graph.node(node_id).state for node_id in sorted(node_ids))
    if any(state is EdgeState.ACTIVE for state in states):
        return PCUGVerdict.INCOMPLETE
    if any(state is EdgeState.UNKNOWN for state in states):
        return PCUGVerdict.UNVERIFIED
    return PCUGVerdict.COMPLETE


def _audit_verdict(method: str, graph: PCUGGraph, protocol: CDCProtocol) -> PCUGVerdict:
    if method == "receipt_only":
        return PCUGVerdict.COMPLETE
    if method == "flat_checklist":
        return _node_verdict(graph, frozenset({"source", "embedding", "index"}))
    if method == "typed_node_audit":
        return _node_verdict(
            graph,
            frozenset({"source", "embedding", "index", "cache", "backup"}),
        )
    if method == "model_only":
        channels = tuple(
            channel for channel in graph.channel_results if channel.name == "identity_lira"
        )
        return compose_channels(channels).verdict
    if method == "pcug":
        return evaluate_actions(graph, protocol, ()).verdict
    raise ValueError(f"unknown PCUG audit method: {method}")


def _delete_all_plan(
    graph: PCUGGraph, protocol: CDCProtocol, actions: tuple[CDCAction, ...]
) -> CDCPlan:
    selected = tuple(action for action in actions if action.permitted)
    report = evaluate_actions(graph, protocol, selected)
    cost = sum(action.cost for action in selected)
    return CDCPlan(
        tuple(sorted(action.id for action in selected)),
        cost,
        report.verdict,
        SolverStatus.APPROXIMATE,
        report,
        0,
        cost if report.verdict is PCUGVerdict.COMPLETE else None,
    )


def _planning_record(method: str, adapter: str, seed: int) -> BenchmarkRecord:
    case = build_adapter_case(adapter, seed=seed)
    if method == "exact_cdc":
        plan = exact_cdc(case.graph, case.protocol, case.actions)
    elif method == "greedy_cdc":
        plan = greedy_cdc(case.graph, case.protocol, case.actions)
    elif method == "delete_all":
        plan = _delete_all_plan(case.graph, case.protocol, case.actions)
    else:
        raise ValueError(f"unknown PCUG planning method: {method}")
    return BenchmarkRecord(
        task="planning",
        seed=seed,
        adapter=adapter,
        fault="initial",
        method=method,
        truth_verdict=plan.report.verdict.value,
        verdict=plan.verdict.value,
        false_complete=False,
        cost=plan.total_cost,
        action_ids=plan.action_ids,
        active_path_count=len(plan.report.active_paths),
        unknown_constraint_count=len(plan.report.unknown_paths) + len(plan.report.unknown_channels),
        exception="",
    )


def _wilson95(numerator: int, denominator: int) -> tuple[float, float] | None:
    if denominator == 0:
        return None
    z = 1.959963984540054
    proportion = numerator / denominator
    denominator_term = 1 + z * z / denominator
    center = (proportion + z * z / (2 * denominator)) / denominator_term
    spread = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / denominator + z * z / (4 * denominator * denominator)
        )
        / denominator_term
    )
    return max(0.0, center - spread), min(1.0, center + spread)


def _aggregate(records: Sequence[BenchmarkRecord]) -> Mapping[str, BenchmarkMetric]:
    groups: dict[str, list[BenchmarkRecord]] = {}
    for record in records:
        groups.setdefault(f"{record.task}:{record.method}", []).append(record)
    metrics: dict[str, BenchmarkMetric] = {}
    for key, items in sorted(groups.items()):
        truth_noncomplete = sum(item.truth_verdict != PCUGVerdict.COMPLETE.value for item in items)
        false_complete = sum(item.false_complete for item in items)
        detected = sum(
            item.truth_verdict != PCUGVerdict.COMPLETE.value
            and item.verdict != PCUGVerdict.COMPLETE.value
            for item in items
        )
        metrics[key] = BenchmarkMetric(
            trials=len(items),
            truth_noncomplete=truth_noncomplete,
            false_complete=false_complete,
            detected_noncomplete=detected,
            false_complete_rate=(false_complete / truth_noncomplete if truth_noncomplete else None),
            noncomplete_recall=(detected / truth_noncomplete if truth_noncomplete else None),
            false_complete_wilson95=_wilson95(false_complete, truth_noncomplete),
            mean_cost=sum(item.cost for item in items) / len(items),
        )
    return MappingProxyType(metrics)


def _protocol_hash(protocol: PCUGBenchmarkProtocol) -> str:
    payload = asdict(protocol)
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def run_pcug_benchmark(
    protocol: PCUGBenchmarkProtocol,
    *,
    split: str,
) -> PCUGBenchmarkRun:
    if split == "holdout" and not protocol.holdout_committed:
        raise RuntimeError("PCUG holdout is not committed")
    if split not in {"development", "holdout"}:
        raise ValueError("split must be development or holdout")
    seeds = protocol.development_seeds if split == "development" else protocol.holdout_seeds
    records: list[BenchmarkRecord] = []
    for seed in seeds:
        for adapter in protocol.adapters:
            for fault in protocol.faults:
                graph, cdc_protocol, action_ids = _fault_state(adapter, seed, fault)
                truth = evaluate_actions(graph, cdc_protocol, ()).verdict
                for method in protocol.audit_methods:
                    try:
                        verdict = _audit_verdict(method, graph, cdc_protocol)
                        records.append(
                            BenchmarkRecord(
                                task="audit",
                                seed=seed,
                                adapter=adapter,
                                fault=fault,
                                method=method,
                                truth_verdict=truth.value,
                                verdict=verdict.value,
                                false_complete=(
                                    truth is not PCUGVerdict.COMPLETE
                                    and verdict is PCUGVerdict.COMPLETE
                                ),
                                cost=0,
                                action_ids=action_ids,
                                active_path_count=len(
                                    evaluate_actions(graph, cdc_protocol, ()).active_paths
                                ),
                                unknown_constraint_count=len(
                                    evaluate_actions(graph, cdc_protocol, ()).unknown_paths
                                ),
                                exception="",
                            )
                        )
                    except Exception as error:  # benchmark failures are retained as data
                        records.append(
                            BenchmarkRecord(
                                "audit",
                                seed,
                                adapter,
                                fault,
                                method,
                                truth.value,
                                PCUGVerdict.UNVERIFIED.value,
                                False,
                                0,
                                action_ids,
                                0,
                                1,
                                f"{type(error).__name__}: {error}",
                            )
                        )
            for method in protocol.planning_methods:
                try:
                    records.append(_planning_record(method, adapter, seed))
                except Exception as error:  # benchmark failures are retained as data
                    records.append(
                        BenchmarkRecord(
                            "planning",
                            seed,
                            adapter,
                            "initial",
                            method,
                            PCUGVerdict.UNVERIFIED.value,
                            PCUGVerdict.UNVERIFIED.value,
                            False,
                            0,
                            (),
                            0,
                            1,
                            f"{type(error).__name__}: {error}",
                        )
                    )
    ordered = tuple(
        sorted(
            records,
            key=lambda item: (item.task, item.seed, item.adapter, item.fault, item.method),
        )
    )
    return PCUGBenchmarkRun(
        protocol_hash=_protocol_hash(protocol),
        split=split,
        records=ordered,
        metrics=_aggregate(ordered),
        exception_count=sum(bool(item.exception) for item in ordered),
    )


def encode_records(records: Sequence[BenchmarkRecord]) -> str:
    return "".join(
        json.dumps(asdict(record), sort_keys=True, separators=(",", ":")) + "\n"
        for record in records
    )
