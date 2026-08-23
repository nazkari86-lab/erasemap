#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
export PYTHONPATH="$project_root/src:$project_root${PYTHONPATH:+:$PYTHONPATH}"

python_bin="${ERASEMAP_PYTHON:-$project_root/.venv/bin/python}"
profile="${1:-core}"
release_temp="$(mktemp -d "${TMPDIR:-/tmp}/erasemap-release.XXXXXX")"
initial_status="$(git status --porcelain=v1 --untracked-files=all)"

cleanup_release_temp() {
  if [[ -d "$release_temp" ]]; then
    find "$release_temp" -depth -delete
  fi
}

trap cleanup_release_temp EXIT

assert_worktree_unchanged() {
  local final_status
  final_status="$(git status --porcelain=v1 --untracked-files=all)"
  if [[ "$final_status" != "$initial_status" ]]; then
    echo "Release reproduction changed the worktree." >&2
    git status --short >&2
    exit 1
  fi
}

if [[ ! -x "$python_bin" ]]; then
  echo "Python environment not found: $python_bin" >&2
  echo "Create .venv and install the required extras first." >&2
  exit 2
fi

python_minor="$($python_bin -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
case "$python_minor" in
  3.11) environment_constraints="constraints/ci-py311.txt" ;;
  3.14) environment_constraints="constraints/local-py314.txt" ;;
  *)
    echo "No frozen release environment for Python $python_minor." >&2
    echo "Use Python 3.11 or 3.14 for evidence reproduction." >&2
    exit 2
    ;;
esac

"$python_bin" -m ruff check .
"$python_bin" -m pip check
"$python_bin" scripts/verify_ci_environment.py --constraints "$environment_constraints"
"$python_bin" -m mypy --strict \
  src pilot external_challenge external_temporal_challenge external_transfer \
  external_ghostgraph_challenge usability
"$python_bin" -m pytest \
  --cov=erasemap --cov=external_challenge --cov=external_temporal_challenge --cov=pilot \
  --cov-report=term --cov-fail-under=90
"$python_bin" experiments/run_manual_pipeline_benchmark.py \
  --output "$release_temp/manual-pipelines.json"
"$python_bin" -m build --outdir "$release_temp/dist"
"$python_bin" scripts/verify_source_locked_holdout.py
"$python_bin" scripts/verify_external_freeze.py
"$python_bin" scripts/verify_sequential_deletion_privacy_v1.py
"$python_bin" scripts/verify_open_transfer_v1.py
"$python_bin" -m usability.verify
"$python_bin" scripts/verify_measured_multiservice_v1.py
"$python_bin" scripts/verify_regeneration_safe_erasure_v1.py
"$python_bin" experiments/run_regeneration_safe_erasure_v1.py \
  --output "$release_temp/rse-v1"
"$python_bin" scripts/verify_regeneration_safe_erasure_v1.py \
  --result "$release_temp/rse-v1/result.json"
"$python_bin" scripts/verify_regeneration_safe_erasure_v2.py
"$python_bin" experiments/run_regeneration_safe_erasure_v2.py \
  --output "$release_temp/rse-v2"
"$python_bin" scripts/verify_regeneration_safe_erasure_v2.py \
  --result "$release_temp/rse-v2/result.json"
"$python_bin" scripts/verify_topology_robust_erasure_v1.py
"$python_bin" experiments/run_topology_robust_erasure_v1.py \
  --output "$release_temp/tre-v1"
"$python_bin" scripts/verify_topology_robust_erasure_v1.py \
  --result "$release_temp/tre-v1/result.json"
"$python_bin" scripts/verify_erasure_tomography_v1.py
"$python_bin" experiments/run_erasure_tomography_v1.py \
  --protocol benchmark/erasure-tomography-v1.json \
  --reveal benchmark/erasure-tomography-v1-reveal.json \
  --output "$release_temp/erasure-tomography-v1"
"$python_bin" scripts/verify_erasure_tomography_v1.py \
  --result "$release_temp/erasure-tomography-v1/result.json"
"$python_bin" scripts/verify_erasure_tomography_redis_v1.py
"$python_bin" scripts/verify_ghostgraph_v1.py
"$python_bin" experiments/run_ghostgraph_v1.py \
  --protocol benchmark/ghostgraph-v1.json \
  --reveal benchmark/ghostgraph-v1-reveal.json \
  --output "$release_temp/ghostgraph-v1"
