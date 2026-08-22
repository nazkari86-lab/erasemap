from __future__ import annotations

import pytest

from erasemap.measured_systems import StrategyMeasurement, geometric_mean, paired_summary


def _record(seed: int, strategy: str, seconds: float, written: int) -> StrategyMeasurement:
    return StrategyMeasurement(seed, strategy, seconds, written, "COMPLETE", 249, 1e-12)


def test_paired_summary_uses_paired_geometric_speedup() -> None:
    records = [
        _record(1, "targeted_exact_cdc", 1.0, 10),
        _record(1, "rebuild_all", 2.0, 100),
        _record(2, "targeted_exact_cdc", 2.0, 20),
        _record(2, "rebuild_all", 8.0, 200),
    ]
    summary = paired_summary(records, bootstrap_seed=7, bootstrap_samples=1000)
    assert summary["paired_speedup"]["geometric_mean"] == pytest.approx(geometric_mean([2, 4]))
    assert summary["bytes_reduction"] == pytest.approx(0.9)
    assert summary["complete_rate"] == 1.0


def test_paired_summary_rejects_incomplete_pairs() -> None:
    with pytest.raises(ValueError, match="both strategies"):
        paired_summary(
            [_record(1, "targeted_exact_cdc", 1.0, 10)],
            bootstrap_seed=1,
            bootstrap_samples=10,
        )
