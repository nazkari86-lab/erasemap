#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
kernel_slug="erasemap-qwen-tofu-v2"
source_slug="erasemap-qwen-tofu-v2-source"
action="${1:-status}"
credential_dir="${KAGGLE_CONFIG_DIR:-$HOME/.kaggle}"
credential_file="$credential_dir/kaggle.json"
access_token_file="$credential_dir/access_token"

if [[ -z "${KAGGLE_API_TOKEN:-}" && -s "$access_token_file" ]]; then
  KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$access_token_file")"
  export KAGGLE_API_TOKEN
fi

if [[ -z "${KAGGLE_API_TOKEN:-}" && ! -f "$credential_file" ]]; then
  echo "Kaggle credentials are absent in $credential_dir." >&2
  exit 2
fi

kaggle_username="${KAGGLE_USERNAME:-}"
if [[ -z "$kaggle_username" && -f "$credential_file" ]]; then
  kaggle_username="$(jq -r '.username // empty' "$credential_file")"
fi
if [[ -z "$kaggle_username" ]]; then
  echo "Kaggle username is not configured." >&2
  exit 2
fi

kernel_id="$kaggle_username/$kernel_slug"
source_id="$kaggle_username/$source_slug"

if [[ "$action" == "status" ]]; then
  kaggle kernels status "$kernel_id"
  exit 0
fi

if [[ "$action" == "submit" ]]; then
  if [[ -n "$(git -C "$project_root" status --porcelain)" ]]; then
    echo "Refusing to freeze v2 from a dirty worktree." >&2
    exit 2
  fi
  revision="$(git -C "$project_root" rev-parse HEAD)"
  source_temp="$(mktemp -d "${TMPDIR:-/tmp}/erasemap-kaggle-v2-source.XXXXXX")"
  kernel_temp="$(mktemp -d "${TMPDIR:-/tmp}/erasemap-kaggle-v2-kernel.XXXXXX")"
  cleanup_submit_temp() {
    for directory in "$source_temp" "$kernel_temp"; do
      if [[ -d "$directory" ]]; then
        find "$directory" -depth -delete
      fi
    done
  }
  trap cleanup_submit_temp EXIT
  mkdir -p "$source_temp/erasemap-source"
  git -C "$project_root" archive HEAD | tar -x -C "$source_temp/erasemap-source"
  printf '%s\n' "$revision" > "$source_temp/ERASEMAP_CODE_REVISION"
  jq -n \
    --arg id "$source_id" \
    '{title:"EraSeMap Qwen TOFU v2 source",id:$id,licenses:[{name:"MIT"}]}' \
    > "$source_temp/dataset-metadata.json"
  if kaggle datasets files "$source_id" --page-size 1 >/dev/null 2>&1; then
    kaggle datasets version -p "$source_temp" -m "Frozen source $revision" --dir-mode zip
  else
    kaggle datasets create -p "$source_temp" --dir-mode zip
  fi
  jq --arg username "$kaggle_username" \
    '.id = ($username + "/erasemap-qwen-tofu-v2")
     | .dataset_sources = ["hijima/erasemap-qwen-tofu-v1-assets", ($username + "/erasemap-qwen-tofu-v2-source")]' \
    "$project_root/kaggle/qwen-tofu-v2/kernel-metadata.template.json" \
    > "$kernel_temp/kernel-metadata.json"
  cp "$project_root/kaggle/qwen-tofu-v2/run.py" "$kernel_temp/run.py"
  kaggle kernels push -p "$kernel_temp"
  echo "Submitted $kernel_id from $revision"
  exit 0
fi

if [[ "$action" == "collect" ]]; then
  destination="$project_root/outputs/qwen-tofu-kaggle-v2"
  if [[ -e "$destination" ]]; then
    echo "Refusing to overwrite existing result: $destination" >&2
    exit 2
  fi
  download_temp="$(mktemp -d "${TMPDIR:-/tmp}/erasemap-kaggle-v2-output.XXXXXX")"
  cleanup_download_temp() {
    if [[ -d "$download_temp" ]]; then
      find "$download_temp" -depth -delete
    fi
  }
  trap cleanup_download_temp EXIT
  kaggle_executable="$(command -v kaggle)"
  kaggle_python="$(head -n 1 "$kaggle_executable" | sed 's/^#!//')"
  if [[ ! -x "$kaggle_python" ]]; then
    echo "Cannot resolve the Python interpreter used by $kaggle_executable" >&2
    exit 2
  fi
  "$kaggle_python" "$project_root/scripts/download_kaggle_kernel_output.py" \
    "$kernel_id" \
    --destination "$download_temp" \
    --prefix "qwen-tofu-v2/"
  source_result="$download_temp/qwen-tofu-v2"
  if [[ ! -f "$source_result/summary.json" ]]; then
    echo "Completed output does not contain qwen-tofu-v2/summary.json" >&2
    exit 1
  fi
  mkdir -p "$destination"
  cp -R "$source_result/." "$destination/"
  PYTHONPATH="$project_root/src:$project_root" \
    "$project_root/.venv/bin/python" "$project_root/scripts/verify_qwen_tofu_kaggle_v2.py" \
    --protocol "$project_root/benchmark/qwen-tofu-kaggle-v2.json" \
    --result "$destination"
  exit 0
fi

echo "Unknown action: $action (expected submit, status, or collect)" >&2
exit 2
