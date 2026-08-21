import pytest

from erasemap.domain import Artifact, ArtifactState, ArtifactType, Edge, EdgeType, ErasureGraph


def test_graph_rejects_edge_with_unknown_target() -> None:
    source = Artifact("person", "subject-1", ArtifactType.SOURCE_RECORD, ArtifactState.ACTIVE)
    with pytest.raises(ValueError, match="unknown target"):
        ErasureGraph(
            nodes={"person": source},
            edges=(Edge("person", "missing", EdgeType.COPIED_TO),),
        )


def test_erased_artifact_cannot_be_active_sink() -> None:
    with pytest.raises(ValueError, match="active sink"):
        Artifact(
            "copy",
            "subject-1",
            ArtifactType.SOURCE_RECORD,
            ArtifactState.ERASED,
            active_sink=True,
        )


def test_graph_rejects_duplicate_edges() -> None:
    nodes = {
        "a": Artifact("a", "subject-1", ArtifactType.SOURCE_RECORD, ArtifactState.ACTIVE),
        "b": Artifact("b", "subject-1", ArtifactType.CACHE_ENTRY, ArtifactState.ACTIVE),
    }
    edge = Edge("a", "b", EdgeType.COPIED_TO)
    with pytest.raises(ValueError, match="duplicate edge"):
        ErasureGraph(nodes=nodes, edges=(edge, edge))


def test_graph_nodes_are_immutable() -> None:
    node = Artifact("a", "subject-1", ArtifactType.SOURCE_RECORD, ArtifactState.ACTIVE)
    graph = ErasureGraph(nodes={"a": node}, edges=())
    with pytest.raises(TypeError):
        graph.nodes["b"] = node  # type: ignore[index]
