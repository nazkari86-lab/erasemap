from __future__ import annotations

import hashlib
import json

from erasemap.temporal import StabilizationControl
from erasemap.temporal_multipath import multipath_controls
from erasemap.temporal_robust import (
    TopologyUncertaintyEnvelope,
    exact_robust_stabilization_cut,
)
from erasemap.temporal_robust_lab import (
    brute_force_robust_oracle,
    scenario_from_mask,
)

TRE_COST_CATALOGS: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("registered", (3, 5, 60, 4, 7, 2)),
    ("all-zero", (0, 0, 0, 0, 0, 0)),
    ("all-seven", (7, 7, 7, 7, 7, 7)),
    ("shared-expensive", (3, 5, 101, 4, 100, 2)),
)


def _envelope(available_mask: int) -> TopologyUncertaintyEnvelope:
    scenario_masks = tuple(
        mask for mask in range(8) if mask & ~available_mask == 0
    )
    return TopologyUncertaintyEnvelope(
        f"tre-conformance-{available_mask}",
        "nominal-backup",
        available_mask.bit_count(),
        tuple(scenario_from_mask(mask) for mask in scenario_masks),
    )


def _controls(
    envelope: TopologyUncertaintyEnvelope,
    costs: tuple[int, ...],
    permission_mask: int,
    *,
    reverse: bool,
) -> tuple[StabilizationControl, ...]:
    transition_ids = frozenset(
        transition.id
        for scenario in envelope.scenarios
        for transition in scenario.transitions
    )
    selected = tuple(
        StabilizationControl(
            item.id,
            costs[index],
            item.guarded_transition_ids & transition_ids,
            permitted=bool(permission_mask & (1 << index)),
        )
        for index, item in enumerate(multipath_controls())
        if item.guarded_transition_ids & transition_ids
    )
    return tuple(reversed(selected)) if reverse else selected


def run_tre_conformance() -> dict[str, object]:
    records = hashlib.sha256()
    configurations = 0
    optimal = 0
    infeasible = 0
    mismatches = 0
    for available_mask in range(8):
        envelope = _envelope(available_mask)
        for permission_mask in range(1 << len(multipath_controls())):
            for catalog_id, costs in TRE_COST_CATALOGS:
                for reverse in (False, True):
                    controls = _controls(
                        envelope,
                        costs,
                        permission_mask,
                        reverse=reverse,
                    )
                    plan = exact_robust_stabilization_cut(envelope, controls)
                    oracle_ids, oracle_cost, oracle_status = brute_force_robust_oracle(
                        envelope, controls
                    )
                    actual = (plan.control_ids, plan.total_cost, plan.status.value)
                    expected = (oracle_ids, oracle_cost, oracle_status)
                    mismatches += actual != expected
                    optimal += plan.complete
                    infeasible += plan.status.value == "INFEASIBLE"
                    record = {
                        "available_mask": available_mask,
                        "catalog": catalog_id,
                        "costs": costs,
                        "permission_mask": permission_mask,
                        "reverse_input": reverse,
                        "scenario_count": len(envelope.scenarios),
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
        "schema": "erasemap-tre-conformance-v1",
        "claim": (
            "production exact_robust_stabilization_cut equals a separately "
            "implemented exhaustive subset oracle on every listed finite-domain "
            "topology-envelope configuration"
        ),
        "uncertainty_envelopes": 8,
        "permission_masks": 1 << len(multipath_controls()),
        "cost_catalogs": len(TRE_COST_CATALOGS),
        "input_orderings": 2,
        "configurations": configurations,
        "optimal_configurations": optimal,
        "infeasible_configurations": infeasible,
        "mismatches": mismatches,
        "records_sha256": records.hexdigest(),
    }
