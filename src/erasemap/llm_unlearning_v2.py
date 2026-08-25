from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from erasemap.llm_unlearning import binary_auc, finite_float, mean

MODEL_IDS = ("base", "target", "exact", "candidate", "candidate_reloaded")
FLAT_CHANNELS = (
    "forget_answer",
    "forget_paraphrase",
    "holdout",
    "retain",
    "world_facts",
    "real_authors",
)
NESTED_CHANNELS = ("forget_perturbed",)


def _flat(values: object, *, name: str) -> list[float]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{name} must be a non-empty list")
    return [finite_float(value, name=name) for value in values]


def _nested(values: object, *, name: str) -> list[list[float]]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{name} must be a non-empty nested list")
    rows = [_flat(value, name=f"{name}[{index}]") for index, value in enumerate(values)]
    width = len(rows[0])
    if width == 0 or any(len(row) != width for row in rows):
        raise ValueError(f"{name} must be rectangular")
    return rows


def validate_evaluations(evaluations: Mapping[str, Mapping[str, object]]) -> None:
    if set(evaluations) != set(MODEL_IDS):
        raise ValueError("evaluation matrix has an unexpected model set")
    expected = set(FLAT_CHANNELS) | set(NESTED_CHANNELS)
    reference_counts: dict[str, tuple[int, int | None]] = {}
    for model_id, channels in evaluations.items():
        if set(channels) != expected:
            raise ValueError(f"evaluation matrix has an unexpected channel set: {model_id}")
        for channel in FLAT_CHANNELS:
            values = _flat(channels[channel], name=f"{model_id}.{channel}")
            shape: tuple[int, int | None] = (len(values), None)
            if channel in reference_counts and reference_counts[channel] != shape:
                raise ValueError(f"evaluation count mismatch: {channel}")
            reference_counts[channel] = shape
        nested = _nested(
            channels["forget_perturbed"], name=f"{model_id}.forget_perturbed"
        )
        shape = (len(nested), len(nested[0]))
        if "forget_perturbed" in reference_counts and reference_counts[
            "forget_perturbed"
        ] != shape:
            raise ValueError("evaluation shape mismatch: forget_perturbed")
        reference_counts["forget_perturbed"] = shape
        if len(nested) != len(_flat(channels["forget_paraphrase"], name="paraphrase")):
            raise ValueError("paraphrase and perturbed rows must align")


def _truth_margins(channels: Mapping[str, object], *, model_id: str) -> list[float]:
    paraphrase = _flat(channels["forget_paraphrase"], name=f"{model_id}.paraphrase")
    perturbed = _nested(channels["forget_perturbed"], name=f"{model_id}.perturbed")
    return [
        mean(row, name=f"{model_id}.perturbed[{index}]") - paraphrase[index]
        for index, row in enumerate(perturbed)
    ]


def _normalized_recovery(target: float, exact: float, candidate: float) -> float:
    denominator = exact - target
    if denominator <= 0:
        raise ValueError("exact reference must increase forget loss relative to target")
    return (candidate - target) / denominator


def score_v2_trial(
    evaluations: Mapping[str, Mapping[str, object]],
    *,
    recurrence_after_reload: float,
    candidate_runtime_seconds: float,
    exact_runtime_seconds: float,
) -> dict[str, float]:
    validate_evaluations(evaluations)
    averages: dict[str, float] = {}
    truth_margins: dict[str, float] = {}
    for model_id, channels in evaluations.items():
        for channel in FLAT_CHANNELS:
            averages[f"{model_id}_{channel}_nll"] = mean(
                _flat(channels[channel], name=f"{model_id}.{channel}"),
                name=f"{model_id}.{channel}",
            )
        margins = _truth_margins(channels, model_id=model_id)
        truth_margins[model_id] = mean(margins, name=f"{model_id}.truth_margin")

    target_forget = averages["target_forget_answer_nll"]
    exact_forget = averages["exact_forget_answer_nll"]
    candidate_forget = averages["candidate_forget_answer_nll"]
    exact_runtime = finite_float(exact_runtime_seconds, name="exact_runtime_seconds")
    candidate_runtime = finite_float(
        candidate_runtime_seconds, name="candidate_runtime_seconds"
    )
    if exact_runtime <= 0 or candidate_runtime <= 0:
        raise ValueError("training runtimes must be positive")
    exact_lift = exact_forget - target_forget
    metrics = {
        **averages,
        **{f"{model_id}_forget_truth_margin": value for model_id, value in truth_margins.items()},
        "target_memorization_gain": averages["base_forget_answer_nll"] - target_forget,
        "exact_forgetting_lift": exact_lift,
        "candidate_forgetting_lift": candidate_forget - target_forget,
        "candidate_exact_normalized_recovery": _normalized_recovery(
            target_forget, exact_forget, candidate_forget
        ),
        "candidate_exact_forget_nll_gap": abs(candidate_forget - exact_forget),
        "candidate_exact_paraphrase_nll_gap": abs(
            averages["candidate_forget_paraphrase_nll"]
            - averages["exact_forget_paraphrase_nll"]
        ),
        "candidate_exact_truth_margin_gap": abs(
            truth_margins["candidate"] - truth_margins["exact"]
        ),
        "candidate_exact_retain_nll_gap": abs(
            averages["candidate_retain_nll"] - averages["exact_retain_nll"]
        ),
        "candidate_world_utility_nll_degradation": (
            averages["candidate_world_facts_nll"] - averages["target_world_facts_nll"]
        ),
        "candidate_real_author_nll_degradation": (
            averages["candidate_real_authors_nll"] - averages["target_real_authors_nll"]
        ),
        "exact_mia_auc": binary_auc(
            [-value for value in _flat(evaluations["exact"]["forget_answer"], name="exact")],
            [-value for value in _flat(evaluations["exact"]["holdout"], name="exact")],
        ),
        "candidate_mia_auc": binary_auc(
            [
                -value
                for value in _flat(
                    evaluations["candidate"]["forget_answer"], name="candidate"
                )
            ],
            [
                -value
                for value in _flat(evaluations["candidate"]["holdout"], name="candidate")
            ],
        ),
        "retained_recurrence_after_reload": finite_float(
            recurrence_after_reload, name="recurrence_after_reload"
        ),
        "candidate_runtime_seconds": candidate_runtime,
        "exact_runtime_seconds": exact_runtime,
        "candidate_speedup_vs_exact": exact_runtime / candidate_runtime,
    }
    metrics["candidate_exact_mia_auc_gap"] = abs(
        metrics["candidate_mia_auc"] - metrics["exact_mia_auc"]
    )
    return metrics


