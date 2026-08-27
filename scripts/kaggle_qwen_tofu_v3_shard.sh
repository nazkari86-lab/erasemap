#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
action="${1:-status}"
shard_index="${2:-0}"
if [[ ! "$shard_index" =~ ^[0-4]$ ]]; then
  echo "Shard index must be 0..4" >&2
  exit 2
fi
credential_dir="${KAGGLE_CONFIG_DIR:-$HOME/.kaggle}"
if [[ -z "${KAGGLE_API_TOKEN:-}" && -s "$credential_dir/access_token" ]]; then
  KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$credential_dir/access_token")"
  export KAGGLE_API_TOKEN
fi
kaggle_username="${KAGGLE_USERNAME:-}"
if [[ -z "$kaggle_username" && -f "$credential_dir/kaggle.json" ]]; then
  kaggle_username="$(jq -r '.username // empty' "$credential_dir/kaggle.json")"
fi
if [[ -z "$kaggle_username" ]]; then
  echo "Kaggle username is not configured" >&2
  exit 2
fi

kernel_slug="erasemap-qwen-tofu-v6-dev-${shard_index}"
kernel_id="$kaggle_username/$kernel_slug"
source_id="$kaggle_username/erasemap-qwen-tofu-v3-source"

if [[ "$action" == "status" ]]; then
  kaggle kernels status "$kernel_id"
  exit 0
fi

if [[ "$action" == "submit" ]]; then
  if [[ -n "$(git -C "$project_root" status --porcelain)" ]]; then
    echo "Refusing to freeze a dirty worktree" >&2
    exit 2
  fi
  revision="$(git -C "$project_root" rev-parse HEAD)"
  source_temp="$(mktemp -d "${TMPDIR:-/tmp}/erasemap-v6-source.XXXXXX")"
  kernel_temp="$(mktemp -d "${TMPDIR:-/tmp}/erasemap-v6-kernel.XXXXXX")"
  cleanup() {
    for directory in "$source_temp" "$kernel_temp"; do
      if [[ -d "$directory" ]]; then find "$directory" -depth -delete; fi
    done
  }
  trap cleanup EXIT
  mkdir -p "$source_temp/erasemap-source"
  git -C "$project_root" archive HEAD | tar -x -C "$source_temp/erasemap-source"
  printf '%s\n' "$revision" > "$source_temp/ERASEMAP_CODE_REVISION"
  jq -n --arg id "$source_id" \
    '{title:"EraSeMap Qwen TOFU v3 source",id:$id,licenses:[{name:"MIT"}]}' \
    > "$source_temp/dataset-metadata.json"
  kaggle datasets version -p "$source_temp" -m "Frozen shard source $revision" --dir-mode zip
  for _ in {1..60}; do
    if [[ "$(kaggle datasets status "$source_id" 2>/dev/null || true)" == "ready" ]]; then
      break
    fi
    sleep 5
  done
  cp "$project_root/kaggle/qwen-tofu-v3/run.py" "$kernel_temp/run.py"
  sed -i.bak \
    "s/SHARD_INDEX: int | None = None/SHARD_INDEX: int | None = ${shard_index}/" \
    "$kernel_temp/run.py"
  find "$kernel_temp" -name '*.bak' -delete
  jq -n \
    --arg id "$kernel_id" \
    --arg title "EraSeMap Qwen TOFU v6 development shard $shard_index" \
    --arg source "$source_id" \
    '{id:$id,title:$title,code_file:"run.py",language:"python",kernel_type:"script",is_private:true,enable_gpu:true,enable_internet:false,dataset_sources:["hijima/erasemap-qwen-tofu-v1-assets",$source],competition_sources:[],kernel_sources:[],model_sources:["qwen-lm/qwen2.5/transformers/1.5b/1"]}' \
    > "$kernel_temp/kernel-metadata.json"
  kaggle kernels push -p "$kernel_temp"
  echo "Submitted $kernel_id from $revision"
  exit 0
fi

if [[ "$action" == "collect" ]]; then
  destination="$project_root/outputs/qwen-tofu-kaggle-v3-shards/development-${shard_index}"
  if [[ -e "$destination" ]]; then
    echo "Refusing to overwrite $destination" >&2
    exit 2
  fi
  temp="$(mktemp -d "${TMPDIR:-/tmp}/erasemap-v6-output.XXXXXX")"
  trap 'find "$temp" -depth -delete' EXIT
  kaggle_python="$(head -n 1 "$(command -v kaggle)" | sed 's/^#!//')"
  "$kaggle_python" "$project_root/scripts/download_kaggle_kernel_output.py" \
    "$kernel_id" --destination "$temp" \
    --prefix "qwen-tofu-v3-development-${shard_index}/"
  source_result="$temp/qwen-tofu-v3-development-${shard_index}"
  mkdir -p "$destination"
  cp -R "$source_result/." "$destination/"
  "$project_root/.venv/bin/python" \
    "$project_root/scripts/verify_qwen_tofu_kaggle_v3_shard.py" \
    "$destination" --expected-fold "$shard_index"
  exit 0
fi

echo "Unknown action: $action (expected submit, status, collect)" >&2
exit 2
