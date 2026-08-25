from __future__ import annotations

import hashlib
from dataclasses import dataclass
from itertools import combinations

from erasemap.ghostgraph import DiscoveryExperiment, GraphEdge, GraphHypothesis, GraphNode

NODE_IDS = (
    "backup",
    "cache",
    "database",
    "index",
    "model",
    "queue",
    "replica",
    "sink",
)

KNOWN_FAMILIES = (
    "async-etl",
    "backup-restore",
    "cache-warming",
    "index-rebuild",
    "model-rebuild",
    "replica-lag",
)
OOD_FAMILY = "retry-replay"

FAMILY_PATHS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "backup-restore": (
        ("backup", "database", "restore-read"),
        ("database", "sink", "restore-write"),
    ),
    "async-etl": (
        ("backup", "database", "etl-read"),
        ("database", "queue", "etl-enqueue"),
        ("queue", "sink", "etl-load"),
    ),
    "cache-warming": (
        ("backup", "database", "cache-source"),
        ("database", "cache", "cache-warm"),
        ("cache", "sink", "cache-serve"),
    ),
    "index-rebuild": (
        ("backup", "database", "index-source"),
        ("database", "index", "index-build"),
        ("index", "sink", "index-serve"),
    ),
    "model-rebuild": (
        ("backup", "database", "model-source"),
        ("database", "model", "model-train"),
        ("model", "sink", "model-deploy"),
    ),
    "replica-lag": (
        ("backup", "database", "replica-primary"),
        ("database", "replica", "replica-copy"),
        ("replica", "sink", "replica-promote"),
    ),
    "retry-replay": (
        ("backup", "queue", "retry-enqueue"),
        ("queue", "database", "retry-run"),
        ("database", "sink", "retry-commit"),
    ),
}


@dataclass(frozen=True, slots=True)
class GhostGraphTCase:
    case_id: str
    split: str
    truth: GraphHypothesis
    catalogue: tuple[GraphHypothesis, ...]
    expected: str


def experiments() -> tuple[DiscoveryExperiment, ...]:
    items = []
    for family in (*KNOWN_FAMILIES, OOD_FAMILY):
        operations = tuple(sorted(operation for _, _, operation in FAMILY_PATHS[family]))
        items.append(_experiment(f"q-{family}", operations, len(operations)))
    all_operations = tuple(
        sorted(
            {
                operation
                for path in FAMILY_PATHS.values()
                for _, _, operation in path
            }
            | {"delayed-release"}
        )
    )
    items.append(_experiment("q-integrity", all_operations, 8))
    return tuple(sorted(items, key=lambda item: item.experiment_id))


def generate_cases() -> tuple[GhostGraphTCase, ...]:
    known = tuple(
        graph
        for family_index, family in enumerate(KNOWN_FAMILIES)
        for graph in (
            _family_graph(f"catalogue-{family}", family),
            _family_graph(
                f"catalogue-{family}-irrelevant-twin",
                family,
                noise_seed=50_000 + family_index,
            ),
        )
    )
    compositions = tuple(
        _composition_graph(f"catalogue-composition-{left}-{right}", left, right)
        for left, right in combinations(KNOWN_FAMILIES, 2)
    )
    delayed = tuple(
        graph
        for family_index, family in enumerate(KNOWN_FAMILIES)
        for graph in (
            _family_graph(f"catalogue-delayed-{family}", family, delayed=True),
            _family_graph(
                f"catalogue-delayed-{family}-irrelevant-twin",
                family,
                delayed=True,
                noise_seed=60_000 + family_index,
            ),
        )
    )
    cases: list[GhostGraphTCase] = []
    for index in range(120):
        family = KNOWN_FAMILIES[index % len(KNOWN_FAMILIES)]
        cases.append(
            GhostGraphTCase(
                f"instance-{index:03d}",
                "instance-held-out",
                _family_graph(f"truth-instance-{index:03d}", family, noise_seed=10_000 + index),
                known,
                "ACTION_IDENTIFIED",
            )
        )
    pairs = tuple(combinations(KNOWN_FAMILIES, 2))
    for index in range(80):
        left, right = pairs[index % len(pairs)]
        cases.append(
            GhostGraphTCase(
                f"composition-{index:03d}",
                "composition-held-out",
                _composition_graph(
                    f"truth-composition-{index:03d}",
                    left,
                    right,
                    noise_seed=20_000 + index,
                ),
                compositions,
                "ACTION_IDENTIFIED",
            )
        )
    for index in range(50):
        cases.append(
            GhostGraphTCase(
                f"family-ood-{index:03d}",
                "family-held-out",
                _family_graph(
                    f"truth-family-ood-{index:03d}",
                    OOD_FAMILY,
                    noise_seed=30_000 + index,
                ),
                known,
                "OUT_OF_HYPOTHESIS",
            )
        )
    for index in range(50):
        family = KNOWN_FAMILIES[index % len(KNOWN_FAMILIES)]
        cases.append(
            GhostGraphTCase(
                f"temporal-{index:03d}",
                "temporal-shift-held-out",
                _family_graph(
                    f"truth-temporal-{index:03d}",
                    family,
                    delayed=True,
                    noise_seed=40_000 + index,
                ),
                delayed,
                "ACTION_IDENTIFIED",
            )
        )
    return tuple(cases)


