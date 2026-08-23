from __future__ import annotations

import itertools

import pytest

from erasemap.erasure_tomography_design import (
    DesignStatus,
    construct_minimum_design,
)


def all_nonzero_rows(width: int) -> tuple[tuple[bool, ...], ...]:
    return tuple(itertools.product((False, True), repeat=width))[1:]


def test_constructor_finds_minimum_row_design() -> None:
    result = construct_minimum_design(
        ("a", "b", "c", "d"),
        all_nonzero_rows(4),
        max_failures=1,
        error_budget=0,
    )

    assert result.status is DesignStatus.OPTIMAL
    assert result.design is not None
    assert result.design.certificate.uniquely_decodable
    assert len(result.design.probe_design.rows) == 3


def test_constructor_reports_infeasible_constraints() -> None:
    result = construct_minimum_design(
        ("a", "b"),
        ((True, True),),
        max_failures=1,
        error_budget=0,
    )

    assert result.status is DesignStatus.INFEASIBLE
    assert result.design is None
    assert result.indistinguishable_support_pairs


def test_constructor_minimizes_declared_cost_after_row_count() -> None:
    rows = (
        (True, False),
        (False, True),
        (True, True),
    )
    result = construct_minimum_design(
        ("a", "b"),
        rows,
        max_failures=1,
        error_budget=0,
        row_costs=(9, 2, 1),
    )

    assert result.design is not None
    assert result.design.probe_design.rows == ((False, True), (True, True))
    assert result.design.total_cost == 3


def test_constructor_is_invariant_to_input_order_and_duplicate_rows() -> None:
    rows = all_nonzero_rows(3)
    forward = construct_minimum_design(("a", "b", "c"), rows, 1, 0)
    reverse = construct_minimum_design(
        ("a", "b", "c"),
        (*tuple(reversed(rows)), rows[0]),
        1,
        0,
    )

    assert forward == reverse


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (((False, False),), "all-zero"),
        (((True,),), "width"),
    ],
)
def test_constructor_rejects_invalid_feasible_rows(
    rows: tuple[tuple[bool, ...], ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        construct_minimum_design(("a", "b"), rows, 1, 0)


def test_constructor_rejects_invalid_cost_catalogue() -> None:
    with pytest.raises(ValueError, match="cost"):
        construct_minimum_design(
            ("a", "b"),
            ((True, False), (False, True)),
            1,
            0,
            row_costs=(1,),
        )


def test_small_domains_match_exhaustive_minimum_row_count() -> None:
    for width in range(2, 5):
        mechanism_ids = tuple(f"m{index}" for index in range(width))
        rows = all_nonzero_rows(width)
        result = construct_minimum_design(mechanism_ids, rows, 1, 0)

        assert result.design is not None
        expected_rows = (width + 1).bit_length()
        if 2 ** (expected_rows - 1) >= width + 1:
            expected_rows -= 1
        assert len(result.design.probe_design.rows) == expected_rows
