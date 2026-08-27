from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.verify_qwen_tofu_kaggle_v3_shard import verify

ROOT = Path(__file__).resolve().parents[1]


def test_shard_plan_preserves_parent_protocol() -> None:
    plan = json.loads((ROOT / "benchmark/qwen-tofu-kaggle-v3-shards.json").read_text())
    protocol = ROOT / plan["parent_protocol"]
    digest = "sha256:" + hashlib.sha256(protocol.read_bytes()).hexdigest()
    assert plan["scientific_change"] is False
    assert plan["parent_protocol_sha256"] == digest
    assert [row["fold"] for row in plan["development_shards"]] == list(range(5))


def test_shard_verifier_rejects_incomplete_result(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text("{}")
    (tmp_path / "development-trials.jsonl").write_text("")
    try:
        verify(tmp_path, expected_fold=0)
    except (AssertionError, KeyError):
        pass
    else:
        raise AssertionError("incomplete shard must be rejected")
