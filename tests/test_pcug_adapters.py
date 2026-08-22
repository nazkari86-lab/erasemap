from dataclasses import replace

import pytest

from erasemap.cdc import exact_cdc
from erasemap.pcug_adapters import adapter_names, build_adapter_case
from erasemap.pcug_domain import PCUGGraph


def _strip_display_metadata(graph: PCUGGraph) -> PCUGGraph:
    return PCUGGraph(
        nodes=tuple(replace(node, display_name="") for node in graph.nodes),
        edges=graph.edges,
        channel_results=graph.channel_results,
    )


@pytest.mark.parametrize("adapter", adapter_names())
def test_adapter_label_does_not_change_core_verdict(adapter: str) -> None:
    case = build_adapter_case(adapter, seed=4409)
    reference = build_adapter_case("faceid_style", seed=4409)
    assert _strip_display_metadata(case.graph) == _strip_display_metadata(reference.graph)
    candidate = exact_cdc(case.graph, case.protocol, case.actions)
    expected = exact_cdc(reference.graph, reference.protocol, reference.actions)
    assert candidate.verdict == expected.verdict
    assert candidate.total_cost == expected.total_cost


def test_every_adapter_is_explicitly_simulated() -> None:
    for name in adapter_names():
        case = build_adapter_case(name, seed=1)
        assert case.evidence_scope == "SYNTHETIC_SIMULATOR"
        assert not case.authorized_integration
        assert "not evidence" in case.disclaimer.lower()


def test_unknown_adapter_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown adapter"):
        build_adapter_case("production_egov", seed=1)

