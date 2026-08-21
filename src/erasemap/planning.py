from __future__ import annotations

from collections.abc import Iterable

from erasemap.domain import RemediationAction, RemediationPlan


def _plan(
    required: frozenset[str],
    chosen: tuple[RemediationAction, ...],
) -> RemediationPlan:
    covered = frozenset().union(
        *(action.covers_artifact_ids for action in chosen)
    ) & required
    return RemediationPlan(
        action_ids=tuple(sorted(action.id for action in chosen)),
        total_cost=sum(action.cost for action in chosen),
        covered_artifact_ids=covered,
        uncovered_artifact_ids=required - covered,
    )


def _partial_key(plan: RemediationPlan) -> tuple[int, int, int, tuple[str, ...]]:
    return (-len(plan.covered_artifact_ids), plan.total_cost, len(plan.action_ids), plan.action_ids)


def _complete_key(plan: RemediationPlan) -> tuple[int, int, tuple[str, ...]]:
    return (plan.total_cost, len(plan.action_ids), plan.action_ids)


def exact_plan(
    required_artifact_ids: frozenset[str],
    actions: Iterable[RemediationAction],
) -> RemediationPlan:
    candidates = tuple(
        sorted((action for action in actions if action.permitted), key=lambda item: item.id)
    )
    if len(candidates) > 30:
        raise ValueError("exact_plan supports at most 30 permitted actions; use greedy_plan")
    if not required_artifact_ids:
        return _plan(required_artifact_ids, ())

    suffix_coverage: list[frozenset[str]] = [frozenset()] * (len(candidates) + 1)
    for index in range(len(candidates) - 1, -1, -1):
        suffix_coverage[index] = suffix_coverage[index + 1] | candidates[index].covers_artifact_ids

    best_complete: RemediationPlan | None = None
    best_partial = _plan(required_artifact_ids, ())

    def search(
        index: int,
        chosen: tuple[RemediationAction, ...],
        covered: frozenset[str],
        cost: int,
    ) -> None:
        nonlocal best_complete, best_partial
        current = _plan(required_artifact_ids, chosen)
        if _partial_key(current) < _partial_key(best_partial):
            best_partial = current
        if required_artifact_ids <= covered:
            if best_complete is None or _complete_key(current) < _complete_key(best_complete):
                best_complete = current
            return
        if index == len(candidates):
            return
        if best_complete is not None and cost >= best_complete.total_cost:
            return
        if (
            best_complete is not None
            and not required_artifact_ids <= covered | suffix_coverage[index]
        ):
            return

        action = candidates[index]
        search(
            index + 1,
            (*chosen, action),
            covered | action.covers_artifact_ids,
            cost + action.cost,
        )
        search(index + 1, chosen, covered, cost)

    search(0, (), frozenset(), 0)
    return best_complete if best_complete is not None else best_partial


def greedy_plan(
    required_artifact_ids: frozenset[str],
    actions: Iterable[RemediationAction],
) -> RemediationPlan:
    remaining_actions = sorted(
        (action for action in actions if action.permitted),
        key=lambda item: item.id,
    )
    uncovered = set(required_artifact_ids)
    chosen: list[RemediationAction] = []
    while uncovered:
        useful = [
            (action.cost / len(action.covers_artifact_ids & uncovered), action.id, action)
            for action in remaining_actions
            if action.covers_artifact_ids & uncovered
        ]
        if not useful:
            break
        _, _, selected = min(useful, key=lambda item: (item[0], item[1]))
        chosen.append(selected)
        uncovered -= selected.covers_artifact_ids
        remaining_actions = [action for action in remaining_actions if action.id != selected.id]
    return _plan(required_artifact_ids, tuple(chosen))
