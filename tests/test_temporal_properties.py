from itertools import combinations

from hypothesis import given
from hypothesis import strategies as st

from erasemap.temporal import (
    RSEVerdict,
    StabilizationControl,
    evaluate_rse,
    exact_stabilization_cut,
)
from erasemap.temporal_multipath import (
    ALL_CARRIERS,
    multipath_controls,
    multipath_coverage,
    multipath_protocol,
    multipath_transitions,
)


def _oracle(
    controls: tuple[StabilizationControl, ...],
) -> tuple[int, int, tuple[str, ...]] | None:
    permitted = tuple(item for item in controls if item.permitted)
    best = None
    for size in range(len(permitted) + 1):
        for chosen in combinations(permitted, size):
            guarded = frozenset().union(*(item.guarded_transition_ids for item in chosen))
            report = evaluate_rse(
                ALL_CARRIERS,
                multipath_transitions(),
                multipath_coverage(),
                multipath_protocol(),
                guarded_transition_ids=guarded,
            )
            if report.verdict is not RSEVerdict.RSE_VERIFIED:
                continue
            ids = tuple(sorted(item.id for item in chosen))
            key = (sum(item.cost for item in chosen), len(ids), ids)
            if best is None or key < best:
                best = key
    return best


@given(
    costs=st.lists(st.integers(min_value=0, max_value=25), min_size=6, max_size=6),
    permissions=st.lists(st.booleans(), min_size=6, max_size=6),
)
def test_branch_and_bound_msc_matches_exhaustive_oracle(
    costs: list[int], permissions: list[bool]
) -> None:
    controls = tuple(
        StabilizationControl(
            base.id,
            cost,
            base.guarded_transition_ids,
            permitted=permitted,
        )
        for base, cost, permitted in zip(
            multipath_controls(), costs, permissions, strict=True
        )
    )
    plan = exact_stabilization_cut(
        ALL_CARRIERS,
        multipath_transitions(),
        multipath_coverage(),
        multipath_protocol(),
        controls,
    )
    oracle = _oracle(controls)

    if oracle is None:
        assert not plan.complete
    else:
        assert plan.complete
        assert (plan.total_cost, len(plan.control_ids), plan.control_ids) == oracle