def compute_v2_gates(
    trials: Sequence[Mapping[str, Any]], criteria: Mapping[str, object]
) -> dict[str, bool]:
    if not trials:
        raise ValueError("at least one trial is required")

    def values(name: str) -> list[float]:
        return [finite_float(trial["metrics"][name], name=name) for trial in trials]

    return {
        "target_memorization": min(values("target_memorization_gain"))
        >= finite_float(criteria["target_memorization_gain_min"], name="criterion"),
        "exact_reference_forgets": min(values("exact_forgetting_lift"))
        >= finite_float(criteria["exact_forgetting_lift_min"], name="criterion"),
        "candidate_recovers_exact_effect": min(
            values("candidate_exact_normalized_recovery")
        )
        >= finite_float(criteria["candidate_exact_normalized_recovery_min"], name="criterion"),
        "candidate_does_not_overscrub": max(
            values("candidate_exact_normalized_recovery")
        )
        <= finite_float(criteria["candidate_exact_normalized_recovery_max"], name="criterion"),
        "candidate_matches_exact_paraphrase": max(
            values("candidate_exact_paraphrase_nll_gap")
        )
        <= finite_float(criteria["candidate_exact_paraphrase_nll_gap_max"], name="criterion"),
        "candidate_matches_exact_truth_margin": max(
            values("candidate_exact_truth_margin_gap")
        )
        <= finite_float(criteria["candidate_exact_truth_margin_gap_max"], name="criterion"),
        "candidate_preserves_retain": max(values("candidate_exact_retain_nll_gap"))
        <= finite_float(criteria["candidate_exact_retain_nll_gap_max"], name="criterion"),
        "candidate_preserves_world_utility": max(
            values("candidate_world_utility_nll_degradation")
        )
        <= finite_float(criteria["candidate_world_utility_nll_degradation_max"], name="criterion"),
        "candidate_preserves_real_authors": max(
            values("candidate_real_author_nll_degradation")
        )
        <= finite_float(criteria["candidate_real_author_nll_degradation_max"], name="criterion"),
        "candidate_matches_exact_membership": max(
            values("candidate_exact_mia_auc_gap")
        )
        <= finite_float(criteria["candidate_exact_mia_auc_gap_max"], name="criterion"),
        "candidate_is_faster": min(values("candidate_speedup_vs_exact"))
        >= finite_float(criteria["candidate_speedup_vs_exact_min"], name="criterion"),
        "candidate_survives_reload_without_recurrence": max(
            values("retained_recurrence_after_reload")
        )
        <= finite_float(criteria["retained_recurrence_after_reload_max"], name="criterion"),
    }


def summarize_v2_trials(
    trials: Sequence[Mapping[str, Any]], criteria: Mapping[str, object]
) -> dict[str, object]:
    gates = compute_v2_gates(trials, criteria)
    metric_names = tuple(str(name) for name in trials[0]["metrics"])
    aggregate = {
        name: {
            "mean": mean(
                [finite_float(row["metrics"][name], name=name) for row in trials],
                name=name,
            ),
            "min": min(finite_float(row["metrics"][name], name=name) for row in trials),
            "max": max(finite_float(row["metrics"][name], name=name) for row in trials),
        }
        for name in metric_names
    }
    return {
        "aggregate": aggregate,
        "decision": "PASS" if all(gates.values()) else "FAIL",
        "gates": gates,
    }


def select_development_candidate(
    summaries: Sequence[Mapping[str, Any]], criteria: Mapping[str, object]
) -> str:
    """Select using development evidence only and a deterministic frozen ordering."""
    if not summaries:
        raise ValueError("development sweep must contain candidates")

    recovery_min = finite_float(
        criteria["candidate_exact_normalized_recovery_min"], name="criterion"
    )
    world_max = finite_float(
        criteria["candidate_world_utility_nll_degradation_max"], name="criterion"
    )
    real_max = finite_float(
        criteria["candidate_real_author_nll_degradation_max"], name="criterion"
    )

    def key(row: Mapping[str, Any]) -> tuple[float, float, float, float, str]:
        aggregate = row["aggregate"]
        recovery = finite_float(
            aggregate["candidate_exact_normalized_recovery"]["min"], name="recovery"
        )
        world = finite_float(
            aggregate["candidate_world_utility_nll_degradation"]["max"], name="world"
        )
        real = finite_float(aggregate["candidate_real_author_nll_degradation"]["max"], name="real")
        speedup = finite_float(aggregate["candidate_speedup_vs_exact"]["min"], name="speedup")
        violation = (
            max(0.0, recovery_min - recovery) / max(recovery_min, 1e-12)
            + max(0.0, world - world_max) / max(abs(world_max), 1e-12)
            + max(0.0, real - real_max) / max(abs(real_max), 1e-12)
        )
        return (violation, -recovery, max(world, real), -speedup, str(row["candidate_id"]))

    return str(min(summaries, key=key)["candidate_id"])
