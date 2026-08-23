from __future__ import annotations

from dataclasses import dataclass

from erasemap.ghostgraph import GraphHypothesis


@dataclass(frozen=True, slots=True)
class GhostGraphControlTrial:
    graph_id: str
    control_ids: tuple[str, ...]
    uncontrolled_recurrence: bool
    post_control_recurrence: bool
    retained_subject_loss: bool
    uncontrolled_snapshot: tuple[tuple[str, tuple[str, ...]], ...]
    controlled_snapshot: tuple[tuple[str, tuple[str, ...]], ...]


class GhostGraphStateLab:
    def __init__(
        self,
        graph: GraphHypothesis,
        *,
        target_subject: str,
        retained_subject: str,
    ) -> None:
        if not target_subject or not retained_subject or target_subject == retained_subject:
            raise ValueError("target and retained subjects must be distinct non-empty values")
        self.graph = graph
        self.target_subject = target_subject
        self.retained_subject = retained_subject
        self._states: dict[str, set[str]] = {}
        self.reset()

    def reset(self) -> None:
        self._states = {
            node.node_id: {self.retained_subject} for node in self.graph.nodes
        }
        for node_id in self.graph.initial_node_ids:
            self._states[node_id].add(self.target_subject)
        for node_id in self.graph.residual_node_ids:
            self._states[node_id].discard(self.target_subject)

    @property
    def target_in_residual(self) -> bool:
        return any(
            self.target_subject in self._states[node_id]
            for node_id in self.graph.residual_node_ids
        )

    @property
    def retained_in_residual(self) -> bool:
        return all(
            self.retained_subject in self._states[node_id]
            for node_id in self.graph.residual_node_ids
        )

    def replay(self, guarded_edge_ids: frozenset[str]) -> bool:
        known_edge_ids = frozenset(edge.edge_id for edge in self.graph.edges)
        unknown = guarded_edge_ids - known_edge_ids
        if unknown:
            # Unknown guards are harmless declarations from other robust scenarios.
            guarded_edge_ids = guarded_edge_ids & known_edge_ids
        for _ in range(len(self.graph.nodes)):
            changed = False
            before = {node_id: set(subjects) for node_id, subjects in self._states.items()}
            for edge in self.graph.edges:
                for subject in before[edge.source_id]:
                    if subject == self.target_subject and edge.edge_id in guarded_edge_ids:
                        continue
                    if subject not in self._states[edge.target_id]:
                        self._states[edge.target_id].add(subject)
                        changed = True
            if not changed:
                break
        return self.target_in_residual

    def snapshot(self) -> dict[str, tuple[str, ...]]:
        return {
            node_id: tuple(sorted(subjects))
            for node_id, subjects in sorted(self._states.items())
        }


def run_control_trial(
    graph: GraphHypothesis,
    control_ids: tuple[str, ...],
) -> GhostGraphControlTrial:
    if len(set(control_ids)) != len(control_ids):
        raise ValueError("control IDs must be unique")
    lab = GhostGraphStateLab(
        graph,
        target_subject="ghostgraph-target",
        retained_subject="ghostgraph-retained",
    )
    uncontrolled = lab.replay(frozenset())
    uncontrolled_snapshot = tuple(lab.snapshot().items())
    lab.reset()
    guarded = frozenset(
        control_id.removeprefix("guard:")
        for control_id in control_ids
        if control_id.startswith("guard:")
    )
    post_control = lab.replay(guarded)
    controlled_snapshot = tuple(lab.snapshot().items())
    return GhostGraphControlTrial(
        graph_id=graph.graph_id,
        control_ids=control_ids,
        uncontrolled_recurrence=uncontrolled,
        post_control_recurrence=post_control,
        retained_subject_loss=not lab.retained_in_residual,
        uncontrolled_snapshot=uncontrolled_snapshot,
        controlled_snapshot=controlled_snapshot,
    )
