from dataclasses import replace

from hypothesis import given
from hypothesis import strategies as st

from erasemap.audit import audit_subject
from erasemap.domain import ArtifactState, AuditStatus, ErasureGraph
from tests.factories import absence_evidence, simple_graph


@given(st.booleans())
def test_active_sink_prevents_complete(active_sink: bool) -> None:
    graph = simple_graph()
    index = replace(
        graph.nodes["index"],
        state=ArtifactState.ACTIVE if active_sink else ArtifactState.ERASED,
        active_sink=active_sink,
    )
    source = replace(graph.nodes["source"], state=ArtifactState.ERASED)
    template = replace(graph.nodes["template"], state=ArtifactState.ERASED)
    updated = ErasureGraph(
        {"source": source, "template": template, "index": index},
        graph.edges,
    )
    evidence = {
        node.id: absence_evidence(node)
        for node in updated.nodes.values()
        if node.state is ArtifactState.ERASED
    }
    status = audit_subject(updated, evidence, "subject-1", 100).status
    if active_sink:
        assert status is AuditStatus.INCOMPLETE
    else:
        assert status is AuditStatus.COMPLETE
