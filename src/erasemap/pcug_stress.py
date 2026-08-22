from __future__ import annotations

from dataclasses import dataclass

from erasemap.cdc import evaluate_actions
from erasemap.pcug_domain import (
    CDCProtocol,
    ChannelDecision,
    ChannelResult,
    EdgeKind,
    EdgeState,
    PCUGEdge,
    PCUGGraph,
    PCUGNode,
    PCUGVerdict,
)


@dataclass(frozen=True, slots=True)
class StressRecord:
    case_id: str
    fault: str
    truth: str
    pcug: str
    typed_node_audit: str


def _channel(fault: str) -> ChannelResult:
    if fault in {"model_channel_fail", "replay_mismatch"}:
        decision, upper = ChannelDecision.FAIL, 0.20
    elif fault == "unknown_verifier":
        decision, upper = ChannelDecision.UNKNOWN, 0.0
    else:
        decision, upper = ChannelDecision.PASS, 0.0
    return ChannelResult(
        "deletion_evidence",
        value=upper,
        upper_bound=upper,
        threshold=0.10,
        decision=decision,
        mandatory=True,
        evidence_id="stress-channel-v1" if decision is not ChannelDecision.UNKNOWN else "",
        stratum="mechanism_stress",
    )


def _case(index: int, fault: str) -> tuple[PCUGGraph, CDCProtocol, PCUGVerdict]:
    subject = f"stress-subject-{index:03d}"
    source = PCUGNode("source", "source_record", subject, EdgeState.CLOSED, evidence_id="gone")
    model = PCUGNode("model", "shared_model", "shared", EdgeState.ACTIVE)
    edge_state = EdgeState.CLOSED
    edge = PCUGEdge(
        "source",
        "model",
        EdgeKind.INFLUENCE,
        edge_state,
        request_scoped=True,
        subject_id=subject,
        evidence_id="influence-closed" if edge_state is EdgeState.CLOSED else "",
    )
    graph = PCUGGraph((source, model), (edge,), (_channel(fault),))
    protocol = CDCProtocol(
        f"stress-{index:03d}",
        subject,
        frozenset({"source"}),
        frozenset({"model"}),
        frozenset({"deletion_evidence"}),
    )
    if fault in {"model_channel_fail", "replay_mismatch"}:
        truth = PCUGVerdict.INCOMPLETE
    elif fault == "unknown_verifier":
        truth = PCUGVerdict.UNVERIFIED
    else:
        truth = PCUGVerdict.COMPLETE
    return graph, protocol, truth


def run_stress_benchmark() -> tuple[StressRecord, ...]:
    faults = ("complete", "model_channel_fail", "unknown_verifier", "replay_mismatch")
    records: list[StressRecord] = []
    for index in range(100):
        fault = faults[index % len(faults)]
        graph, protocol, truth = _case(index, fault)
        pcug = evaluate_actions(graph, protocol, ()).verdict
        typed = PCUGVerdict.COMPLETE  # all subject-scoped physical nodes are closed
        records.append(
            StressRecord(f"stress-{index:03d}", fault, truth.value, pcug.value, typed.value)
        )
    return tuple(records)
