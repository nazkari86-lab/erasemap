from __future__ import annotations

import pytest

from erasemap.erasure_tomography import (
    ProbeDesign,
    TomographyEvidence,
    TomographyVerdict,
    certify_design,
    decode,
)


def triangle_design(*, error_budget: int = 0) -> ProbeDesign:
    return ProbeDesign(
        mechanism_ids=("backup", "queue", "vector"),
        rows=(
            (True, True, False),
            (True, False, True),
            (False, True, True),
        ),
        max_failures=1,
        error_budget=error_budget,
    )


def test_unique_support_is_localized() -> None:
    report = decode(
        triangle_design(),
        (True, False, True),
        TomographyEvidence.complete(),
    )

    assert report.verdict is TomographyVerdict.LOCALIZED
    assert report.support == ("queue",)
    assert report.admissible_supports == (("queue",),)
    assert report.distance == 0
    assert report.certificate.uniquely_decodable


def test_identical_columns_are_ambiguous() -> None:
    design = ProbeDesign(("a", "b"), ((True, True),), 1, 0)

    report = decode(design, (True,), TomographyEvidence.complete())

    assert report.verdict is TomographyVerdict.AMBIGUOUS
    assert report.support == ()
    assert report.admissible_supports == (("a",), ("b",))
    assert not report.certificate.uniquely_decodable


def test_missing_execution_evidence_is_unverified() -> None:
    design = ProbeDesign(("a",), ((True,),), 1, 0)
    evidence = TomographyEvidence(
        catalogue_complete=True,
        workflows_executed=False,
        subjects_isolated=True,
        recurrence_observable=True,
        observations_complete=True,
        sparsity_bound_verified=True,
        noise_bound_verified=True,
        stable_behavior=True,
        synthetic_subjects_only=True,
    )

    report = decode(design, (True,), evidence)

    assert report.verdict is TomographyVerdict.UNVERIFIED
    assert report.support == ()


def test_all_negative_is_not_global_complete() -> None:
    design = ProbeDesign(
        ("a", "b"),
        ((True, False), (False, True)),
        1,
        0,
    )

    report = decode(design, (False, False), TomographyEvidence.complete())

    assert report.verdict is TomographyVerdict.NO_OBSERVED_RECURRENCE
    assert report.support == ()


def test_error_correcting_design_recovers_one_flipped_observation() -> None:
    design = ProbeDesign(
        ("a", "b"),
        (
            (True, False),
            (True, False),
            (True, False),
            (False, True),
            (False, True),
            (False, True),
        ),
        1,
        1,
    )

    report = decode(
        design,
        (True, False, True, False, False, False),
        TomographyEvidence.complete(),
    )

    assert report.verdict is TomographyVerdict.LOCALIZED
    assert report.support == ("a",)
    assert report.distance == 1
    assert report.certificate.minimum_outcome_distance == 3


def test_observation_outside_bounded_model_is_rejected() -> None:
    design = ProbeDesign(
        ("a", "b"),
        ((True, False), (False, True)),
        1,
        0,
    )

    report = decode(design, (True, True), TomographyEvidence.complete())

    assert report.verdict is TomographyVerdict.OUT_OF_MODEL
    assert report.admissible_supports == ()


def test_certificate_lists_indistinguishable_supports() -> None:
    design = ProbeDesign(("a", "b"), ((True, True),), 1, 0)

    certificate = certify_design(design)

    assert certificate.support_count == 3
    assert certificate.minimum_outcome_distance == 0
    assert certificate.indistinguishable_support_pairs == ((('a',), ('b',)),)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (((), ((True,),), 0, 0), "mechanism"),
        ((("a", "a"), ((True, False),), 1, 0), "unique"),
        ((("a",), (), 1, 0), "probe"),
        ((("a", "b"), ((True,),), 1, 0), "match"),
        ((("a",), ((True,),), 2, 0), "maximum"),
        ((("a",), ((True,),), 1, -1), "error"),
    ],
)
def test_design_validation_rejects_invalid_contract(
    args: tuple[object, object, int, int], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        ProbeDesign(*args)  # type: ignore[arg-type]


def test_wrong_observation_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="observation"):
        decode(triangle_design(), (True,), TomographyEvidence.complete())


def test_decoding_is_deterministic() -> None:
    design = triangle_design()
    evidence = TomographyEvidence.complete()

    first = decode(design, (False, True, True), evidence)
    second = decode(design, (False, True, True), evidence)

    assert first == second
