from __future__ import annotations

import itertools

from erasemap.erasure_tomography import (
    ProbeDesign,
    TomographyEvidence,
    decode,
)
from erasemap.erasure_tomography_conformance import (
    run_erasure_tomography_conformance,
)
from erasemap.erasure_tomography_oracle import oracle_decode


def test_oracle_matches_production_on_complete_small_domain() -> None:
    evidence = TomographyEvidence.complete()
    for width in range(1, 5):
        mechanism_ids = tuple(f"m{index}" for index in range(width))
        rows = tuple(
            tuple(index == column for index in range(width))
            for column in range(width)
        )
        for max_failures in range(min(2, width) + 1):
            design = ProbeDesign(mechanism_ids, rows, max_failures, 0)
            for observations in itertools.product((False, True), repeat=len(rows)):
                actual = decode(design, observations, evidence)
                expected = oracle_decode(design, observations, evidence)
                assert (
                    actual.verdict,
                    actual.support,
                    actual.admissible_supports,
                    actual.distance,
                ) == (
                    expected.verdict,
                    expected.support,
                    expected.admissible_supports,
                    expected.distance,
                )


def test_oracle_matches_unverified_evidence_boundary() -> None:
    design = ProbeDesign(("a",), ((True,),), 1, 0)
    evidence = TomographyEvidence(True, True, False, True, True)

    actual = decode(design, (True,), evidence)
    expected = oracle_decode(design, (True,), evidence)

    assert actual.verdict == expected.verdict
    assert actual.support == expected.support


def test_finite_conformance_has_no_mismatches_and_is_deterministic() -> None:
    first = run_erasure_tomography_conformance()
    second = run_erasure_tomography_conformance()

    assert first == second
    assert first["schema"] == "erasemap-erasure-tomography-conformance-v1"
    assert first["configurations"] > 1_000
    assert first["mismatches"] == 0
    assert first["localized"] > 0
    assert first["ambiguous"] > 0
    assert first["out_of_model"] > 0
    assert first["unverified"] > 0
