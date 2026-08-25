from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from erasemap.ghostgraph import (
    DiscoveryEvidence,
    DiscoveryVerdict,
    ExecutedObservation,
    ObservationTrace,
    update_version_space,
)
from erasemap.ghostgraph_oracle import oracle_select_next
from erasemap.ghostgraph_planner import PlannerScore, select_next_experiment
from experiments.run_ghostgraph_v1 import _objects
from external_ghostgraph_challenge.schema import canonical, load_object

TraceAdapter = Callable[[str, str], tuple[bool, ...]]


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _score_tuple(score: PlannerScore | None) -> tuple[int, int, int, str] | None:
    if score is None:
        return None
    return (
        int(score.largest_bucket),
        int(score.squared_bucket_sum),
        int(score.declared_cost),
        str(score.experiment_id),
    )


def run_active(
    public: dict[str, Any],
    core_protocol: dict[str, Any],
    execute: TraceAdapter,
) -> dict[str, object]:
    if public.get("schema_version") != "erasemap-external-ghostgraph-public-v2":
        raise ValueError("unsupported external GhostGraph public v2 bundle")
    hypotheses, experiments = _objects(core_protocol)
    graph_by_id = {item.graph_id: item for item in hypotheses}
    experiment_by_id = {item.experiment_id: item for item in experiments}
    trials: list[dict[str, object]] = []
    for case in public["cases"]:
        evidence = DiscoveryEvidence.complete()
        overrides = case.get("evidence_overrides", {})
        if overrides:
            evidence = replace(evidence, **overrides)
        observations: tuple[ExecutedObservation, ...] = ()
        used: tuple[str, ...] = ()
        steps: list[dict[str, object]] = []
        while True:
            report = update_version_space(hypotheses, observations, evidence)
            if report.verdict in {
                DiscoveryVerdict.UNVERIFIED,
                DiscoveryVerdict.OUT_OF_HYPOTHESIS,
            }:
                break
            survivors = tuple(graph_by_id[item] for item in report.surviving_graph_ids)
            certificate = select_next_experiment(survivors, experiments, used_ids=used)
            oracle_id, oracle_score = oracle_select_next(survivors, experiments, used)
            selected = certificate.selected_experiment_id
            production_score = _score_tuple(certificate.selected_score)
            if selected is None:
                steps.append(
                    {
                        "version_space_before": report.surviving_graph_ids,
                        "selected_experiment_id": None,
                        "production_score": None,
                        "oracle_experiment_id": oracle_id,
                        "oracle_score": oracle_score,
                        "oracle_match": oracle_id is None and oracle_score is None,
                        "trace_bits": None,
                        "version_space_after": report.surviving_graph_ids,
                    }
                )
                break
            experiment = experiment_by_id[selected]
            bits = tuple(bool(item) for item in execute(str(case["case_id"]), selected))
            observation = ExecutedObservation(
                experiment,
                ObservationTrace(
                    experiment.checkpoint_node_ids,
                    experiment.time_buckets,
                    bits,
                ),
            )
            observations = (*observations, observation)
            used = (*used, selected)
            after = update_version_space(hypotheses, observations, evidence)
            steps.append(
                {
                    "version_space_before": report.surviving_graph_ids,
                    "selected_experiment_id": selected,
                    "production_score": production_score,
                    "oracle_experiment_id": oracle_id,
                    "oracle_score": oracle_score,
                    "oracle_match": selected == oracle_id and production_score == oracle_score,
                    "trace_bits": bits,
                    "version_space_after": after.surviving_graph_ids,
                }
            )
        final = update_version_space(hypotheses, observations, evidence)
        trials.append(
            {
                "case_id": case["case_id"],
                "kind": case["kind"],
                "steps": steps,
                "verdict": final.verdict.value,
                "surviving_graph_ids": final.surviving_graph_ids,
            }
        )
    return {
        "schema_version": "erasemap-external-ghostgraph-run-v2",
        "public_sha256": _sha(canonical(public)),
        "core_sha256": _sha(canonical(core_protocol)),
        "trials": trials,
    }


def _http_adapter(url: str) -> TraceAdapter:
    def execute(case_id: str, experiment_id: str) -> tuple[bool, ...]:
        request = urllib.request.Request(
            url,
            data=canonical({"case_id": case_id, "experiment_id": experiment_id}),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read())
        if not isinstance(payload, dict) or not isinstance(payload.get("trace_bits"), list):
            raise ValueError("evaluator adapter returned an invalid trace")
        return tuple(bool(item) for item in payload["trace_bits"])

    return execute


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--core-protocol", type=Path, required=True)
    parser.add_argument("--adapter-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"output already exists: {args.output}")
    result = run_active(
        load_object(args.public),
        load_object(args.core_protocol),
        _http_adapter(args.adapter_url),
    )
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
