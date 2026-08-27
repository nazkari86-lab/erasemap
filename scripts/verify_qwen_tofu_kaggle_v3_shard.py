from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def verify(result: Path, *, expected_fold: int) -> dict[str, Any]:
    protocol_path = ROOT / "benchmark/qwen-tofu-kaggle-v3.json"
    manifest = json.loads((result / "manifest.json").read_text())
    trials_path = result / "development-trials.jsonl"
    trials = [json.loads(line) for line in trials_path.read_text().splitlines()]
    protocol = json.loads(protocol_path.read_text())
    expected_count = (
        len(protocol["development_seeds"])
        * len(protocol["method"]["temperatures"])
        * len(protocol["method"]["keep_weights"])
        * len(protocol["method"]["checkpoint_steps"])
        * len(protocol["method"]["alphas"])
    )
    assert manifest["schema_version"] == "erasemap-qwen-tofu-v3-shard-v1"
    assert manifest["phase"] == "development"
    assert manifest["fold_index"] == expected_fold
    assert manifest["parent_protocol_sha256"] == _sha256(protocol_path)
    assert manifest["development_seeds"] == protocol["development_seeds"]
    assert manifest["scientific_inputs_frozen"] is True
    assert manifest["trial_count"] == expected_count == len(trials)
    assert manifest["trials_sha256"] == _sha256(trials_path)
    assert {row["seed"] for row in trials} == set(protocol["development_seeds"])
    assert {row["block"] for row in trials} == {f"development-{expected_fold}"}
    identities = {
        (
            row["seed"],
            row["temperature"],
            row["keep_weight"],
            row["checkpoint"],
            row["alpha"],
        )
        for row in trials
    }
    assert len(identities) == len(trials)
    return {
        "fold_index": expected_fold,
        "protocol_sha256": manifest["parent_protocol_sha256"],
        "trial_count": len(trials),
        "valid": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path)
    parser.add_argument("--expected-fold", required=True, type=int)
    args = parser.parse_args()
    print(json.dumps(verify(args.result, expected_fold=args.expected_fold), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
