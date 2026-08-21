from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from erasemap.domain import ArtifactState, ArtifactType
from erasemap.evidence import validate_evidence
from erasemap.generator import GeneratedCase


@dataclass(frozen=True, slots=True)
class MethodDecision:
    declared_complete: bool
    detected_artifact_ids: frozenset[str]


class AuditMethod(Protocol):
    name: str

    def assess(self, case: GeneratedCase, *, now_epoch: int) -> MethodDecision: ...


@dataclass(frozen=True, slots=True)
class ReceiptOnly:
    """Naive comparator that equates a signed receipt with successful erasure."""

    name: str = "receipt-only"

    def assess(self, case: GeneratedCase, *, now_epoch: int) -> MethodDecision:
        del now_epoch
        trusted = any(
            node.type is ArtifactType.AUDIT_RECEIPT
            and (evidence := case.evidence.get(node.id)) is not None
            and evidence.valid_signature
            for node in case.graph.nodes.values()
        )
        return MethodDecision(trusted, frozenset())


@dataclass(frozen=True, slots=True)
class FlatChecklist:
    """Comparator limited to a fixed, explicitly enumerated store checklist."""

    checked_types: frozenset[ArtifactType]
    name: str = "flat-checklist"

    def assess(self, case: GeneratedCase, *, now_epoch: int) -> MethodDecision:
        detected: set[str] = set()
        for node in case.graph.nodes.values():
            if node.type not in self.checked_types:
                continue
            evidence = case.evidence.get(node.id)
            if node.state is ArtifactState.ACTIVE or evidence is None:
                detected.add(node.id)
            elif not validate_evidence(node, evidence, now_epoch).valid:
                detected.add(node.id)
        return MethodDecision(not detected, frozenset(detected))


@dataclass(frozen=True, slots=True)
class UntypedTraversal:
    """Graph comparator that treats all non-empty evidence as interchangeable."""

    name: str = "untyped-traversal"

    def assess(self, case: GeneratedCase, *, now_epoch: int) -> MethodDecision:
        detected: set[str] = set()
        for node in case.graph.nodes.values():
            evidence = case.evidence.get(node.id)
            expired = (
                evidence is not None
                and evidence.expires_epoch is not None
                and evidence.expires_epoch <= now_epoch
            )
            generic_claim = evidence is not None and (
                evidence.observed_absent
                or evidence.valid_signature
                or bool(evidence.metadata)
            )
            if node.state is ArtifactState.ACTIVE or expired or not generic_claim:
                detected.add(node.id)
        return MethodDecision(not detected, frozenset(detected))
