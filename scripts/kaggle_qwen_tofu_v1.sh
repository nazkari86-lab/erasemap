#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
kernel_slug="erasemap-qwen-tofu-v1"
action="${1:-status}"
credential_file="${KAGGLE_CONFIG_DIR:-$HOME/.kaggle}/kaggle.json"

if [[ ! -f "$credential_file" ]]; then
  echo "Kaggle credentials are absent: $credential_file" >&2
  echo "Create a fresh legacy API token in Kaggle Settings and place kaggle.json there." >&2
  exit 2
fi

kaggle_username="$(jq -r '.username // empty' "$credential_file")"
if [[ -z "$kaggle_username" ]]; then
  echo "Kaggle username is empty in $credential_file." >&2
  echo "Replace it with a fresh kaggle.json from Kaggle Settings > API > Create Legacy API Key." >&2
  exit 2
fi
kernel_id="$kaggle_username/$kernel_slug"

if [[ "$action" == "status" ]]; then
  kaggle kernels status "$kernel_id"
  exit 0
fi

if [[ "$action" == "submit" ]]; then
  kernel_temp="$(mktemp -d "${TMPDIR:-/tmp}/erasemap-kaggle.XXXXXX")"
  cleanup_kernel_temp() {
    if [[ -d "$kernel_temp" ]]; then
      find "$kernel_temp" -depth -delete
    fi
  }
  trap cleanup_kernel_temp EXIT
  jq --arg username "$kaggle_username" \
    '.id = ($username + "/erasemap-qwen-tofu-v1")' \
    "$project_root/kaggle/qwen-tofu-v1/kernel-metadata.template.json" \
    > "$kernel_temp/kernel-metadata.json"
  cp "$project_root/kaggle/qwen-tofu-v1/run.py" "$kernel_temp/run.py"
  kaggle kernels push -p "$kernel_temp"
  echo "Submitted $kernel_id"
  exit 0
fi

if [[ "$action" == "collect" ]]; then
  destination="$project_root/outputs/qwen-tofu-kaggle-v1"
  if [[ -e "$destination" ]]; then
    echo "Refusing to overwrite existing result: $destination" >&2
    exit 2
  fi
  download_temp="$(mktemp -d "${TMPDIR:-/tmp}/erasemap-kaggle-output.XXXXXX")"
  cleanup_download_temp() {
    if [[ -d "$download_temp" ]]; then
      find "$download_temp" -depth -delete
    fi
  }
  trap cleanup_download_temp EXIT
  kaggle kernels output "$kernel_id" -p "$download_temp"
  source_result="$download_temp/qwen-tofu-v1"
  if [[ ! -f "$source_result/summary.json" ]]; then
    echo "Completed output does not contain qwen-tofu-v1/summary.json" >&2
    exit 1
  fi
  mkdir -p "$destination"
  cp -R "$source_result/." "$destination/"
  PYTHONPATH="$project_root/src:$project_root" \
    "$project_root/.venv/bin/python" "$project_root/scripts/verify_qwen_tofu_kaggle_v1.py" \
    --protocol "$project_root/benchmark/qwen-tofu-kaggle-v1.json" \
    --result "$destination"
  exit 0
fi

echo "Unknown action: $action (expected submit, status, or collect)" >&2
exit 2
