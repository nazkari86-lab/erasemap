from itertools import combinations

from hypothesis import given
from hypothesis import strategies as st

from erasemap.domain import ArtifactState, RemediationAction
from erasemap.planning import exact_plan


@given(
    st.lists(
        st.tuples(
            st.sets(st.integers(min_value=0, max_value=3), min_size=1),
            st.integers(min_value=0, max_value=10),
        ),
        min_size=1,
        max_size=8,
    )
)
def test_exact_plan_matches_exhaustive_search(raw_actions: list[tuple[set[int], int]]) -> None:
    required = frozenset(str(item) for item in range(4))
    actions = tuple(
        RemediationAction(
            f"a-{index}",
            frozenset(str(item) for item in covered),
            cost,
            ArtifactState.ERASED,
        )
        for index, (covered, cost) in enumerate(raw_actions)
    )
    complete_costs: list[int] = []
    for count in range(len(actions) + 1):
        for chosen in combinations(actions, count):
            coverage = frozenset().union(*(action.covers_artifact_ids for action in chosen))
            if required <= coverage:
                complete_costs.append(sum(action.cost for action in chosen))
    plan = exact_plan(required, actions)
    if complete_costs:
        assert plan.complete
        assert plan.total_cost == min(complete_costs)
    else:
        assert not plan.complete
