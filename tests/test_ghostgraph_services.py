from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from experiments import ghostgraph_services as module
from experiments.ghostgraph_services import (
    GhostGraphServices,
    NativeObservation,
    require_image,
    require_name,
)
from experiments.run_ghostgraph_v1 import _objects


def _images() -> dict[str, str]:
    return {
        key: str(value)
        for key, value in json.loads(
            Path("benchmark/ghostgraph-live-v2.json").read_text()
        )["images"].items()
    }


def test_rejects_mutable_images_and_unrelated_container_names() -> None:
    with pytest.raises(ValueError, match="pinned"):
        require_image("redis:latest")
    with pytest.raises(ValueError, match="non-GhostGraph"):
        require_name("postgres-production")


def test_docker_start_is_loopback_digest_pinned_and_namespaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []

    def fake_run(
        args: list[str], *, check: bool = True, timeout: int = 120
    ) -> subprocess.CompletedProcess[str]:
        commands.append(args)
        return subprocess.CompletedProcess(args, 0, "container\n", "")

    monkeypatch.setattr(module, "run_command", fake_run)
    services = GhostGraphServices(_images(), tmp_path)
    services._docker_run("source", 6379, args=())

    command = commands[0]
    assert command[:3] == ["docker", "run", "--detach"]
    assert any(item.startswith("127.0.0.1:") for item in command)
    assert services.names["source"].startswith("erasemap-ghostgraph-source-")
    assert "@sha256:" in services.images["source"]


class MemoryServices(GhostGraphServices):
    def __init__(self) -> None:
        self.state: dict[str, set[str]] = {
            "identity": set(),
            "lineage": set(),
            "source": set(),
            "vector": set(),
        }

    def put(self, node: str, subject: str) -> None:
        self.state[node].add(subject)

    def has(self, node: str, subject: str) -> NativeObservation:
        return NativeObservation(node, "sha256:test", subject in self.state[node])


def test_memory_service_trace_matches_three_hop_live_graph() -> None:
    protocol = json.loads(Path("benchmark/ghostgraph-live-v2.json").read_text())
    graphs, experiments = _objects(protocol)
    graph = next(item for item in graphs if item.graph_id == "g-live-multi")
    experiment = next(item for item in experiments if item.experiment_id == "q-multi")
    services = MemoryServices()

    bits, observations = services.execute_trace(graph, experiment, "target")

    assert bits == (
        True, False, True, False,
        True, True, True, False,
        True, True, True, True,
    )
    assert tuple(item.present for item in observations) == bits
