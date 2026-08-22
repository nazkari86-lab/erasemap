from __future__ import annotations

from dataclasses import dataclass

from erasemap.cdc import evaluate_actions, exact_cdc, greedy_cdc
from erasemap.holdout_commitment import PublicCase
from erasemap.multiview_verifier import compose_channels
from erasemap.pcug_domain import EdgeState, PCUGVerdict

METHODS = ("pcug", "typed_node_audit", "flat_checklist", "model_only", "receipt_only")


@dataclass(frozen=True, slots=True)
class EvaluationRecord:
    case_id: str
    family: str
    case_commitment: str
    method: str
    verdict: str
    shortest_path: tuple[str, ...] | None
    exception: str


def _node_verdict(case: PublicCase, limit: int) -> PCUGVerdict:
    states = tuple(node.state for node in case.case.graph.nodes[:limit])
    if any(state is EdgeState.ACTIVE for state in states):
        return PCUGVerdict.INCOMPLETE
    if any(state is EdgeState.UNKNOWN for state in states):
        return PCUGVerdict.UNVERIFIED
    return PCUGVerdict.COMPLETE


def evaluate_case(case: PublicCase, method: str) -> EvaluationRecord:
    try:
        if method == "pcug":
            report = evaluate_actions(case.case.graph, case.case.protocol, ())
            verdict = report.verdict
            path = report.shortest_counterexample
        elif method == "typed_node_audit":
            verdict, path = _node_verdict(case, 3), None
        elif method == "flat_checklist":
            verdict, path = _node_verdict(case, 1), None
        elif method == "model_only":
            verdict = compose_channels(case.case.graph.channel_results).verdict
            path = None
        elif method == "receipt_only":
            verdict, path = PCUGVerdict.COMPLETE, None
        else:
            raise ValueError(f"unknown method: {method}")
        return EvaluationRecord(
            case.id, case.family, case.case_commitment, method, verdict.value, path, ""
        )
    except Exception as error:  # fail-closed record, never an exclusion
        return EvaluationRecord(
            case.id,
            case.family,
            case.case_commitment,
            method,
            PCUGVerdict.UNVERIFIED.value,
            None,
            f"{type(error).__name__}: {error}",
        )


def evaluate_public_cases(cases: tuple[PublicCase, ...]) -> tuple[EvaluationRecord, ...]:
    return tuple(evaluate_case(case, method) for case in cases for method in METHODS)


def planner_records(cases: tuple[PublicCase, ...]) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    for case in cases:
        for method in ("exact_cdc", "greedy_cdc", "delete_all"):
            if method == "exact_cdc":
                plan = exact_cdc(case.case.graph, case.case.protocol, case.case.actions)
            elif method == "greedy_cdc":
                plan = greedy_cdc(case.case.graph, case.case.protocol, case.case.actions)
            else:
                report = evaluate_actions(case.case.graph, case.case.protocol, case.case.actions)
                records.append(
                    {
                        "action_ids": [action.id for action in case.case.actions],
                        "case_id": case.id,
                        "cost": sum(action.cost for action in case.case.actions),
                        "method": method,
                        "verdict": report.verdict.value,
                    }
                )
                continue
            records.append(
                {
                    "action_ids": list(plan.action_ids),
                    "case_id": case.id,
                    "cost": plan.total_cost,
                    "method": method,
                    "verdict": plan.verdict.value,
                }
            )
    return tuple(records)
