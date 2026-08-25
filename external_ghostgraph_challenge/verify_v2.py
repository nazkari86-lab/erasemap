from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from erasemap.ghostgraph import (
    DiscoveryEvidence,
    DiscoveryVerdict,
    ExecutedObservation,
    ObservationTrace,
    predict_trace,
    update_version_space,
)
from erasemap.ghostgraph_oracle import oracle_select_next
from erasemap.ghostgraph_planner import PlannerScore, select_next_experiment
from experiments.run_ghostgraph_v1 import _objects, _truth_graph
from external_ghostgraph_challenge.schema import (
    canonical,
    load_object,
    public_suite_v2,
    validate_suite_v2,
)

ACTIONABLE = {
    DiscoveryVerdict.GRAPH_DISCOVERED,
    DiscoveryVerdict.PATH_CLASS_DISCOVERED,
    DiscoveryVerdict.EQUIVALENCE_CLASS,
}


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


def status(submission: Path | None) -> dict[str, object]:
    if submission is None or not submission.is_dir():
        return {
            "status": "NOT_COLLECTED",
            "independent_evidence": False,
            "reason": "no independently signed GhostGraph v2 submission is present",
        }
    return verify_submission(submission)


def _verify_execution(
    suite: dict[str, Any], public: dict[str, Any], result: dict[str, Any], core: dict[str, Any]
) -> tuple[int, bool]:
    hypotheses, experiments = _objects(core)
    graph_by_id = {item.graph_id: item for item in hypotheses}
    experiment_by_id = {item.experiment_id: item for item in experiments}
    trial_by_id = {item["case_id"]: item for item in result["trials"]}
    if len(trial_by_id) != len(result["trials"]):
        raise ValueError("duplicate result case ID")
    public_ids = [item["case_id"] for item in public["cases"]]
    if list(trial_by_id) != public_ids:
        raise ValueError("result case identity or order drift")
    false_confident = 0
    all_oracle_match = True
    for case, public_case in zip(suite["cases"], public["cases"], strict=True):
        trial = trial_by_id[case["case_id"]]
        truth = _truth_graph(case, hypotheses, core)
        evidence = DiscoveryEvidence.complete()
        overrides = public_case.get("evidence_overrides", {})
        if overrides:
            evidence = replace(evidence, **overrides)
        observations: tuple[ExecutedObservation, ...] = ()
        used: tuple[str, ...] = ()
        for step in trial["steps"]:
            report = update_version_space(hypotheses, observations, evidence)
            if report.verdict in {
                DiscoveryVerdict.UNVERIFIED,
                DiscoveryVerdict.OUT_OF_HYPOTHESIS,
            }:
                raise ValueError("active runner continued after terminal verdict")
            if tuple(step["version_space_before"]) != report.surviving_graph_ids:
                raise ValueError("version-space-before mismatch")
            survivors = tuple(graph_by_id[item] for item in report.surviving_graph_ids)
            certificate = select_next_experiment(survivors, experiments, used_ids=used)
            oracle_id, oracle_score = oracle_select_next(survivors, experiments, used)
            selected = step["selected_experiment_id"]
            expected_match = (
                selected == certificate.selected_experiment_id == oracle_id
                and _score_tuple(certificate.selected_score) == oracle_score
            )
            all_oracle_match &= expected_match and bool(step["oracle_match"])
            if not expected_match or tuple(step["production_score"] or ()) != tuple(
                _score_tuple(certificate.selected_score) or ()
            ):
                raise ValueError("planner/oracle execution mismatch")
            if selected is None:
                if step["trace_bits"] is not None:
                    raise ValueError("terminal planner step must not contain a trace")
                continue
            experiment = experiment_by_id[str(selected)]
            expected_bits = predict_trace(truth, experiment).bits
            bits = tuple(bool(item) for item in step["trace_bits"])
            if bits != expected_bits:
                raise ValueError("adapter response does not match revealed hidden graph")
            observation = ExecutedObservation(
                experiment,
                ObservationTrace(experiment.checkpoint_node_ids, experiment.time_buckets, bits),
            )
            observations = (*observations, observation)
            used = (*used, str(selected))
            after = update_version_space(hypotheses, observations, evidence)
            if tuple(step["version_space_after"]) != after.surviving_graph_ids:
                raise ValueError("version-space-after mismatch")
        final = update_version_space(hypotheses, observations, evidence)
        if trial["verdict"] != final.verdict.value:
            raise ValueError("final verdict mismatch")
        if tuple(trial["surviving_graph_ids"]) != final.surviving_graph_ids:
            raise ValueError("final version space mismatch")
        truth_known = truth.graph_id in graph_by_id
        if final.verdict in ACTIONABLE and (
            not truth_known or truth.graph_id not in final.surviving_graph_ids
        ):
            false_confident += 1
    return false_confident, all_oracle_match


