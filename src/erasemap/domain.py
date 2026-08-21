from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class ArtifactType(StrEnum):
    SOURCE_RECORD = "SOURCE_RECORD"
    BIOMETRIC_TEMPLATE = "BIOMETRIC_TEMPLATE"
    SEARCH_INDEX_ENTRY = "SEARCH_INDEX_ENTRY"
    CACHE_ENTRY = "CACHE_ENTRY"
    BACKUP_COPY = "BACKUP_COPY"
    MODEL_INFLUENCE = "MODEL_INFLUENCE"
    AUDIT_RECEIPT = "AUDIT_RECEIPT"


class ArtifactState(StrEnum):
    ACTIVE = "ACTIVE"
    ERASED = "ERASED"
    BLOCKED = "BLOCKED"
    WAITING_EXPIRY = "WAITING_EXPIRY"
    UNVERIFIED = "UNVERIFIED"


class EdgeType(StrEnum):
    COPIED_TO = "COPIED_TO"
    DERIVED_INTO = "DERIVED_INTO"
    INDEXED_AS = "INDEXED_AS"
    BACKED_UP_AS = "BACKED_UP_AS"
    USED_TO_TRAIN = "USED_TO_TRAIN"
    SUPERSEDED_BY = "SUPERSEDED_BY"


class EvidenceKind(StrEnum):
    ABSENCE_CHECK = "ABSENCE_CHECK"
    CACHE_INVALIDATION = "CACHE_INVALIDATION"
    EXPIRY_SCHEDULE = "EXPIRY_SCHEDULE"
    CRYPTO_ERASURE = "CRYPTO_ERASURE"
    MODEL_AUDIT = "MODEL_AUDIT"
    SIGNED_STATEMENT = "SIGNED_STATEMENT"


class AuditStatus(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    UNVERIFIED = "UNVERIFIED"


class PolicyDecision(StrEnum):
    ERASE_REQUIRED = "ERASE_REQUIRED"
    BLOCK_ALLOWED = "BLOCK_ALLOWED"
    RETENTION_REQUIRED = "RETENTION_REQUIRED"


@dataclass(frozen=True, slots=True)
class Artifact:
    id: str
    subject_id: str
    type: ArtifactType
    state: ArtifactState
    active_sink: bool = False
    purpose: str = ""
    commitment: str = ""
    evidence_id: str | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.subject_id:
            raise ValueError("artifact id and subject id are required")
        if self.state is ArtifactState.ERASED and self.active_sink:
            raise ValueError("erased artifact cannot be an active sink")


@dataclass(frozen=True, slots=True)
class Edge:
    source_id: str
    target_id: str
    type: EdgeType
    cross_subject: bool = False

    def __post_init__(self) -> None:
        if not self.source_id or not self.target_id:
            raise ValueError("edge endpoints are required")


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    artifact_id: str
    kind: EvidenceKind
    valid_signature: bool = False
    commitment: str = ""
    observed_absent: bool = False
    issued_epoch: int = 0
    expires_epoch: int | None = None
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.id or not self.artifact_id:
            raise ValueError("evidence id and artifact id are required")
        if self.issued_epoch < 0:
            raise ValueError("issued epoch cannot be negative")
        if self.expires_epoch is not None and self.expires_epoch < self.issued_epoch:
            raise ValueError("evidence expires before it was issued")

    def metadata_value(self, key: str) -> str | None:
        return dict(self.metadata).get(key)


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    artifact_id: str
    decision: PolicyDecision

    def __post_init__(self) -> None:
        if not self.artifact_id:
            raise ValueError("policy artifact id is required")


@dataclass(frozen=True, slots=True)
class RemediationAction:
    id: str
    covers_artifact_ids: frozenset[str]
    cost: int
    result_state: ArtifactState
    permitted: bool = True

    def __post_init__(self) -> None:
        if not self.id or not self.covers_artifact_ids:
            raise ValueError("action id and coverage are required")
        if self.cost < 0:
            raise ValueError("action cost cannot be negative")
        if self.result_state not in {ArtifactState.ERASED, ArtifactState.BLOCKED}:
            raise ValueError("action must erase or block processing")


@dataclass(frozen=True, slots=True)
class EvidenceCheck:
    valid: bool
    reason: str
    effective_state: ArtifactState


@dataclass(frozen=True, slots=True)
class ResidualPath:
    node_ids: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        if not self.node_ids:
            raise ValueError("residual path cannot be empty")


@dataclass(frozen=True, slots=True)
class AuditResult:
    status: AuditStatus
    residual_paths: tuple[ResidualPath, ...]
    shortest_path: ResidualPath | None
    evidence_checks: tuple[tuple[str, EvidenceCheck], ...]
    reachable_artifact_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class RemediationPlan:
    action_ids: tuple[str, ...]
    total_cost: int
    covered_artifact_ids: frozenset[str]
    uncovered_artifact_ids: frozenset[str]

    def __post_init__(self) -> None:
        if self.total_cost < 0:
            raise ValueError("plan cost cannot be negative")

    @property
    def complete(self) -> bool:
        return not self.uncovered_artifact_ids


@dataclass(frozen=True, slots=True)
class ErasureGraph:
    nodes: Mapping[str, Artifact]
    edges: tuple[Edge, ...]

    def __post_init__(self) -> None:
        copied_nodes = dict(self.nodes)
        for node_id, node in copied_nodes.items():
            if node_id != node.id:
                raise ValueError(f"node key {node_id!r} does not match artifact id {node.id!r}")

        seen: set[Edge] = set()
        for edge in self.edges:
            if edge.source_id not in copied_nodes:
                raise ValueError(f"edge has unknown source {edge.source_id!r}")
            if edge.target_id not in copied_nodes:
                raise ValueError(f"edge has unknown target {edge.target_id!r}")
            if edge in seen:
                raise ValueError(f"duplicate edge {edge.source_id!r} -> {edge.target_id!r}")
            seen.add(edge)
            source = copied_nodes[edge.source_id]
            target = copied_nodes[edge.target_id]
            if source.subject_id != target.subject_id and not edge.cross_subject:
                raise ValueError("cross-subject edge must be explicitly marked")

        object.__setattr__(self, "nodes", MappingProxyType(copied_nodes))
