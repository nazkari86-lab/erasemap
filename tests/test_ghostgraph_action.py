from __future__ import annotations

from erasemap.ghostgraph import (
    DiscoveryExperiment,
    GraphEdge,
    GraphHypothesis,
    GraphNode,
)
from erasemap.ghostgraph_action import (
    ActionSignature,
    action_signature,
    assess_action_identifiability,
    build_global_policy,
    run_global_policy,
)
from erasemap.ghostgraph_action_oracle import oracle_global_policy_value

NODES = tuple(GraphNode(item) for item in ("backup", "cache", "database", "vector"))


def graph(graph_id: str, edges: tuple[tuple[str, str, str, str], ...]) -> GraphHypothesis:
    return GraphHypothesis(
        graph_id=graph_id,
        nodes=NODES,
        edges=tuple(GraphEdge(*item) for item in sorted(edges)),
        initial_node_ids=("backup",),
        residual_node_ids=("vector",),
    )


def probe(experiment_id: str, operations: tuple[str, ...], cost: int = 1) -> DiscoveryExperiment:
    return DiscoveryExperiment(
        experiment_id,
        tuple(sorted(operations)),
        ("cache", "database", "vector"),
        3,
        cost,
    )


def test_action_signature_finds_all_minimum_operation_cuts() -> None:
    item = graph(
        "fork",
        (
            ("a1", "backup", "cache", "restore"),
            ("a2", "cache", "vector", "index"),
            ("b1", "backup", "database", "restore"),
            ("b2", "database", "vector", "sync"),
        ),
    )

    assert action_signature(item) == ActionSignature(
        True,
        1,
        (("restore",),),
    )


def test_safe_graph_and_uncontrollable_initial_residual_are_distinct() -> None:
    safe = graph("safe", ())
    trapped = GraphHypothesis(
        graph_id="trapped",
        nodes=NODES,
        edges=(),
        initial_node_ids=("vector",),
        residual_node_ids=("vector",),
    )

    assert action_signature(safe) == ActionSignature(True, 0, ((),))
    assert action_signature(trapped) == ActionSignature(False, None, ())


def test_identifiability_returns_constructive_impossibility_witness() -> None:
    left = graph("left", (("a", "backup", "vector", "a"),))
    right = graph("right", (("b", "backup", "vector", "b"),))
    blind = probe("blind", (), 1)

    report = assess_action_identifiability((left, right), (blind,))

    assert not report.identifiable
    assert report.information_lower_bound_probes is None
    assert len(report.witnesses) == 1
    assert report.witnesses[0].shared_trace_vector == ((False,) * 9,)


def test_global_policy_optimizes_action_not_exact_graph_identity() -> None:
    safe = graph("safe", ())
    a1 = graph("a1", (("a", "backup", "vector", "a"),))
    a2 = graph(
        "a2",
        (
            ("a", "backup", "vector", "a"),
            ("noise", "backup", "cache", "noise"),
        ),
    )
    b = graph("b", (("b", "backup", "vector", "b"),))
    experiments = (
        probe("q-a", ("a",)),
        probe("q-b", ("b",)),
        probe("q-noise", ("noise",), 5),
    )

    certificate = build_global_policy((safe, a1, a2, b), experiments)
    oracle = oracle_global_policy_value((safe, a1, a2, b), experiments)

    assert certificate.identifiable
    assert oracle is not None
    assert (
        certificate.root_worst_case_cost,
        certificate.root_worst_case_probes,
    ) == oracle[:2]
    result, executed, _ = run_global_policy(certificate, (safe, a1, a2, b), experiments, a2)
    assert result == action_signature(a2)
    assert "q-noise" not in executed


def test_global_policy_fails_closed_when_different_actions_are_indistinguishable() -> None:
    left = graph("left", (("a", "backup", "vector", "a"),))
    right = graph("right", (("b", "backup", "vector", "b"),))

    certificate = build_global_policy((left, right), (probe("blind", ()),))

    assert not certificate.identifiable
    assert certificate.root_worst_case_cost is None
    assert certificate.impossibility_witnesses
