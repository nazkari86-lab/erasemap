from __future__ import annotations

from erasemap.ghostgraph_action import action_signature, build_global_policy
from erasemap.ghostgraph_t_benchmark import experiments, generate_cases
from erasemap.ghostgraph_t_eval import evaluate_strategy


def test_global_policy_identifies_in_model_action_and_rejects_ood_family() -> None:
    probes = experiments()
    cases = generate_cases()
    for case in (cases[0], cases[120], cases[200], cases[250]):
        policy = build_global_policy(case.catalogue, probes)
        outcome = evaluate_strategy(
            "global-action-policy",
            case.truth,
            case.catalogue,
            probes,
            global_policy=policy,
            random_seed=7,
        )
        assert outcome.verdict == case.expected
        if case.expected == "ACTION_IDENTIFIED":
            assert outcome.predicted_action == action_signature(case.truth)
        else:
            assert outcome.predicted_action is None


def test_all_frozen_strategies_return_typed_fail_closed_outcomes() -> None:
    case = generate_cases()[0]
    probes = experiments()
    policy = build_global_policy(case.catalogue, probes)
    for strategy in (
        "global-action-policy",
        "one-step-minimax",
        "exact-graph-minimax-ablation",
        "greedy-separated-pairs",
        "frozen-random",
        "nonadaptive-exhaustive",
        "sink-only-ablation",
        "passive-lineage-ablation",
    ):
        outcome = evaluate_strategy(
            strategy,
            case.truth,
            case.catalogue,
            probes,
            global_policy=policy,
            random_seed=11,
        )
        assert outcome.verdict in {
            "ACTION_IDENTIFIED",
            "OUT_OF_HYPOTHESIS",
            "UNVERIFIED",
        }
