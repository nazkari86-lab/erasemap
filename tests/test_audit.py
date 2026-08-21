from dataclasses import replace

import pytest

from erasemap.audit import audit_subject
from erasemap.domain import (
    ArtifactState,
    ArtifactType,
    AuditStatus,
    ErasureGraph,
    Evidence,
    EvidenceKind,
)
from tests.factories import (
    absence_evidence,
    artifact,
    graph_with_orphaned_index,
    simple_graph,
)


def test_audit_returns_shortest_residual_counterexample() -> None:
    graph, evidence = graph_with_orphaned_index()
    result = audit_subject(graph, evidence, subject_id="subject-1", now_epoch=100)
    assert result.status is AuditStatus.INCOMPLETE
    assert result.shortest_path is not None
    assert result.shortest_path.node_ids == ("source", "template", "index")
    assert result.shortest_path.reason == "active sink remains reachable"


def test_missing_evidence_is_unverified_not_complete() -> None:
    graph = simple_graph()
    nodes = {
        key: replace(node, state=ArtifactState.ERASED, active_sink=False)
        for key, node in graph.nodes.items()
    }
    result = audit_subject(ErasureGraph(nodes, graph.edges), {}, "subject-1", 100)
    assert result.status is AuditStatus.UNVERIFIED
    assert result.shortest_path is None


def test_fully_evidenced_erasure_is_complete() -> None:
    graph = simple_graph()
    nodes = {
        key: replace(node, state=ArtifactState.ERASED, active_sink=False)
        for key, node in graph.nodes.items()
    }
    erased = ErasureGraph(nodes, graph.edges)
    evidence = {node.id: absence_evidence(node) for node in erased.nodes.values()}
    result = audit_subject(erased, evidence, "subject-1", 100)
    assert result.status is AuditStatus.COMPLETE


def test_unknown_subject_has_no_registered_artifacts() -> None:
    result = audit_subject(simple_graph(), {}, "missing-subject", 100)
    assert result.status is AuditStatus.UNVERIFIED
    assert result.reachable_artifact_ids == frozenset()


def test_waiting_backup_keeps_overall_status_unverified() -> None:
    backup = artifact(
        id="backup",
        type=ArtifactType.BACKUP_COPY,
        state=ArtifactState.WAITING_EXPIRY,
    )
    graph = ErasureGraph({"backup": backup}, ())
    evidence = {
        "backup": Evidence(
            "backup-proof",
            "backup",
            EvidenceKind.EXPIRY_SCHEDULE,
            issued_epoch=50,
            expires_epoch=200,
        )
    }
    result = audit_subject(graph, evidence, "subject-1", 100)
    assert result.status is AuditStatus.UNVERIFIED


@pytest.mark.parametrize(("subject_id", "now_epoch"), [("", 0), ("subject-1", -1)])
def test_invalid_audit_arguments_are_rejected(subject_id: str, now_epoch: int) -> None:
    with pytest.raises(ValueError):
        audit_subject(simple_graph(), {}, subject_id, now_epoch)
