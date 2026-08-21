from dataclasses import replace

from erasemap.domain import (
    Artifact,
    ArtifactState,
    ArtifactType,
    Edge,
    EdgeType,
    ErasureGraph,
    Evidence,
    EvidenceKind,
)


def artifact(
    *,
    id: str = "artifact",
    subject_id: str = "subject-1",
    type: ArtifactType = ArtifactType.SOURCE_RECORD,
    state: ArtifactState = ArtifactState.ACTIVE,
    active_sink: bool = False,
    commitment: str = "sha256:test",
    evidence_id: str | None = None,
) -> Artifact:
    return Artifact(
        id=id,
        subject_id=subject_id,
        type=type,
        state=state,
        active_sink=active_sink,
        purpose="test",
        commitment=commitment,
        evidence_id=evidence_id,
    )


def simple_graph() -> ErasureGraph:
    nodes = {
        "source": artifact(id="source"),
        "template": artifact(id="template", type=ArtifactType.BIOMETRIC_TEMPLATE),
        "index": artifact(
            id="index",
            type=ArtifactType.SEARCH_INDEX_ENTRY,
            active_sink=True,
        ),
    }
    edges = (
        Edge("source", "template", EdgeType.DERIVED_INTO),
        Edge("template", "index", EdgeType.INDEXED_AS),
    )
    return ErasureGraph(nodes=nodes, edges=edges)


def absence_evidence(node: Artifact) -> Evidence:
    return Evidence(
        id=f"{node.id}-proof",
        artifact_id=node.id,
        kind=EvidenceKind.ABSENCE_CHECK,
        commitment=node.commitment,
        observed_absent=True,
        issued_epoch=90,
        expires_epoch=200,
    )


def graph_with_orphaned_index() -> tuple[ErasureGraph, dict[str, Evidence]]:
    graph = simple_graph()
    erased_source = replace(graph.nodes["source"], state=ArtifactState.ERASED)
    erased_template = replace(graph.nodes["template"], state=ArtifactState.ERASED)
    updated = ErasureGraph(
        nodes={**graph.nodes, "source": erased_source, "template": erased_template},
        edges=graph.edges,
    )
    evidence = {
        erased_source.id: absence_evidence(erased_source),
        erased_template.id: absence_evidence(erased_template),
    }
    return updated, evidence
