import numpy as np
import pytest

from erasemap.verification_metrics import (
    bootstrap_mean_interval,
    linear_cka,
    normalize_rows,
    verification_metrics,
)


def test_normalize_rows_and_cka_identity() -> None:
    values = np.array([[3.0, 4.0], [0.0, 2.0], [2.0, 1.0]])
    normalized = normalize_rows(values)
    assert np.linalg.norm(normalized, axis=1) == pytest.approx(np.ones(3))
    assert linear_cka(values, values) == pytest.approx(1.0)


def test_verification_metrics_separates_pairs() -> None:
    result = verification_metrics(
        np.array([0.8, 0.9]), np.array([0.1, 0.2]), far_target=0.01
    )
    assert result.auc == 1.0
    assert result.tar_at_far == 1.0


def test_bootstrap_interval_is_deterministic() -> None:
    values = np.array([1.0, 2.0, 3.0])
    assert bootstrap_mean_interval(values, seed=7, samples=100) == bootstrap_mean_interval(
        values, seed=7, samples=100
    )


@pytest.mark.parametrize(
    "call",
    [
        lambda: normalize_rows(np.array([])),
        lambda: linear_cka(np.ones((2, 2)), np.ones((3, 2))),
        lambda: verification_metrics(np.array([]), np.array([1.0]), far_target=0.1),
        lambda: bootstrap_mean_interval(np.array([]), seed=1, samples=10),
    ],
)
def test_invalid_inputs(call: object) -> None:
    with pytest.raises(ValueError):
        call()  # type: ignore[operator]
