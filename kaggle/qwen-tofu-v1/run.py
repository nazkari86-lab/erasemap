from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

CODE_REVISION = "50305b8931ef915a6de3242d5220e1b2b25d9841"
ASSETS = Path("/kaggle/input/erasemap-qwen-tofu-v1-assets")
MODEL = Path("/kaggle/input/qwen2.5/transformers/1.5b/1")
CHECKOUT = Path("/kaggle/working/erasemap-source")
WHEELS = Path("/kaggle/working/pinned-wheels")
TOFU = Path("/kaggle/working/tofu-source")
OUTPUT = Path("/kaggle/working/qwen-tofu-v1")


def run(*command: str, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive) as stream:
        stream.extractall(destination, filter="data")


def main() -> int:
    os.environ.update(
        {
            "ERASEMAP_MODEL_PATH": str(MODEL),
            "ERASEMAP_TOFU_PATH": str(TOFU),
            "HF_DATASETS_CACHE": "/tmp/erasemap-hf/datasets",
            "HF_HOME": "/tmp/erasemap-hf",
            "HF_HUB_OFFLINE": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "TRANSFORMERS_CACHE": "/tmp/erasemap-hf/transformers",
        }
    )
    for directory in (CHECKOUT, WHEELS, TOFU, OUTPUT):
        if directory.exists():
            shutil.rmtree(directory)
    extract(ASSETS / "erasemap-50305b8.tar.gz", CHECKOUT)
    extract(ASSETS / "pinned-wheels.tar.gz", WHEELS)
    tofu_container = TOFU.parent / "tofu-container"
    if tofu_container.exists():
        shutil.rmtree(tofu_container)
    extract(ASSETS / "tofu-324592d.tar.gz", tofu_container)
    shutil.move(str(tofu_container / "tofu-source"), TOFU)
    shutil.rmtree(tofu_container)
    if not (MODEL / "config.json").is_file():
        raise RuntimeError(f"attached Qwen model is absent at {MODEL}")
    run(
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--no-index",
        "--no-deps",
        "--find-links",
        str(WHEELS),
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
