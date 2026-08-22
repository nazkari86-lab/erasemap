from __future__ import annotations

from dataclasses import dataclass

from erasemap.multiview_verifier import unknown_channel, upper_bound_channel
from erasemap.pcug_domain import (
    CDCAction,
    CDCProtocol,
    EdgeKind,
    EdgeState,
    PCUGEdge,
    PCUGGraph,
    PCUGNode,
    Transition,
    TransitionTarget,
)

EVIDENCE_SCOPE = "SYNTHETIC_SIMULATOR"

_LABELS: dict[str, dict[str, str]] = {
    "faceid_style": {
        "subject": "Deletion request",
        "source": "Enrollment image",
        "embedding": "Face template",
        "index": "Matcher index",
        "cache": "Unlock cache",
        "backup": "Encrypted backup",
        "model": "Shared verifier",
        "api": "Access decision",
    },
    "egov_style": {
        "subject": "Citizen deletion request",
        "source": "Identity verification image",
        "embedding": "Verification template",
        "index": "Identity search index",
        "cache": "Service cache",
        "backup": "Government-style backup",
        "model": "Shared identity model",
        "api": "Portal decision",
    },
    "kyc_style": {
        "subject": "Customer deletion request",
        "source": "KYC capture",
        "embedding": "KYC template",
        "index": "Customer index",
        "cache": "Risk cache",
        "backup": "Bank-style backup",
        "model": "Shared KYC model",
        "api": "Onboarding decision",
    },
    "school_style": {
        "subject": "Student deletion request",
        "source": "Enrollment capture",
        "embedding": "Access template",
        "index": "Student index",
        "cache": "Gate cache",
        "backup": "School-style backup",
        "model": "Shared access model",
        "api": "Gate decision",
    },
}


@dataclass(frozen=True, slots=True)
class AdapterCase:
    adapter: str
    seed: int
    graph: PCUGGraph
    protocol: CDCProtocol
    actions: tuple[CDCAction, ...]
    evidence_scope: str
    authorized_integration: bool
    disclaimer: str


def adapter_names() -> tuple[str, ...]:
    return tuple(_LABELS)


def _edge(
    source: str,
    target: str,
    kind: EdgeKind = EdgeKind.MATERIAL,
    *,
    request_scoped: bool = False,
) -> PCUGEdge:
    return PCUGEdge(
        source,
        target,
        kind,
        EdgeState.ACTIVE,
        request_scoped=request_scoped,
        subject_id="person-1" if request_scoped or kind is EdgeKind.INFLUENCE else "",
    )


def build_adapter_case(adapter: str, *, seed: int) -> AdapterCase:
    labels = _LABELS.get(adapter)
    if labels is None:
        raise ValueError(f"unknown adapter: {adapter}")
    if seed < 0:
        raise ValueError("adapter seed cannot be negative")
    nodes = (
        PCUGNode("subject", "SUBJECT_CLAIM", "person-1", display_name=labels["subject"]),
        PCUGNode("source", "SOURCE", "person-1", display_name=labels["source"]),
        PCUGNode("embedding", "EMBEDDING", "person-1", display_name=labels["embedding"]),
        PCUGNode("index", "INDEX", "person-1", display_name=labels["index"]),
        PCUGNode("cache", "CACHE", "person-1", display_name=labels["cache"]),
        PCUGNode(
            "backup",
            "BACKUP",
            "person-1",
            active_sink=True,
            display_name=labels["backup"],
        ),
        PCUGNode("model", "SHARED_MODEL", "shared", display_name=labels["model"]),
        PCUGNode("api", "API", "shared", active_sink=True, display_name=labels["api"]),
    )
    edges = (
        _edge("subject", "source", request_scoped=True),
        _edge("source", "embedding", request_scoped=True),
        _edge("embedding", "index", EdgeKind.PROCESSING, request_scoped=True),
        _edge("index", "api", EdgeKind.PROCESSING, request_scoped=True),
        _edge("embedding", "cache", EdgeKind.PROCESSING, request_scoped=True),
        _edge("cache", "api", EdgeKind.PROCESSING, request_scoped=True),
        _edge("source", "backup", request_scoped=True),
        _edge("subject", "model", EdgeKind.INFLUENCE, request_scoped=True),
        _edge("model", "api", EdgeKind.PROCESSING),
    )
    graph = PCUGGraph(
        nodes,
        edges,
        (
            upper_bound_channel("storage", value=0, upper_bound=0, threshold=0),
            unknown_channel("identity_lira", threshold=0.10),
        ),
    )
    protocol = CDCProtocol(
        request_id=f"synthetic-{seed}",
        subject_id="person-1",
        source_ids=frozenset({"subject"}),
        sink_ids=frozenset({"source", "embedding", "index", "cache", "backup", "api"}),
        mandatory_channels=frozenset({"storage", "identity_lira"}),
    )
    model_edge = next(edge for edge in edges if edge.kind is EdgeKind.INFLUENCE)
    cost_offset = seed % 3
    actions = (
        CDCAction(
            "erase-source",
            1 + cost_offset,
            (Transition("source", EdgeState.CLOSED, "absence-source", TransitionTarget.NODE),),
        ),
        CDCAction(
            "purge-derived",
            4 + cost_offset,
            tuple(
                Transition(node, EdgeState.CLOSED, f"absence-{node}", TransitionTarget.NODE)
                for node in ("embedding", "index", "cache", "backup")
            ),
        ),
        CDCAction(
            "unlearn-model",
            7 + cost_offset,
            (Transition(model_edge.id, EdgeState.CLOSED, "model-audit-v1"),),
            result_channels=(
                upper_bound_channel(
                    "identity_lira",
                    value=0.03,
                    upper_bound=0.08,
                    threshold=0.10,
                    evidence_id="model-audit-v1",
                ),
            ),
        ),
        CDCAction(
            "restrict-all-subject-processing",
            30 + cost_offset,
            (
                *(
                    Transition(
                        node,
                        EdgeState.CLOSED,
                        f"enforced-block-{node}",
                        TransitionTarget.NODE,
                    )
                    for node in ("source", "embedding", "index", "cache", "backup")
                ),
                Transition(model_edge.id, EdgeState.CLOSED, "enforced-model-block"),
            ),
            result_channels=(
                upper_bound_channel(
                    "identity_lira",
                    value=0.0,
                    upper_bound=0.0,
                    threshold=0.10,
                    evidence_id="enforced-model-block",
                ),
            ),
        ),
    )
    return AdapterCase(
        adapter=adapter,
        seed=seed,
        graph=graph,
        protocol=protocol,
        actions=actions,
        evidence_scope=EVIDENCE_SCOPE,
        authorized_integration=False,
        disclaimer=(
            "Synthetic architecture simulator; this is not evidence about Apple, eGov, a bank, "
            "a school, or any production integration."
        ),
    )
