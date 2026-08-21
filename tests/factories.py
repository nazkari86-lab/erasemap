from erasemap.domain import (
    Artifact,
    ArtifactState,
    ArtifactType,
    Edge,
    EdgeType,
    ErasureGraph,
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
