from __future__ import annotations

from dataclasses import replace
from itertools import combinations

from erasemap.multiview_verifier import compose_channels
from erasemap.pcug_domain import (
    CDCAction,
    CDCPlan,
    CDCProtocol,
    EdgeState,
    FeasibilityReport,
    PCUGEdge,
    PCUGGraph,
    PCUGVerdict,
    SolverStatus,
    TransitionTarget,
)


def _apply_action(graph: PCUGGraph, action: CDCAction) -> PCUGGraph:
    if not action.permitted:
        raise ValueError(f"action {action.id!r} is not permitted")
    nodes = {node.id: node for node in graph.nodes}
    edges = {edge.id: edge for edge in graph.edges}
    for transition in action.transitions:
        state = transition.result_state if transition.verified else EdgeState.UNKNOWN
        evidence_id = transition.evidence_id if transition.verified else ""
        if transition.target is TransitionTarget.NODE:
            node = nodes.get(transition.target_id)
            if node is None:
                raise ValueError(f"action {action.id!r} targets unknown node")
            nodes[node.id] = replace(
                node,
                state=state,
                active_sink=node.active_sink and state is not EdgeState.CLOSED,
                evidence_id=evidence_id,
            )
        else:
            edge = edges.get(transition.target_id)
            if edge is None:
                raise ValueError(f"action {action.id!r} targets unknown edge")
            edges[edge.id] = replace(edge, state=state, evidence_id=evidence_id)

    channels = {(item.name, item.stratum): item for item in graph.channel_results}
    for channel in action.result_channels:
        channels[(channel.name, channel.stratum)] = channel
    return PCUGGraph(
        nodes=tuple(sorted(nodes.values(), key=lambda item: item.id)),
        edges=tuple(sorted(edges.values(), key=lambda item: item.id)),
        channel_results=tuple(
            sorted(channels.values(), key=lambda item: (item.name, item.stratum))
        ),
    )


def _request_starts(graph: PCUGGraph, protocol: CDCProtocol) -> tuple[str, ...]:
    starts = {
        node.id
        for node in graph.nodes
        if node.subject_id == protocol.subject_id and node.state is not EdgeState.CLOSED
    }
    starts.update(protocol.source_ids)
    starts.update(
        edge.source_id
        for edge in graph.edges
        if edge.request_scoped
        and edge.subject_id == protocol.subject_id
        and edge.state is not EdgeState.CLOSED
    )
    return tuple(sorted(starts))


def _classified_paths(
    graph: PCUGGraph, protocol: CDCProtocol
) -> tuple[tuple[tuple[str, ...], ...], tuple[tuple[str, ...], ...]]:
    nodes = {node.id: node for node in graph.nodes}
    outgoing: dict[str, list[PCUGEdge]] = {}
    for edge in graph.edges:
        outgoing.setdefault(edge.source_id, []).append(edge)
    for edges in outgoing.values():
        edges.sort(key=lambda item: item.id)

    active_paths: set[tuple[str, ...]] = set()
    unknown_paths: set[tuple[str, ...]] = set()

    def walk(
        node_id: str,
        path: tuple[str, ...],
        visited: frozenset[str],
        uncertain: bool,
    ) -> None:
        node = nodes[node_id]
        node_uncertain = uncertain or node.state is EdgeState.UNKNOWN
        if node_id in protocol.sink_ids and node.state is not EdgeState.CLOSED:
            (unknown_paths if node_uncertain else active_paths).add(path)
        for edge in outgoing.get(node_id, ()):
            target = nodes[edge.target_id]
            if edge.state is EdgeState.CLOSED or target.state is EdgeState.CLOSED:
                continue
            if edge.target_id in visited:
                continue
            walk(
                edge.target_id,
                (*path, edge.target_id),
                visited | {edge.target_id},
                node_uncertain
                or edge.state is EdgeState.UNKNOWN
                or target.state is EdgeState.UNKNOWN,
            )

    for start in _request_starts(graph, protocol):
        node = nodes[start]
        if node.state is EdgeState.CLOSED:
            continue
        walk(start, (start,), frozenset({start}), node.state is EdgeState.UNKNOWN)
    return tuple(sorted(active_paths, key=lambda p: (len(p), p))), tuple(
        sorted(unknown_paths, key=lambda p: (len(p), p))
    )


def evaluate_actions(
    graph: PCUGGraph,
    protocol: CDCProtocol,
    actions: tuple[CDCAction, ...],
) -> FeasibilityReport:
    protocol.validate_graph(graph)
    action_ids = [action.id for action in actions]
    if len(action_ids) != len(set(action_ids)):
        raise ValueError("duplicate selected action")
    state = graph
    for action in sorted(actions, key=lambda item: item.id):
        state = _apply_action(state, action)

    active_paths, unknown_paths = _classified_paths(state, protocol)
    verification = compose_channels(
        state.channel_results,
        required_names=protocol.mandatory_channels,
    )
    if active_paths or verification.verdict is PCUGVerdict.INCOMPLETE:
        verdict = PCUGVerdict.INCOMPLETE
    elif unknown_paths or verification.verdict is PCUGVerdict.UNVERIFIED:
        verdict = PCUGVerdict.UNVERIFIED
    else:
        verdict = PCUGVerdict.COMPLETE
    candidates = (*active_paths, *unknown_paths)
    shortest = min(candidates, key=lambda path: (len(path), path)) if candidates else None
    return FeasibilityReport(
        graph=state,
        verdict=verdict,
        active_paths=active_paths,
        unknown_paths=unknown_paths,
        shortest_counterexample=shortest,
        failed_channels=verification.failed_channels,
        unknown_channels=(*verification.unknown_channels, *verification.missing_channels),
    )


