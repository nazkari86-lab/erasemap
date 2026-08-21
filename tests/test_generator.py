import pytest

from erasemap.codec import graph_to_json
from erasemap.generator import FaultKind, generate_case


def test_generation_is_byte_deterministic() -> None:
    left = generate_case(seed=17, node_count=100, faults=(FaultKind.ORPHANED_TEMPLATE,))
    right = generate_case(seed=17, node_count=100, faults=(FaultKind.ORPHANED_TEMPLATE,))
    assert graph_to_json(left.graph) == graph_to_json(right.graph)
    assert left.truth == right.truth


def test_injected_fault_is_present_in_ground_truth() -> None:
    case = generate_case(seed=3, node_count=20, faults=(FaultKind.REPLAYED_RECEIPT,))
    assert case.truth.faults[0].kind is FaultKind.REPLAYED_RECEIPT
    assert case.truth.has_prohibited_residual


@pytest.mark.parametrize("node_count", [10, 100, 1_000, 10_000])
def test_generation_preserves_requested_size(node_count: int) -> None:
    case = generate_case(seed=5, node_count=node_count, faults=())
    assert len(case.graph.nodes) == node_count
    assert not case.truth.has_prohibited_residual


def test_generation_rejects_too_small_graph() -> None:
    with pytest.raises(ValueError, match="at least 10"):
        generate_case(seed=1, node_count=9, faults=())


def test_each_fault_kind_can_be_injected() -> None:
    for fault in FaultKind:
        case = generate_case(seed=11, node_count=30, faults=(fault,))
        assert case.truth.faults[0].kind is fault
