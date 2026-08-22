from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StrategyMeasurement:
    seed: int
    strategy: str
    seconds: float
    bytes_rewritten: int
    verdict: str
    retained_count: int
    expected_retained_count: int
    model_weight_delta: float

    def __post_init__(self) -> None:
        if self.strategy not in {"targeted_exact_cdc", "rebuild_all"}:
            raise ValueError("unknown measured strategy")
        if self.seconds <= 0 or self.bytes_rewritten < 0:
            raise ValueError("invalid resource measurement")
        if (
            self.retained_count < 0
            or self.expected_retained_count <= 0
            or self.retained_count > self.expected_retained_count
            or not math.isfinite(self.model_weight_delta)
        ):
            raise ValueError("invalid verification measurement")


def geometric_mean(values: list[float]) -> float:
    if not values or any(value <= 0 or not math.isfinite(value) for value in values):
        raise ValueError("positive finite values are required")
    return math.exp(sum(math.log(value) for value in values) / len(values))


def paired_summary(
    records: list[StrategyMeasurement], *, bootstrap_seed: int, bootstrap_samples: int
) -> dict[str, object]:
    if bootstrap_samples <= 0:
        raise ValueError("bootstrap_samples must be positive")
    by_seed: dict[int, dict[str, StrategyMeasurement]] = {}
    for record in records:
        slot = by_seed.setdefault(record.seed, {})
        if record.strategy in slot:
            raise ValueError("duplicate strategy measurement")
        slot[record.strategy] = record
    expected = {"targeted_exact_cdc", "rebuild_all"}
    if not by_seed or any(set(pair) != expected for pair in by_seed.values()):
        raise ValueError("every seed requires both strategies")
    ordered = [by_seed[seed] for seed in sorted(by_seed)]
    speedups = [
        pair["rebuild_all"].seconds / pair["targeted_exact_cdc"].seconds for pair in ordered
    ]
    point = geometric_mean(speedups)
    rng = random.Random(bootstrap_seed)
    samples = sorted(
        geometric_mean([speedups[rng.randrange(len(speedups))] for _ in speedups])
        for _ in range(bootstrap_samples)
    )
    lower_index = int(0.025 * (bootstrap_samples - 1))
    upper_index = int(0.975 * (bootstrap_samples - 1))
    targeted_bytes = sum(pair["targeted_exact_cdc"].bytes_rewritten for pair in ordered)
    rebuild_bytes = sum(pair["rebuild_all"].bytes_rewritten for pair in ordered)
    return {
        "bytes_reduction": 1 - targeted_bytes / rebuild_bytes if rebuild_bytes else None,
        "complete_rate": sum(
            record.verdict == "COMPLETE" for record in records
        )
        / len(records),
        "maximum_model_weight_delta": max(record.model_weight_delta for record in records),
        "maximum_retained_data_loss_rate": max(
            1 - record.retained_count / record.expected_retained_count for record in records
        ),
        "paired_speedup": {
            "bootstrap_ci95": [samples[lower_index], samples[upper_index]],
            "geometric_mean": point,
            "pairs": len(ordered),
        },
        "rebuild_bytes": rebuild_bytes,
        "targeted_bytes": targeted_bytes,
    }
