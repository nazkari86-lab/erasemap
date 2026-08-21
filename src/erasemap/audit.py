from __future__ import annotations

from collections import deque
from collections.abc import Mapping

from erasemap.domain import (
    ArtifactState,
    ArtifactType,
    AuditResult,
    AuditStatus,
    ErasureGraph,
    Evidence,
    EvidenceCheck,
    ResidualPath,
)
from erasemap.evidence import validate_evidence


def _subject_roots(graph: ErasureGraph, subject_id: str) -> tuple[str, ...]:
    subject_nodes = {
        node.id for node in graph.nodes.values() if node.subject_id == subject_id
    }
    explicit = sorted(
        node.id
        for node in graph.nodes.values()
        if node.subject_id == subject_id and node.type is ArtifactType.SOURCE_RECORD
    )
    if explicit:
        return tuple(explicit)
    incoming = {
        edge.target_id
        for edge in graph.edges
        if edge.source_id in subject_nodes and edge.target_id in subject_nodes
    }
    return tuple(sorted(subject_nodes - incoming))


def _shortest_paths(
    graph: ErasureGraph,
    roots: tuple[str, ...],
    subject_id: str,
) -> dict[str, tuple[str, ...]]:
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in graph.nodes}
    for edge in graph.edges:
        if (
            graph.nodes[edge.source_id].subject_id == subject_id
            and graph.nodes[edge.target_id].subject_id == subject_id
        ):
            adjacency[edge.source_id].append(edge.target_id)
    for targets in adjacency.values():
        targets.sort()

    paths: dict[str, tuple[str, ...]] = {}
    queue: deque[str] = deque()
    for root in roots:
        if root not in paths:
            paths[root] = (root,)
            queue.append(root)
    while queue:
        current = queue.popleft()
        for target in adjacency[current]:
            candidate = (*paths[current], target)
            previous = paths.get(target)
            if previous is None or (len(candidate), candidate) < (len(previous), previous):
                paths[target] = candidate
                queue.append(target)
    return paths


def audit_subject(
    graph: ErasureGraph,
    evidence_by_artifact: Mapping[str, Evidence],
    subject_id: str,
    now_epoch: int,
) -> AuditResult:
    if now_epoch < 0:
        raise ValueError("now_epoch cannot be negative")
    if not subject_id:
        raise ValueError("subject_id is required")

    roots = _subject_roots(graph, subject_id)
    paths = _shortest_paths(graph, roots, subject_id)
    reachable = frozenset(
        node_id for node_id in paths if graph.nodes[node_id].subject_id == subject_id
    )
    if not reachable:
        return AuditResult(
            status=AuditStatus.UNVERIFIED,
            residual_paths=(),
            shortest_path=None,
            evidence_checks=(),
            reachable_artifact_ids=frozenset(),
        )

    residuals: list[ResidualPath] = []
    checks: list[tuple[str, EvidenceCheck]] = []
    waiting = False
    for node_id in sorted(reachable):
        node = graph.nodes[node_id]
        if node.state is ArtifactState.ACTIVE:
            reason = (
                "active sink remains reachable"
                if node.active_sink
                else "active artifact remains"
            )
            residuals.append(ResidualPath(paths[node_id], reason))
            checks.append(
                (
                    node_id,
                    EvidenceCheck(False, "artifact remains active", ArtifactState.ACTIVE),
                )
            )
            continue

        evidence = evidence_by_artifact.get(node_id)
        if evidence is None:
            checks.append(
                (
                    node_id,
                    EvidenceCheck(False, "missing evidence", ArtifactState.UNVERIFIED),
                )
            )
            continue
        check = validate_evidence(node, evidence, now_epoch)
        checks.append((node_id, check))
        if check.effective_state is ArtifactState.WAITING_EXPIRY:
            waiting = True

    ordered_residuals = tuple(
        sorted(residuals, key=lambda item: (len(item.node_ids), item.node_ids, item.reason))
    )
    invalid_evidence = any(not check.valid for _, check in checks)
    if ordered_residuals:
        status = AuditStatus.INCOMPLETE
    elif invalid_evidence or waiting:
        status = AuditStatus.UNVERIFIED
    else:
        status = AuditStatus.COMPLETE
    return AuditResult(
        status=status,
        residual_paths=ordered_residuals,
        shortest_path=ordered_residuals[0] if ordered_residuals else None,
        evidence_checks=tuple(checks),
        reachable_artifact_ids=reachable,
    )
