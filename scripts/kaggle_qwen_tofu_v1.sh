#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
kernel_slug="erasemap-qwen-tofu-v1"
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
  echo "Create an API token in Kaggle Settings and save it as access_token or kaggle.json." >&2
  exit 2
fi

kaggle_username="${KAGGLE_USERNAME:-}"
if [[ -z "$kaggle_username" && -f "$credential_file" ]]; then
  kaggle_username="$(jq -r '.username // empty' "$credential_file")"
fi
if [[ -z "$kaggle_username" ]]; then
  echo "Kaggle username is not configured." >&2
  echo "Set KAGGLE_USERNAME or add username to $credential_file." >&2
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
  kaggle_executable="$(command -v kaggle)"
  kaggle_python="$(head -n 1 "$kaggle_executable" | sed 's/^#!//')"
  if [[ ! -x "$kaggle_python" ]]; then
    echo "Cannot resolve the Python interpreter used by $kaggle_executable" >&2
    exit 2
  fi
  "$kaggle_python" "$project_root/scripts/download_kaggle_kernel_output.py" \
    "$kernel_id" \
    --destination "$download_temp" \
    --prefix "qwen-tofu-v1/"
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
