from __future__ import annotations

import hashlib
import itertools
import json

from erasemap.temporal import (
    RSEVerdict,
    StabilizationControl,
    StabilizationStatus,
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

COST_CATALOGS: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("registered", (3, 5, 60, 4, 7, 2)),
    ("all-zero", (0, 0, 0, 0, 0, 0)),
    ("all-one", (1, 1, 1, 1, 1, 1)),
    ("all-seven", (7, 7, 7, 7, 7, 7)),
    ("ascending", (0, 1, 2, 3, 4, 5)),
    ("descending", (5, 4, 3, 2, 1, 0)),
    ("shared-expensive", (3, 5, 101, 4, 100, 2)),
    ("path-expensive", (9, 8, 50, 7, 6, 5)),
)


def _carrier_subsets() -> tuple[frozenset[str], ...]:
    carriers = tuple(sorted(ALL_CARRIERS))
    return tuple(
        frozenset(carrier for index, carrier in enumerate(carriers) if mask & (1 << index))
        for mask in range(1 << len(carriers))
    )


def _controls(
    costs: tuple[int, ...], permission_mask: int, *, reverse: bool
) -> tuple[StabilizationControl, ...]:
    base = multipath_controls()
    controls = tuple(
        StabilizationControl(
            item.id,
            costs[index],
            item.guarded_transition_ids,
            permitted=bool(permission_mask & (1 << index)),
        )
        for index, item in enumerate(base)
    )
    return tuple(reversed(controls)) if reverse else controls


def _oracle(
    initial: frozenset[str], controls: tuple[StabilizationControl, ...]
) -> tuple[tuple[str, ...], int, str]:
    permitted = tuple(item for item in controls if item.permitted)
    best: tuple[int, int, tuple[str, ...]] | None = None
    for size in range(len(permitted) + 1):
        for chosen in itertools.combinations(permitted, size):
            guarded = frozenset().union(
                *(item.guarded_transition_ids for item in chosen)
            )
            report = evaluate_rse(
                initial,
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
    if best is None:
        return (), 0, StabilizationStatus.INFEASIBLE.value
    return best[2], best[0], StabilizationStatus.OPTIMAL.value


def run_rse_conformance() -> dict[str, object]:
    records = hashlib.sha256()
    mismatches = 0
    complete = 0
    infeasible = 0
    configurations = 0
    for initial in _carrier_subsets():
        for permission_mask in range(1 << len(multipath_controls())):
            for catalog_id, costs in COST_CATALOGS:
                for reverse in (False, True):
                    controls = _controls(costs, permission_mask, reverse=reverse)
                    plan = exact_stabilization_cut(
                        initial,
                        multipath_transitions(),
                        multipath_coverage(),
                        multipath_protocol(),
                        controls,
                    )
                    oracle_ids, oracle_cost, oracle_status = _oracle(initial, controls)
                    actual = (plan.control_ids, plan.total_cost, plan.status.value)
                    expected = (oracle_ids, oracle_cost, oracle_status)
                    mismatches += actual != expected
                    complete += plan.complete
                    infeasible += plan.status is StabilizationStatus.INFEASIBLE
                    record = {
                        "catalog": catalog_id,
                        "costs": costs,
                        "initial": sorted(initial),
                        "permission_mask": permission_mask,
                        "reverse_input": reverse,
                        "selected": plan.control_ids,
                        "selected_cost": plan.total_cost,
                        "status": plan.status.value,
                    }
                    records.update(
                        (
                            json.dumps(record, sort_keys=True, separators=(",", ":"))
                            + "\n"
                        ).encode()
                    )
                    configurations += 1
    return {
        "schema": "erasemap-rse-msc-conformance-v1",
        "claim": (
            "production exact_stabilization_cut equals a separately implemented "
            "exhaustive subset oracle on every listed finite-domain configuration"
        ),
        "carrier_subsets": len(_carrier_subsets()),
        "permission_masks": 1 << len(multipath_controls()),
        "cost_catalogs": len(COST_CATALOGS),
        "input_orderings": 2,
        "configurations": configurations,
        "complete_configurations": complete,
        "infeasible_configurations": infeasible,
        "mismatches": mismatches,
        "records_sha256": records.hexdigest(),
    }
