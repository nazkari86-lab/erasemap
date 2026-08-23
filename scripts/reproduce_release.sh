#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

python_bin="${ERASEMAP_PYTHON:-$project_root/.venv/bin/python}"
profile="${1:-core}"
release_temp="$(mktemp -d "${TMPDIR:-/tmp}/erasemap-release.XXXXXX")"
initial_status="$(git status --porcelain=v1 --untracked-files=all)"
trap 'rm -rf "$release_temp"' EXIT

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

"$python_bin" -m ruff check .
"$python_bin" -m pip check
"$python_bin" scripts/verify_ci_environment.py
"$python_bin" -m mypy --strict \
  src pilot external_challenge external_temporal_challenge
"$python_bin" -m pytest \
  --cov=erasemap --cov=external_challenge --cov=external_temporal_challenge --cov=pilot \
  --cov-report=term --cov-fail-under=90
PYTHONPATH=src "$python_bin" experiments/run_manual_pipeline_benchmark.py \
  --output "$release_temp/manual-pipelines.json"
"$python_bin" -m build --outdir "$release_temp/dist"
"$python_bin" scripts/verify_source_locked_holdout.py
"$python_bin" scripts/verify_external_freeze.py
"$python_bin" scripts/verify_sequential_deletion_privacy_v1.py
PYTHONPATH=src "$python_bin" scripts/verify_measured_multiservice_v1.py
"$python_bin" scripts/verify_regeneration_safe_erasure_v1.py
PYTHONPATH=src "$python_bin" experiments/run_regeneration_safe_erasure_v1.py \
  --output "$release_temp/rse-v1"
"$python_bin" scripts/verify_regeneration_safe_erasure_v1.py \
  --result "$release_temp/rse-v1/result.json"
"$python_bin" scripts/verify_regeneration_safe_erasure_v2.py
PYTHONPATH=src "$python_bin" experiments/run_regeneration_safe_erasure_v2.py \
  --output "$release_temp/rse-v2"
"$python_bin" scripts/verify_regeneration_safe_erasure_v2.py \
  --result "$release_temp/rse-v2/result.json"
"$python_bin" scripts/verify_formal_conformance.py \
  --expected formal/conformance-v1.json \
  --output "$release_temp/formal-conformance.json"
"$python_bin" scripts/verify_rse_conformance.py \
  --expected formal/rse-msc-conformance-v1.json \
  --output "$release_temp/rse-msc-conformance.json"
lake build --wfail
PYTHONPATH=src "$python_bin" experiments/run_pcug_mechanism_stress.py \
  --output "$release_temp/pcug-stress.json"
PYTHONPATH=src "$python_bin" external_evaluator/run.py \
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
if [[ "$profile" != "face-open" ]]; then
  echo "Unknown profile: $profile (expected core or face-open)" >&2
  exit 2
fi

PYTHONPATH=src "$python_bin" experiments/prepare_face_assets.py
PYTHONPATH=src "$python_bin" experiments/advanced_face_unlearning.py \
  --dataset olivetti --protocol benchmark/advanced-face-unlearning-v1.json \
  --output outputs/advanced-face-unlearning-v1
PYTHONPATH=src "$python_bin" experiments/advanced_face_unlearning.py \
  --dataset lfw --protocol benchmark/lfw-holdout-v1.json \
  --output outputs/lfw-holdout-v1
PYTHONPATH=src "$python_bin" experiments/run_egov_pilot_simulator.py \
  --output "$release_temp/egov-pilot"
PYTHONPATH=src "$python_bin" experiments/task_agnostic_unlearning_v2.py \
  --protocol benchmark/task-agnostic-v3.json --split development \
  --output outputs/task-agnostic-v3-development
PYTHONPATH=src "$python_bin" experiments/task_agnostic_unlearning_v2.py \
  --protocol benchmark/task-agnostic-v3.json --split evaluation \
  --output outputs/task-agnostic-v3-evaluation
PYTHONPATH=src "$python_bin" experiments/trainable_pixel_backbone.py \
  --output outputs/trainable-pixel-backbone-v1
assert_worktree_unchanged