def _family_graph(
    graph_id: str,
    family: str,
    *,
    delayed: bool = False,
    noise_seed: int | None = None,
) -> GraphHypothesis:
    path = FAMILY_PATHS[family]
    if delayed:
        path = _delay_path(path)
    edges = list(_path_edges(family, path))
    if noise_seed is not None:
        edges.extend(_noise_edges(path, noise_seed, limit=12 - len(edges)))
    return _graph(graph_id, tuple(edges))


def _composition_graph(
    graph_id: str,
    left: str,
    right: str,
    *,
    noise_seed: int | None = None,
) -> GraphHypothesis:
    left_path = FAMILY_PATHS[left]
    right_path = FAMILY_PATHS[right]
    edges = [*_path_edges(left, left_path), *_path_edges(right, right_path)]
    if noise_seed is not None:
        used_path = (*left_path, *right_path)
        edges.extend(_noise_edges(used_path, noise_seed, limit=12 - len(edges)))
    return _graph(graph_id, tuple(edges))


def _path_edges(
    prefix: str,
    path: tuple[tuple[str, str, str], ...],
) -> tuple[GraphEdge, ...]:
    return tuple(
        GraphEdge(f"{prefix}-{index}", source, target, operation)
        for index, (source, target, operation) in enumerate(path)
    )


def _delay_path(
    path: tuple[tuple[str, str, str], ...],
) -> tuple[tuple[str, str, str], ...]:
    source, target, operation = path[-1]
    used = {node for edge in path for node in edge[:2]}
    middle = next(
        node
        for node in ("queue", "replica", "cache", "index", "model")
        if node not in used
    )
    return (*path[:-1], (source, middle, operation), (middle, target, "delayed-release"))


def _noise_edges(
    paths: tuple[tuple[str, str, str], ...],
    seed: int,
    *,
    limit: int,
) -> tuple[GraphEdge, ...]:
    used = {node for source, target, _ in paths for node in (source, target)}
    unused = tuple(node for node in NODE_IDS if node not in used and node != "sink")
    candidates = tuple(combinations(unused, 2))
    digest = hashlib.sha256(f"ghostgraph-t-noise:{seed}".encode()).digest()
    selected = tuple(
        pair
        for index, pair in enumerate(candidates)
        if digest[index // 8] & (1 << (index % 8))
    )[:limit]
    return tuple(
        GraphEdge(f"noise-{index:02d}", source, target, f"noise-{source}-{target}")
        for index, (source, target) in enumerate(selected)
    )


def _graph(graph_id: str, edges: tuple[GraphEdge, ...]) -> GraphHypothesis:
    return GraphHypothesis(
        graph_id=graph_id,
        nodes=tuple(GraphNode(node_id) for node_id in NODE_IDS),
        edges=tuple(sorted(edges, key=lambda item: item.edge_id)),
        initial_node_ids=("backup",),
        residual_node_ids=("sink",),
    )


def _experiment(
    experiment_id: str,
    operations: tuple[str, ...],
    cost: int,
) -> DiscoveryExperiment:
    return DiscoveryExperiment(
        experiment_id=experiment_id,
        enabled_operation_ids=operations,
        checkpoint_node_ids=("cache", "database", "model", "replica", "sink"),
        time_buckets=3,
        declared_cost=cost,
    )
