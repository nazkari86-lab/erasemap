from __future__ import annotations

import hashlib
import random
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from types import MappingProxyType

from erasemap.domain import (
    Artifact,
    ArtifactState,
    ArtifactType,
    Edge,
    EdgeType,
    ErasureGraph,
    Evidence,
    EvidenceKind,
    PolicyDecision,
    RemediationAction,
    RetentionPolicy,
)


class FaultKind(StrEnum):
    ORPHANED_RECORD = "ORPHANED_RECORD"
    ORPHANED_TEMPLATE = "ORPHANED_TEMPLATE"
    UNPURGED_INDEX = "UNPURGED_INDEX"
    STALE_CACHE = "STALE_CACHE"
    EXPIRED_BACKUP = "EXPIRED_BACKUP"
    MODEL_FALSELY_UNLEARNED = "MODEL_FALSELY_UNLEARNED"
    REPLAYED_RECEIPT = "REPLAYED_RECEIPT"
    MODIFIED_RECEIPT = "MODIFIED_RECEIPT"
    WRONG_GRAPH_ROOT = "WRONG_GRAPH_ROOT"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"


@dataclass(frozen=True, slots=True)
class InjectedFault:
    kind: FaultKind
    artifact_id: str


@dataclass(frozen=True, slots=True)
class GroundTruth:
    faults: tuple[InjectedFault, ...]
    has_prohibited_residual: bool
    residual_artifact_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class GeneratedCase:
    graph: ErasureGraph
    evidence: Mapping[str, Evidence]
    actions: tuple[RemediationAction, ...]
    policies: tuple[RetentionPolicy, ...]
    truth: GroundTruth
    topology: str
    seed: int


_TOPOLOGIES = ("government-identity", "bank-kyc", "school-access")
_DERIVED_TYPES = (
    ArtifactType.BIOMETRIC_TEMPLATE,
    ArtifactType.SEARCH_INDEX_ENTRY,
    ArtifactType.CACHE_ENTRY,
    ArtifactType.BACKUP_COPY,
    ArtifactType.MODEL_INFLUENCE,
    ArtifactType.AUDIT_RECEIPT,
)
_EDGE_FOR_TYPE = {
    ArtifactType.BIOMETRIC_TEMPLATE: EdgeType.DERIVED_INTO,
    ArtifactType.SEARCH_INDEX_ENTRY: EdgeType.INDEXED_AS,
    ArtifactType.CACHE_ENTRY: EdgeType.COPIED_TO,
    ArtifactType.BACKUP_COPY: EdgeType.BACKED_UP_AS,
    ArtifactType.MODEL_INFLUENCE: EdgeType.USED_TO_TRAIN,
    ArtifactType.AUDIT_RECEIPT: EdgeType.DERIVED_INTO,
}
_FAULT_TYPE = {
    FaultKind.ORPHANED_RECORD: ArtifactType.SOURCE_RECORD,
    FaultKind.ORPHANED_TEMPLATE: ArtifactType.BIOMETRIC_TEMPLATE,
    FaultKind.UNPURGED_INDEX: ArtifactType.SEARCH_INDEX_ENTRY,
    FaultKind.STALE_CACHE: ArtifactType.CACHE_ENTRY,
    FaultKind.EXPIRED_BACKUP: ArtifactType.BACKUP_COPY,
    FaultKind.MODEL_FALSELY_UNLEARNED: ArtifactType.MODEL_INFLUENCE,
    FaultKind.REPLAYED_RECEIPT: ArtifactType.AUDIT_RECEIPT,
    FaultKind.MODIFIED_RECEIPT: ArtifactType.AUDIT_RECEIPT,
    FaultKind.WRONG_GRAPH_ROOT: ArtifactType.AUDIT_RECEIPT,
    FaultKind.MISSING_EVIDENCE: ArtifactType.SOURCE_RECORD,
}


def _commitment(seed: int, node_id: str) -> str:
    digest = hashlib.sha256(f"erasemap:{seed}:{node_id}".encode()).hexdigest()
    return f"sha256:{digest}"


def _valid_evidence(node: Artifact) -> Evidence:
    evidence_id = f"evidence-{node.id}"
    if node.type in {
        ArtifactType.SOURCE_RECORD,
        ArtifactType.BIOMETRIC_TEMPLATE,
        ArtifactType.SEARCH_INDEX_ENTRY,
    }:
        return Evidence(
            evidence_id,
            node.id,
            kind=EvidenceKind.ABSENCE_CHECK,
            commitment=node.commitment,
            observed_absent=True,
            issued_epoch=10,
            expires_epoch=1_000,
        )
    if node.type is ArtifactType.CACHE_ENTRY:
        return Evidence(
            evidence_id,
            node.id,
            kind=EvidenceKind.CACHE_INVALIDATION,
            observed_absent=True,
            issued_epoch=10,
            expires_epoch=1_000,
            metadata=(("propagation_deadline", "50"),),
        )
    if node.type is ArtifactType.BACKUP_COPY:
        return Evidence(
            evidence_id,
            node.id,
            kind=EvidenceKind.CRYPTO_ERASURE,
            valid_signature=True,
            issued_epoch=10,
            expires_epoch=1_000,
            metadata=(("key_destroyed", "true"),),
        )
    if node.type is ArtifactType.MODEL_INFLUENCE:
        return Evidence(
            evidence_id,
            node.id,
            kind=EvidenceKind.MODEL_AUDIT,
            issued_epoch=10,
            expires_epoch=1_000,
            metadata=(("pass", "true"), ("protocol_id", "model-v1"), ("reference_id", "r1")),
        )
    return Evidence(
        evidence_id,
        node.id,
        kind=EvidenceKind.SIGNED_STATEMENT,
        valid_signature=True,
        issued_epoch=10,
        expires_epoch=1_000,
        metadata=(
            ("expected_graph_root", "root-valid"),
            ("graph_root", "root-valid"),
            ("nonce", node.id),
        ),
    )


