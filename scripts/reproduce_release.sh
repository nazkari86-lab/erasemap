#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

python_bin="${ERASEMAP_PYTHON:-$project_root/.venv/bin/python}"
profile="${1:-core}"
release_temp="$(mktemp -d "${TMPDIR:-/tmp}/erasemap-release.XXXXXX")"

if [[ ! -x "$python_bin" ]]; then
  echo "Python environment not found: $python_bin" >&2
  echo "Create .venv and install the required extras first." >&2
  exit 2
fi

"$python_bin" -m ruff check .
"$python_bin" -m mypy src/erasemap
"$python_bin" -m pytest --cov=erasemap --cov-report=term --cov-fail-under=90
PYTHONPATH=src "$python_bin" experiments/run_manual_pipeline_benchmark.py \
  --output outputs/release-v3/manual-pipelines.json
PYTHONPATH=src "$python_bin" experiments/run_egov_pilot_simulator.py \
  --output "$release_temp/egov-pilot"

if [[ "$profile" == "core" ]]; then
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
PYTHONPATH=src "$python_bin" experiments/task_agnostic_unlearning_v2.py \
  --protocol benchmark/task-agnostic-v3.json --split development \
  --output outputs/task-agnostic-v3-development
PYTHONPATH=src "$python_bin" experiments/task_agnostic_unlearning_v2.py \
  --protocol benchmark/task-agnostic-v3.json --split evaluation \
  --output outputs/task-agnostic-v3-evaluation
PYTHONPATH=src "$python_bin" experiments/trainable_pixel_backbone.py \
  --output outputs/trainable-pixel-backbone-v1
