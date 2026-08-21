from dataclasses import replace

import pytest

from erasemap.audit import audit_subject
from erasemap.domain import (
    ArtifactState,
    ArtifactType,
    AuditResult,
    Edge,
    EdgeType,
    ErasureGraph,
    Evidence,
    EvidenceKind,
)
from erasemap.model_remediation import (
    ModelRemediationMethod,
    select_model_remediation,
)
from tests.factories import absence_evidence, artifact


def model_residual_case() -> tuple[ErasureGraph, AuditResult]:
    source = artifact(id="source", state=ArtifactState.ERASED)
    model = artifact(
        id="model",
        type=ArtifactType.MODEL_INFLUENCE,
        state=ArtifactState.ACTIVE,
        active_sink=True,
    )
    graph = ErasureGraph(
        {"source": source, "model": model},
        (Edge("source", "model", EdgeType.USED_TO_TRAIN),),
    )
    return graph, audit_subject(graph, {"source": absence_evidence(source)}, "subject-1", 100)


def test_lineage_selects_exact_when_it_fits_deadline() -> None:
    graph, audit = model_residual_case()
    decision = select_model_remediation(
        graph,
        audit,
        exact_retrain_seconds=2.0,
        maximum_update_seconds=3.0,
        approximate_protocol_available=True,
    )
    assert decision.method is ModelRemediationMethod.EXACT_RETRAIN
    assert decision.model_artifact_ids == ("model",)


def test_lineage_selects_approximate_only_with_frozen_protocol() -> None:
    graph, audit = model_residual_case()
    selected = select_model_remediation(
        graph,
        audit,
        exact_retrain_seconds=5.0,
        maximum_update_seconds=1.0,
        approximate_protocol_available=True,
    )
    blocked = select_model_remediation(
        graph,
        audit,
        exact_retrain_seconds=5.0,
        maximum_update_seconds=1.0,
        approximate_protocol_available=False,
    )
    assert selected.method is ModelRemediationMethod.INFLUENCE_SELECTIVE
    assert "primary endpoint equivalence to exact" in selected.required_evidence
    assert "registered multi-attack worst-case privacy result" in selected.required_evidence
    assert blocked.method is ModelRemediationMethod.BLOCKED


def test_no_model_residual_requires_no_action() -> None:
    graph, _audit = model_residual_case()
    erased_model = replace(graph.nodes["model"], state=ArtifactState.ERASED, active_sink=False)
    clean_graph = ErasureGraph({**graph.nodes, "model": erased_model}, graph.edges)
    clean_audit = audit_subject(
        clean_graph,
        {
            "source": absence_evidence(clean_graph.nodes["source"]),
            "model": Evidence(
                "model-proof",
                "model",
                EvidenceKind.MODEL_AUDIT,
                issued_epoch=90,
                metadata=(
                    ("pass", "true"),
                    ("protocol_id", "task-agnostic-v2.1"),
                    ("reference_id", "result-hash"),
                ),
            ),
        },
        "subject-1",
        100,
    )
    decision = select_model_remediation(
        clean_graph,
        clean_audit,
        exact_retrain_seconds=None,
        maximum_update_seconds=None,
        approximate_protocol_available=False,
    )
    assert decision.method is ModelRemediationMethod.NO_ACTION


def test_negative_runtime_is_rejected() -> None:
    graph, audit = model_residual_case()
    with pytest.raises(ValueError):
        select_model_remediation(
            graph,
            audit,
            exact_retrain_seconds=-1,
            maximum_update_seconds=1,
            approximate_protocol_available=True,
        )
