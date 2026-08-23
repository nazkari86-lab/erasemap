from __future__ import annotations

import hashlib
import itertools
import json

from erasemap.erasure_tomography import (
    ProbeDesign,
    TomographyEvidence,
    TomographyVerdict,
    decode,
)
from erasemap.erasure_tomography_oracle import oracle_decode


def _candidate_matrices(width: int) -> tuple[tuple[tuple[bool, ...], ...], ...]:
    identity = tuple(
        tuple(column == row for column in range(width)) for row in range(width)
    )
    all_ones = (tuple(True for _ in range(width)),)
    bit_count = max(1, width.bit_length())
    binary = tuple(
        tuple(bool((column + 1) & (1 << bit)) for column in range(width))
        for bit in range(bit_count)
    )
    paired = tuple(
        tuple(column in {row, (row + 1) % width} for column in range(width))
        for row in range(width)
    )
    return tuple(sorted({identity, all_ones, binary, paired}))


def _designs() -> tuple[ProbeDesign, ...]:
    designs = []
    for width in range(1, 6):
        mechanism_ids = tuple(f"m{index}" for index in range(width))
        for rows in _candidate_matrices(width):
            for max_failures in range(min(2, width) + 1):
                for error_budget in range(2):
                    designs.append(
                        ProbeDesign(
                            mechanism_ids,
                            rows,
                            max_failures,
                            error_budget,
                        )
                    )
    return tuple(designs)


def run_erasure_tomography_conformance() -> dict[str, object]:
    digest = hashlib.sha256()
    counts = {verdict: 0 for verdict in TomographyVerdict}
    mismatches = 0
    configurations = 0
    evidence_catalogue = (
        TomographyEvidence.complete(),
        TomographyEvidence(True, False, True, True, True),
    )
    for design in _designs():
        row_orders = (design.rows, tuple(reversed(design.rows)))
        for order_index, rows in enumerate(row_orders):
            ordered = ProbeDesign(
                design.mechanism_ids,
                rows,
                design.max_failures,
                design.error_budget,
            )
            for evidence_index, evidence in enumerate(evidence_catalogue):
                for observations in itertools.product(
                    (False, True), repeat=len(ordered.rows)
                ):
                    actual = decode(ordered, observations, evidence)
                    expected = oracle_decode(ordered, observations, evidence)
                    actual_tuple = (
                        actual.verdict,
                        actual.support,
                        actual.admissible_supports,
                        actual.distance,
                    )
                    expected_tuple = (
                        expected.verdict,
                        expected.support,
                        expected.admissible_supports,
                        expected.distance,
                    )
                    mismatches += actual_tuple != expected_tuple
                    counts[actual.verdict] += 1
                    record = {
                        "mechanism_ids": ordered.mechanism_ids,
                        "rows": ordered.rows,
                        "max_failures": ordered.max_failures,
                        "error_budget": ordered.error_budget,
                        "row_order": order_index,
                        "evidence": evidence_index,
                        "observations": observations,
                        "verdict": actual.verdict.value,
                        "support": actual.support,
                        "admissible_supports": actual.admissible_supports,
                        "distance": actual.distance,
                    }
                    digest.update(
                        (
                            json.dumps(
                                record,
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                            + "\n"
                        ).encode()
                    )
                    configurations += 1
    return {
        "schema": "erasemap-erasure-tomography-conformance-v1",
        "claim": (
            "the production bounded decoder equals an independently structured "
            "integer-bitmask exhaustive oracle on every listed configuration"
        ),
        "configurations": configurations,
        "localized": counts[TomographyVerdict.LOCALIZED],
        "no_observed_recurrence": counts[
            TomographyVerdict.NO_OBSERVED_RECURRENCE
        ],
        "ambiguous": counts[TomographyVerdict.AMBIGUOUS],
        "out_of_model": counts[TomographyVerdict.OUT_OF_MODEL],
        "unverified": counts[TomographyVerdict.UNVERIFIED],
        "mismatches": mismatches,
        "records_sha256": digest.hexdigest(),
    }
