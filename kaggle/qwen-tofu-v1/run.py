from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

CODE_REVISION = "50305b8931ef915a6de3242d5220e1b2b25d9841"
ASSETS = Path("/kaggle/input/erasemap-qwen-tofu-v1-assets")
INPUTS = Path("/kaggle/input")
CHECKOUT = Path("/kaggle/working/erasemap-source")
WHEELS = ASSETS / "pinned-wheels" / "wheels"
TOFU = ASSETS / "tofu-324592d" / "tofu-source"
OUTPUT = Path("/kaggle/working/qwen-tofu-v1")


def run(*command: str, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def locate_model() -> Path:
    candidates = [
        config.parent
        for config in INPUTS.rglob("config.json")
        if ASSETS not in config.parents and "qwen2.5" in str(config).lower()
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"expected one attached Qwen model, found {candidates}")
    return candidates[0]


def main() -> int:
    model = locate_model()
    torch_wheels = list(ASSETS.glob("torch-2.5.1*cu121*.whl"))
    if len(torch_wheels) != 1:
        raise RuntimeError(f"expected one frozen CUDA Torch wheel, found {torch_wheels}")
    os.environ.update(
        {
            "ERASEMAP_MODEL_PATH": str(model),
            "ERASEMAP_TOFU_PATH": str(TOFU),
            "HF_DATASETS_CACHE": "/tmp/erasemap-hf/datasets",
            "HF_HOME": "/tmp/erasemap-hf",
            "HF_HUB_OFFLINE": "1",
            "PYTHONPATH": f"{CHECKOUT / 'src'}:{CHECKOUT}",
            "TOKENIZERS_PARALLELISM": "false",
            "TRANSFORMERS_CACHE": "/tmp/erasemap-hf/transformers",
        }
    )
    for directory in (CHECKOUT, OUTPUT):
        if directory.exists():
            shutil.rmtree(directory)
    shutil.copytree(ASSETS / "erasemap-50305b8", CHECKOUT)
    if not WHEELS.is_dir() or not TOFU.is_dir():
        raise RuntimeError("attached frozen wheels or TOFU snapshot are absent")
    torch_wheel = Path("/kaggle/working/torch-2.5.1+cu121-cp312-cp312-linux_x86_64.whl")
    shutil.copy2(torch_wheels[0], torch_wheel)
    run(
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--no-index",
        "--no-deps",
        str(torch_wheel),
    )
    torch_wheel.unlink()
    run(sys.executable, "-m", "pip", "uninstall", "--yes", "torchvision")
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
        "tokenizers==0.21.4",
        "huggingface-hub==0.28.1",
    )
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
