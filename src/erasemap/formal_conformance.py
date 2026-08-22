from __future__ import annotations

import hashlib
import itertools
import json
from typing import Any, cast

from erasemap.cdc import brute_force_cdc, exact_cdc
from erasemap.multiview_verifier import upper_bound_channel
from erasemap.pcug_domain import (
    CDCAction,
    CDCProtocol,
    EdgeKind,
    EdgeState,
    PCUGEdge,
    PCUGGraph,
    PCUGNode,
    PCUGVerdict,
    Transition,
    TransitionTarget,
)

SCHEMA = "erasemap-formal-conformance-v1"


def _case(
    costs: tuple[int, int, int], permitted: tuple[bool, bool, bool]
) -> tuple[PCUGGraph, CDCProtocol, tuple[CDCAction, ...]]:
    nodes = (
        PCUGNode("subject", "SUBJECT", "person-1"),
        PCUGNode("a", "COPY", "person-1"),
        PCUGNode("b", "COPY", "person-1"),
        PCUGNode("sink", "API", "shared", active_sink=True),
    )
    edges = tuple(
        PCUGEdge(
            source,
            target,
            EdgeKind.PROCESSING,
            EdgeState.ACTIVE,
            request_scoped=True,
            subject_id="person-1",
        )
        for source, target in (
            ("subject", "a"),
            ("subject", "b"),
            ("a", "sink"),
            ("b", "sink"),
        )
    )
    graph = PCUGGraph(
        nodes,
        edges,
        (upper_bound_channel("storage", value=0, upper_bound=0, threshold=0),),
    )
    protocol = CDCProtocol(
        "formal-conformance",
        "person-1",
        frozenset({"subject"}),
        frozenset({"sink"}),
        frozenset({"storage"}),
    )
    actions = (
        CDCAction(
            "close-a",
            costs[0],
            (Transition("a", EdgeState.CLOSED, "proof-a", TransitionTarget.NODE),),
            permitted=permitted[0],
        ),
        CDCAction(
            "close-b",
            costs[1],
            (Transition("b", EdgeState.CLOSED, "proof-b", TransitionTarget.NODE),),
            permitted=permitted[1],
        ),
        CDCAction(
            "close-both",
            costs[2],
            (
                Transition("a", EdgeState.CLOSED, "proof-both-a", TransitionTarget.NODE),
                Transition("b", EdgeState.CLOSED, "proof-both-b", TransitionTarget.NODE),
            ),
            permitted=permitted[2],
        ),
    )
    return graph, protocol, actions


def run_formal_conformance(*, cost_levels: int = 4) -> dict[str, Any]:
    if cost_levels <= 0:
        raise ValueError("cost_levels must be positive")
    records: list[dict[str, object]] = []
    ordering_runs = 0
    complete_catalogs = 0
    incomplete_catalogs = 0
    for costs in itertools.product(range(cost_levels), repeat=3):
        for permitted in itertools.product((False, True), repeat=3):
            typed_costs = cast(tuple[int, int, int], costs)
            typed_permitted = cast(tuple[bool, bool, bool], permitted)
            graph, protocol, actions = _case(typed_costs, typed_permitted)
            reference = brute_force_cdc(graph, protocol, actions)
            for ordering in itertools.permutations(actions):
                candidate = exact_cdc(graph, protocol, ordering)
                ordering_runs += 1
                if candidate != reference:
                    raise AssertionError(
                        f"exact/oracle mismatch for costs={costs}, permitted={permitted}"
                    )
            is_complete = reference.verdict is PCUGVerdict.COMPLETE
            complete_catalogs += int(is_complete)
            incomplete_catalogs += int(not is_complete)
            records.append(
                {
                    "action_ids": list(reference.action_ids),
                    "costs": list(costs),
                    "permitted": list(permitted),
                    "total_cost": reference.total_cost,
                    "verdict": reference.verdict.value,
                }
            )
    canonical_records = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    return {
        "schema": SCHEMA,
        "cost_levels": cost_levels,
        "catalogs": len(records),
        "action_orderings_per_catalog": 6,
        "ordering_runs": ordering_runs,
        "complete_catalogs": complete_catalogs,
        "incomplete_catalogs": incomplete_catalogs,
        "mismatches": 0,
        "records_sha256": hashlib.sha256(canonical_records).hexdigest(),
        "claim": "production exact_cdc equals exhaustive brute_force_cdc on every listed run",
    }