def _first_of_type(nodes: Mapping[str, Artifact], artifact_type: ArtifactType) -> str:
    return min(node.id for node in nodes.values() if node.type is artifact_type)


def _activate(nodes: dict[str, Artifact], evidence: dict[str, Evidence], node_id: str) -> None:
    nodes[node_id] = replace(nodes[node_id], state=ArtifactState.ACTIVE, active_sink=True)
    evidence.pop(node_id, None)


def _inject_fault(
    kind: FaultKind,
    nodes: dict[str, Artifact],
    evidence: dict[str, Evidence],
) -> InjectedFault:
    node_id = _first_of_type(nodes, _FAULT_TYPE[kind])
    if kind in {
        FaultKind.ORPHANED_RECORD,
        FaultKind.ORPHANED_TEMPLATE,
        FaultKind.UNPURGED_INDEX,
        FaultKind.STALE_CACHE,
    }:
        _activate(nodes, evidence, node_id)
    elif kind is FaultKind.EXPIRED_BACKUP:
        nodes[node_id] = replace(nodes[node_id], state=ArtifactState.WAITING_EXPIRY)
        evidence[node_id] = Evidence(
            f"evidence-{node_id}",
            node_id,
            EvidenceKind.EXPIRY_SCHEDULE,
            issued_epoch=10,
            expires_epoch=50,
        )
    elif kind is FaultKind.MODEL_FALSELY_UNLEARNED:
        evidence[node_id] = replace(
            evidence[node_id],
            metadata=(("pass", "false"), ("protocol_id", "model-v1"), ("reference_id", "r1")),
        )
    elif kind is FaultKind.REPLAYED_RECEIPT:
        evidence[node_id] = replace(
            evidence[node_id], metadata=((*evidence[node_id].metadata, ("replayed", "true")))
        )
    elif kind is FaultKind.MODIFIED_RECEIPT:
        evidence[node_id] = replace(evidence[node_id], valid_signature=False)
    elif kind is FaultKind.WRONG_GRAPH_ROOT:
        evidence[node_id] = replace(
            evidence[node_id],
            metadata=(
                ("expected_graph_root", "root-valid"),
                ("graph_root", "root-wrong"),
                ("nonce", node_id),
            ),
        )
    elif kind is FaultKind.MISSING_EVIDENCE:
        evidence.pop(node_id, None)
    return InjectedFault(kind, node_id)


def generate_case(
    *,
    seed: int,
    node_count: int,
    faults: tuple[FaultKind, ...],
) -> GeneratedCase:
    if node_count < 10:
        raise ValueError("node_count must be at least 10")
    if seed < 0:
        raise ValueError("seed cannot be negative")
    rng = random.Random(seed)
    subject_id = "subject-1"
    nodes: dict[str, Artifact] = {}
    edges: list[Edge] = []

    for index in range(node_count):
        node_id = f"node-{index:05d}"
        artifact_type = (
            ArtifactType.SOURCE_RECORD
            if index == 0
            else _DERIVED_TYPES[(index - 1) % len(_DERIVED_TYPES)]
        )
        nodes[node_id] = Artifact(
            id=node_id,
            subject_id=subject_id,
            type=artifact_type,
            state=ArtifactState.ERASED,
            purpose=_TOPOLOGIES[seed % len(_TOPOLOGIES)],
            commitment=_commitment(seed, node_id),
            evidence_id=f"evidence-{node_id}",
        )
        if index:
            parent_id = f"node-{rng.randrange(index):05d}"
            edges.append(Edge(parent_id, node_id, _EDGE_FOR_TYPE[artifact_type]))

    evidence = {node_id: _valid_evidence(node) for node_id, node in nodes.items()}
    injected = tuple(_inject_fault(kind, nodes, evidence) for kind in faults)
    residual_ids = frozenset(fault.artifact_id for fault in injected)
    actions = tuple(
        RemediationAction(
            id=f"erase-{node_id}",
            covers_artifact_ids=frozenset({node_id}),
            cost=1 + rng.randrange(10),
            result_state=ArtifactState.ERASED,
        )
        for node_id in sorted(nodes)
    )
    policies = tuple(
        RetentionPolicy(node_id, PolicyDecision.ERASE_REQUIRED) for node_id in sorted(nodes)
    )
    return GeneratedCase(
        graph=ErasureGraph(nodes, tuple(edges)),
        evidence=MappingProxyType(evidence),
        actions=actions,
        policies=policies,
        truth=GroundTruth(injected, bool(injected), residual_ids),
        topology=_TOPOLOGIES[seed % len(_TOPOLOGIES)],
        seed=seed,
    )
