from __future__ import annotations

import itertools
from dataclasses import dataclass
from enum import StrEnum

from erasemap.erasure_tomography import (
    ProbeDesign,
    Support,
    TomographyCertificate,
    certify_design,
)


class DesignStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    INFEASIBLE = "INFEASIBLE"


@dataclass(frozen=True, slots=True)
class CertifiedProbeDesign:
    probe_design: ProbeDesign
    certificate: TomographyCertificate
    total_cost: int


@dataclass(frozen=True, slots=True)
class ConstructionResult:
    status: DesignStatus
    design: CertifiedProbeDesign | None
    indistinguishable_support_pairs: tuple[tuple[Support, Support], ...]


def _canonical_rows(
    mechanism_count: int,
    feasible_rows: tuple[tuple[bool, ...], ...],
    row_costs: tuple[int, ...] | None,
) -> tuple[tuple[tuple[bool, ...], int], ...]:
    if not feasible_rows:
        raise ValueError("at least one feasible row is required")
    if row_costs is not None and len(row_costs) != len(feasible_rows):
        raise ValueError("row cost count must match feasible rows")
    costs = row_costs or (1,) * len(feasible_rows)
    selected: dict[tuple[bool, ...], int] = {}
    for row, cost in zip(feasible_rows, costs, strict=True):
        if len(row) != mechanism_count:
            raise ValueError("feasible row width must match mechanism catalogue")
        if any(type(value) is not bool for value in row):
            raise ValueError("feasible row values must be Boolean")
        if not any(row):
            raise ValueError("all-zero feasible rows are not permitted")
        if cost < 0:
            raise ValueError("row cost cannot be negative")
        selected[row] = min(cost, selected.get(row, cost))
    return tuple(sorted(selected.items()))


def construct_minimum_design(
    mechanism_ids: tuple[str, ...],
    feasible_rows: tuple[tuple[bool, ...], ...],
    max_failures: int,
    error_budget: int,
    *,
    row_costs: tuple[int, ...] | None = None,
    max_exact_rows: int = 24,
) -> ConstructionResult:
    rows_with_costs = _canonical_rows(
        len(mechanism_ids), feasible_rows, row_costs
    )
    if len(rows_with_costs) > max_exact_rows:
        raise ValueError("exact feasible-row limit exceeded")

    best: tuple[
        tuple[int, tuple[tuple[bool, ...], ...]], CertifiedProbeDesign
    ] | None = None
    for row_count in range(1, len(rows_with_costs) + 1):
        for chosen in itertools.combinations(rows_with_costs, row_count):
            rows = tuple(item[0] for item in chosen)
            probe_design = ProbeDesign(
                mechanism_ids,
                rows,
                max_failures,
                error_budget,
            )
            certificate = certify_design(probe_design)
            if not certificate.uniquely_decodable:
                continue
            total_cost = sum(item[1] for item in chosen)
            key = (total_cost, rows)
            candidate = CertifiedProbeDesign(
                probe_design,
                certificate,
                total_cost,
            )
            if best is None or key < best[0]:
                best = (key, candidate)
        if best is not None:
            return ConstructionResult(DesignStatus.OPTIMAL, best[1], ())

    full_design = ProbeDesign(
        mechanism_ids,
        tuple(item[0] for item in rows_with_costs),
        max_failures,
        error_budget,
    )
    certificate = certify_design(full_design)
    return ConstructionResult(
        DesignStatus.INFEASIBLE,
        None,
        certificate.indistinguishable_support_pairs,
    )
