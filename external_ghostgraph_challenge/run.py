from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from erasemap.ghostgraph import (
    DiscoveryEvidence,
    ExecutedObservation,
    ObservationTrace,
    update_version_space,
)
from erasemap.ghostgraph_oracle import oracle_verdict
from experiments.run_ghostgraph_v1 import _objects
from external_ghostgraph_challenge.schema import canonical, load_object


def run_public(public: dict[str, Any], core_protocol: dict[str, Any]) -> dict[str, object]:
    hypotheses, experiments = _objects(core_protocol)
    experiment_by_id = {item.experiment_id: item for item in experiments}
    trials = []
    for case in public["cases"]:
        raw_evidence = case.get("evidence", {})
        evidence = DiscoveryEvidence.complete()
        if raw_evidence:
            evidence = replace(evidence, **raw_evidence)
        observations = tuple(
            ExecutedObservation(
                experiment_by_id[str(item["experiment_id"])],
                ObservationTrace(
                    experiment_by_id[str(item["experiment_id"])].checkpoint_node_ids,
                    experiment_by_id[str(item["experiment_id"])].time_buckets,
                    tuple(bool(bit) for bit in item["trace_bits"]),
                ),
            )
            for item in case["observations"]
        )
        report = update_version_space(hypotheses, observations, evidence)
        trials.append(
            {
                "case_id": case["case_id"],
                "kind": case["kind"],
                "verdict": report.verdict.value,
                "surviving_graph_ids": report.surviving_graph_ids,
                "oracle_match": report.verdict.value
                == oracle_verdict(hypotheses, observations, evidence.trace_error_budget),
            }
        )
    return {
        "schema_version": "erasemap-external-ghostgraph-run-v1",
        "public_sha256": "sha256:" + hashlib.sha256(canonical(public)).hexdigest(),
        "core_sha256": core_protocol["core_sha256"],
        "trials": trials,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--core-protocol", type=Path, default=Path("benchmark/ghostgraph-v1.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"output already exists: {args.output}")
    result = run_public(load_object(args.public), load_object(args.core_protocol))
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
