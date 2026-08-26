from __future__ import annotations

import hashlib
import json
from pathlib import Path

V2_PATH = Path("benchmark/qwen-tofu-kaggle-v2.json")
V3_PATH = Path("benchmark/qwen-tofu-kaggle-v3.json")


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text())
    assert isinstance(value, dict)
    return value


def test_v3_keeps_all_v2_primary_gates_and_pins() -> None:
    v2 = _load(V2_PATH)
    v3 = _load(V3_PATH)
    assert v3["success_criteria"] == v2["success_criteria"]
    assert v3["model"] == v2["model"]
    assert v3["training"] == v2["training"]
    assert v3["evaluation"] == v2["evaluation"]
    assert v3["dataset"]["repository"] == v2["dataset"]["repository"]  # type: ignore[index]
    assert v3["dataset"]["revision"] == v2["dataset"]["revision"]  # type: ignore[index]


def test_v3_freezes_disjoint_author_blocks_and_real_commitments() -> None:
    protocol = _load(V3_PATH)
    blocks = protocol["author_blocks"]
    assert isinstance(blocks, dict)
    assert blocks["development_pairs"] == [[0, 1], [2, 3], [4, 5], [6, 7], [8, 9]]
    assert blocks["primary_confirmation"] == [10, 11]
    assert blocks["replication_confirmation"] == [12, 13]
    assert blocks["future_reserve"] == [14, 15, 16, 17, 18, 19]
    development = {
        author for pair in blocks["development_pairs"] for author in pair
    }
    used = {
        *development,
        *blocks["primary_confirmation"],
        *blocks["replication_confirmation"],
    }
    assert used.isdisjoint(blocks["future_reserve"])
    commitments = blocks["commitments"]
    assert isinstance(commitments, list)
    assert len(commitments) == 20
    assert len(set(commitments)) == 20
    assert all(
        isinstance(value, str) and value.startswith("sha256:") and len(value) == 71
        for value in commitments
    )


def test_v3_freezes_robust_selection_and_confirmation_blindness() -> None:
    protocol = _load(V3_PATH)
    assert protocol["status"] == "FROZEN_BEFORE_FIRST_V3_GPU_RUN"
    method = protocol["method"]
    assert isinstance(method, dict)
    assert method["minimum_contiguous_feasible_alphas"] == 3
    assert method["checkpoint_steps"] == [20, 40, 60, 80, 100, 120]
    assert method["alphas"] == [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.65, 0.8, 1.0]
    assert len(protocol["development_seeds"]) == 2  # type: ignore[arg-type]
    assert len(protocol["confirmation_seeds"]) == 5  # type: ignore[arg-type]
    assert set(protocol["development_seeds"]).isdisjoint(protocol["confirmation_seeds"])  # type: ignore[arg-type]
    assert protocol["selection_uses_confirmation"] is False
    assert "result" not in protocol


def test_v3_source_hashes_and_protocol_are_canonical() -> None:
    protocol = _load(V3_PATH)
    sources = protocol["author_blocks"]  # type: ignore[index]
    assert isinstance(sources, dict)
    source_hashes = sources["source_sha256"]
    assert source_hashes == {
        "forget10": "sha256:0044c8c2e70a38be93f62ec6cb1c1cc2a1f55a8df2fb549a4da2da8dde9d92f6",
        "forget10_perturbed": (
            "sha256:6fbcb946c57ea1d7b2124cea0e61bf3b5409d1bc10d02368f090109450ed73c7"
        ),
    }
    raw = V3_PATH.read_bytes()
    assert raw.endswith(b"\n")
    assert hashlib.sha256(raw).hexdigest()
