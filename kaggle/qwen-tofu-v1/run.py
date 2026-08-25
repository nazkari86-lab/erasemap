from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPOSITORY = "https://github.com/nazkari86-lab/erasemap.git"
CODE_REVISION = "e0cf331fb0bae95f8ac434297105f407d8f59428"
CHECKOUT = Path("/kaggle/working/erasemap-source")
OUTPUT = Path("/kaggle/working/qwen-tofu-v1")


def run(*command: str, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    os.environ.update(
        {
            "HF_DATASETS_CACHE": "/tmp/erasemap-hf/datasets",
            "HF_HOME": "/tmp/erasemap-hf",
            "TOKENIZERS_PARALLELISM": "false",
            "TRANSFORMERS_CACHE": "/tmp/erasemap-hf/transformers",
        }
    )
    if CHECKOUT.exists():
        shutil.rmtree(CHECKOUT)
    run("git", "clone", "--filter=blob:none", REPOSITORY, str(CHECKOUT))
    run("git", "checkout", "--detach", CODE_REVISION, cwd=CHECKOUT)
    observed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=CHECKOUT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if observed != CODE_REVISION:
        raise RuntimeError("checked-out revision does not match the frozen experiment")
    run(
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "transformers==4.48.3",
        "peft==0.14.0",
        "datasets==3.2.0",
        "accelerate==1.3.0",
        "bitsandbytes==0.45.2",
    )
    run(sys.executable, "-m", "pip", "install", "--no-deps", "-e", str(CHECKOUT))
    run(
        sys.executable,
        "experiments/run_qwen_tofu_kaggle_v1.py",
        "--protocol",
        "benchmark/qwen-tofu-kaggle-v1.json",
        "--output",
        str(OUTPUT),
        "--code-revision",
        CODE_REVISION,
        cwd=CHECKOUT,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