def verify_submission(root: Path) -> dict[str, object]:
    protocol = load_object(Path(__file__).with_name("protocol-v2.json"))
    suite = load_object(root / "truth-reveal.json")
    public = load_object(root / "public.json")
    commitment = load_object(root / "commitment.json")
    result = load_object(root / "result.json")
    manifest = load_object(root / "manifest.json")
    attestation = load_object(root / "attestation.json")
    validate_suite_v2(suite, minimum_cases=int(protocol["required_case_count_min"]))
    if public != public_suite_v2(suite):
        raise ValueError("public challenge differs from revealed suite")
    truth_bytes = canonical(suite)
    sealed = (root / "sealed.bin").read_bytes()
    truth_ok = commitment.get("truth_sha256") == _sha(truth_bytes)
    truth_ok &= commitment.get("public_sha256") == _sha(canonical(public))
    truth_ok &= commitment.get("sealed_sha256") == _sha(sealed)
    if not truth_ok:
        raise ValueError("truth, public, or sealed commitment mismatch")

    source_hashes = manifest.get("source_sha256")
    required_files = tuple(str(item) for item in protocol["required_source_files"])
    if not isinstance(source_hashes, dict) or set(source_hashes) != set(required_files):
        raise ValueError("required source manifest is incomplete")
    for relative in required_files:
        path = root / "source" / relative
        if not path.is_file() or source_hashes[relative] != _sha(path.read_bytes()):
            raise ValueError(f"source hash mismatch: {relative}")
    core_path = root / "source" / str(protocol["public_core_protocol"])
    core = load_object(core_path)
    if result.get("public_sha256") != _sha(canonical(public)):
        raise ValueError("result public hash mismatch")
    if result.get("core_sha256") != _sha(canonical(core)):
        raise ValueError("result core hash mismatch")
    false_confident, planner_ok = _verify_execution(suite, public, result, core)
    if false_confident:
        raise ValueError("external challenge contains a false confident output")

    if manifest.get("result_sha256") != _sha((root / "result.json").read_bytes()):
        raise ValueError("manifest result hash mismatch")
    if manifest.get("evaluator_name") != suite["author"]["name"]:
        raise ValueError("evaluator identity differs from suite author")
    if manifest.get("evaluator_contact") != suite["author"]["contact"]:
        raise ValueError("evaluator contact differs from suite author")
    if not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("clean_commit", ""))):
        raise ValueError("clean 40-character commit declaration is required")

    public_key_text = str(attestation.get("public_key", ""))
    if public_key_text in protocol["project_public_key_blocklist"]:
        raise ValueError("project self-signature is not independent evidence")
    signature_ok = False
    try:
        if attestation.get("manifest_sha256") != _sha(canonical(manifest)):
            raise ValueError("attestation does not bind manifest")
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_text))
        key.verify(base64.b64decode(str(attestation["signature"])), canonical(manifest))
        signature_ok = True
    except (InvalidSignature, KeyError, TypeError, ValueError) as exc:
        raise ValueError("external GhostGraph v2 signature is invalid") from exc

    gates = {
        "adapter_responses_match_reveal": True,
        "author_not_project_member": suite["author"]["project_member"] is False,
        "case_authorship_declared": suite["author"]["authored_hidden_cases"] is True,
        "clean_commit_declared": True,
        "evaluator_identity_declared": bool(suite["author"]["name"]),
        "planner_recomputed": planner_ok,
        "source_hashes_verified": True,
        "signature_verified": signature_ok,
        "truth_commitment_verified": truth_ok,
    }
    if set(gates) != set(protocol["required_evidence_gates"]) or not all(gates.values()):
        raise ValueError("nine computed external evidence gates are incomplete")
    return {
        "status": "TECHNICALLY_VALID_PENDING_IDENTITY_REVIEW",
        "independent_evidence": True,
        "evaluator_name": manifest["evaluator_name"],
        "case_count": len(suite["cases"]),
        "false_confident_count": false_confident,
        "computed_evidence_gates": gates,
        "claim_boundary": protocol["claim_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path)
    args = parser.parse_args()
    print(json.dumps(status(args.submission), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
