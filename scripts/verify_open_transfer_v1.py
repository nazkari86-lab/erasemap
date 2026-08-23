from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, cast

from erasemap.open_transfer import summarize_transfer, transfer_record_from_payload
from erasemap.open_transfer_evidence import canonical_json, sha256_file
from experiments.run_open_transfer_v1 import core_sha256


def _load_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact is not an object: {path}")
    return cast(dict[str, Any], payload)


def verify_result(
    result_path: Path,
    *,
    protocol_path: Path = Path("benchmark/open-transfer-v1.json"),
) -> dict[str, Any]:
    root = result_path.parent
    result = _load_object(result_path)
    provenance = _load_object(root / "PROVENANCE.json")
    protocol = _load_object(protocol_path)
    if result.get("schema_version") != "erasemap-open-transfer-result-v1":
        raise ValueError("unexpected open-transfer result schema")
    if provenance.get("schema_version") != "erasemap-open-transfer-provenance-v1":
        raise ValueError("unexpected open-transfer provenance schema")
    protocol_hash = sha256_file(protocol_path)
    if result.get("protocol_sha256") != protocol_hash:
        raise ValueError("protocol hash mismatch")
    if provenance.get("protocol_sha256") != protocol_hash:
        raise ValueError("provenance protocol hash mismatch")
    selected_core_hash = core_sha256(protocol)
    if result.get("core_sha256") != selected_core_hash:
        raise ValueError("core hash mismatch")
    if provenance.get("core_sha256") != selected_core_hash:
        raise ValueError("provenance core hash mismatch")

    artifacts_raw = provenance.get("artifacts")
    if not isinstance(artifacts_raw, dict):
        raise ValueError("provenance artifact manifest is missing")
    artifacts = cast(dict[str, Any], artifacts_raw)
    for relative, expected_hash in artifacts.items():
        path = root / relative
        if not path.is_file() or sha256_file(path) != expected_hash:
            raise ValueError(f"artifact hash mismatch: {relative}")
    expected_files = set(artifacts) | {"PROVENANCE.json"}
    observed_files = {
        str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()
    }
    unexpected = sorted(observed_files - expected_files)
    if unexpected:
        raise ValueError(f"unexpected result artifact: {unexpected[0]}")
    missing = sorted(expected_files - observed_files)
    if missing:
        raise ValueError(f"missing result artifact: {missing[0]}")

    trials_path = root / "trials.jsonl"
    try:
        trial_payloads = [json.loads(line) for line in trials_path.read_text().splitlines()]
    except json.JSONDecodeError as exc:
        raise ValueError("invalid transfer trials JSONL") from exc
    if not all(isinstance(item, dict) for item in trial_payloads):
        raise ValueError("transfer trial must be an object")
    records = tuple(
        transfer_record_from_payload(cast(dict[str, Any], item)) for item in trial_payloads
    )
    summary = summarize_transfer(records, protocol, selected_core_hash)
    if canonical_json(result.get("summary")) != canonical_json(summary.payload()):
        raise ValueError("recorded summary does not match recomputed trials")
    passed = summary.decision == "PASS"
    return {
        "passed": passed,
        "case_count": summary.case_count,
        "family_count": summary.family_count,
        "erasemap_false_complete_count": summary.erasemap_false_complete_count,
        "post_control_recurrence_count": summary.post_control_recurrence_count,
        "oracle_mismatch_count": summary.oracle_mismatch_count,
        "core_diff_count": summary.core_diff_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--result", type=Path, default=Path("outputs/open-transfer-v1/result.json")
    )
    parser.add_argument("--protocol", type=Path, default=Path("benchmark/open-transfer-v1.json"))
    args = parser.parse_args()
    result = verify_result(args.result, protocol_path=args.protocol)
    print(canonical_json(result).decode())
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