"$python_bin" scripts/verify_ghostgraph_v1.py \
  --output "$release_temp/ghostgraph-v1"
"$python_bin" -m external_ghostgraph_challenge.verify
"$python_bin" scripts/verify_formal_conformance.py \
  --expected formal/conformance-v1.json \
  --output "$release_temp/formal-conformance.json"
"$python_bin" scripts/verify_rse_conformance.py \
  --expected formal/rse-msc-conformance-v1.json \
  --output "$release_temp/rse-msc-conformance.json"
"$python_bin" scripts/verify_tre_conformance.py \
  --expected formal/tre-conformance-v1.json \
  --output "$release_temp/tre-conformance.json"
"$python_bin" scripts/verify_erasure_tomography_conformance.py \
  --expected formal/erasure-tomography-conformance-v1.json \
  --output "$release_temp/erasure-tomography-conformance.json"
"$python_bin" scripts/verify_ghostgraph_conformance.py \
  --expected formal/ghostgraph-conformance-v1.json \
  --output "$release_temp/ghostgraph-conformance.json"
lake build --wfail
"$python_bin" experiments/run_pcug_mechanism_stress.py \
  --output "$release_temp/pcug-stress.json"
"$python_bin" external_evaluator/run.py \
  --sources benchmark/external-sources-v1.json \
  --output "$release_temp/external-evaluator"
"$python_bin" external_evaluator/verify.py \
  "$release_temp/external-evaluator/evaluation-records.json"
"$python_bin" -m erasemap.cli pcug benchmark development \
  --protocol benchmark/pcug-protocol-v1.json \
  --output "$release_temp/pcug-development"
"$python_bin" -m erasemap.cli pcug verify-directory \
  "$release_temp/pcug-development/bundles" \
  --public-key "$release_temp/pcug-development/public-key.pem"

if [[ "$profile" == "core" ]]; then
  assert_worktree_unchanged
  exit 0
fi
if [[ "$profile" == "tomography-redis-live" ]]; then
  "$python_bin" experiments/run_erasure_tomography_redis_v1.py \
    --protocol benchmark/erasure-tomography-redis-v1.json \
    --output "$release_temp/erasure-tomography-redis-v1"
  "$python_bin" scripts/verify_erasure_tomography_redis_v1.py \
    --result "$release_temp/erasure-tomography-redis-v1/result.json"
  assert_worktree_unchanged
  exit 0
fi
if [[ "$profile" == "transfer-live" ]]; then
  "$python_bin" experiments/run_open_transfer_v1.py \
    --protocol benchmark/open-transfer-v1.json \
    --output "$release_temp/open-transfer-v1"
  "$python_bin" scripts/verify_open_transfer_v1.py \
    --result "$release_temp/open-transfer-v1/result.json"
  assert_worktree_unchanged
  exit 0
fi
if [[ "$profile" != "face-open" ]]; then
  echo "Unknown profile: $profile (expected core, tomography-redis-live, transfer-live, or face-open)" >&2
  exit 2
fi

"$python_bin" experiments/prepare_face_assets.py
"$python_bin" experiments/advanced_face_unlearning.py \
  --dataset olivetti --protocol benchmark/advanced-face-unlearning-v1.json \
  --output outputs/advanced-face-unlearning-v1
"$python_bin" experiments/advanced_face_unlearning.py \
  --dataset lfw --protocol benchmark/lfw-holdout-v1.json \
  --output outputs/lfw-holdout-v1
"$python_bin" experiments/run_egov_pilot_simulator.py \
  --output "$release_temp/egov-pilot"
"$python_bin" experiments/task_agnostic_unlearning_v2.py \
  --protocol benchmark/task-agnostic-v3.json --split development \
  --output outputs/task-agnostic-v3-development
"$python_bin" experiments/task_agnostic_unlearning_v2.py \
  --protocol benchmark/task-agnostic-v3.json --split evaluation \
  --output outputs/task-agnostic-v3-evaluation
"$python_bin" experiments/trainable_pixel_backbone.py \
  --output outputs/trainable-pixel-backbone-v1
assert_worktree_unchanged