def _violation_count(report: FeasibilityReport) -> int:
    return (
        len(report.active_paths)
        + len(report.unknown_paths)
        + len(report.failed_channels)
        + len(report.unknown_channels)
    )


def _make_plan(
    chosen: tuple[CDCAction, ...],
    report: FeasibilityReport,
    status: SolverStatus,
) -> CDCPlan:
    ordered = tuple(sorted(chosen, key=lambda item: item.id))
    cost = sum(action.cost for action in ordered)
    complete = report.verdict is PCUGVerdict.COMPLETE
    return CDCPlan(
        action_ids=tuple(action.id for action in ordered),
        total_cost=cost,
        verdict=report.verdict,
        solver_status=status,
        report=report,
        lower_cost_bound=cost if complete and status is SolverStatus.OPTIMAL else 0,
        upper_cost_bound=cost if complete else None,
    )


def _complete_key(plan: CDCPlan) -> tuple[int, int, tuple[str, ...]]:
    return plan.total_cost, len(plan.action_ids), plan.action_ids


def _partial_key(plan: CDCPlan) -> tuple[int, int, int, tuple[str, ...]]:
    return (
        _violation_count(plan.report),
        plan.total_cost,
        len(plan.action_ids),
        plan.action_ids,
    )


def brute_force_cdc(
    graph: PCUGGraph,
    protocol: CDCProtocol,
    actions: tuple[CDCAction, ...],
) -> CDCPlan:
    ordered = tuple(sorted((action for action in actions if action.permitted), key=lambda a: a.id))
    best_complete: CDCPlan | None = None
    best_partial: CDCPlan | None = None
    for size in range(len(ordered) + 1):
        for chosen in combinations(ordered, size):
            report = evaluate_actions(graph, protocol, chosen)
            status = (
                SolverStatus.OPTIMAL
                if report.verdict is PCUGVerdict.COMPLETE
                else SolverStatus.INFEASIBLE
            )
            candidate = _make_plan(chosen, report, status)
            if report.verdict is PCUGVerdict.COMPLETE:
                if best_complete is None or _complete_key(candidate) < _complete_key(best_complete):
                    best_complete = candidate
            elif best_partial is None or _partial_key(candidate) < _partial_key(best_partial):
                best_partial = candidate
    if best_complete is not None:
        return best_complete
    if best_partial is None:
        raise AssertionError("empty action subset must produce a plan")
    return best_partial


def exact_cdc(
    graph: PCUGGraph,
    protocol: CDCProtocol,
    actions: tuple[CDCAction, ...],
) -> CDCPlan:
    ordered = tuple(sorted((action for action in actions if action.permitted), key=lambda a: a.id))
    if len(ordered) > protocol.max_exact_actions:
        raise ValueError("exact CDC action limit exceeded")

    best_complete: CDCPlan | None = None
    best_partial: CDCPlan | None = None

    def search(index: int, chosen: tuple[CDCAction, ...], cost: int) -> None:
        nonlocal best_complete, best_partial
        report = evaluate_actions(graph, protocol, chosen)
        if report.verdict is PCUGVerdict.COMPLETE:
            candidate = _make_plan(chosen, report, SolverStatus.OPTIMAL)
            if best_complete is None or _complete_key(candidate) < _complete_key(best_complete):
                best_complete = candidate
            return
        if best_complete is not None and (
            cost > best_complete.total_cost
            or (cost == best_complete.total_cost and len(chosen) >= len(best_complete.action_ids))
        ):
            return
        partial = _make_plan(chosen, report, SolverStatus.INFEASIBLE)
        if best_partial is None or _partial_key(partial) < _partial_key(best_partial):
            best_partial = partial
        if index == len(ordered):
            return
        action = ordered[index]
        search(index + 1, (*chosen, action), cost + action.cost)
        search(index + 1, chosen, cost)

    search(0, (), 0)
    if best_complete is not None:
        return best_complete
    if best_partial is None:
        raise AssertionError("empty action subset must produce a plan")
    return best_partial


def greedy_cdc(
    graph: PCUGGraph,
    protocol: CDCProtocol,
    actions: tuple[CDCAction, ...],
) -> CDCPlan:
    chosen: tuple[CDCAction, ...] = ()
    remaining = tuple(
        sorted((action for action in actions if action.permitted), key=lambda action: action.id)
    )
    report = evaluate_actions(graph, protocol, chosen)
    while report.verdict is not PCUGVerdict.COMPLETE:
        current_violations = _violation_count(report)
        ranked: list[tuple[float, int, str, CDCAction, FeasibilityReport]] = []
        for action in remaining:
            candidate_report = evaluate_actions(graph, protocol, (*chosen, action))
            improvement = current_violations - _violation_count(candidate_report)
            if improvement <= 0:
                continue
            ratio = float("inf") if action.cost == 0 else improvement / action.cost
            ranked.append((-ratio, action.cost, action.id, action, candidate_report))
        if not ranked:
            break
        _, _, _, selected, selected_report = min(ranked, key=lambda item: item[:3])
        chosen = (*chosen, selected)
        remaining = tuple(action for action in remaining if action.id != selected.id)
        report = selected_report
    status = (
        SolverStatus.APPROXIMATE
        if report.verdict is PCUGVerdict.COMPLETE
        else SolverStatus.INFEASIBLE
    )
    return _make_plan(chosen, report, status)
