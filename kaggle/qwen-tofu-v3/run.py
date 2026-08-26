from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

SOURCE_DATASET = Path("/kaggle/input/erasemap-qwen-tofu-v3-source")
INPUTS = Path("/kaggle/input")
CHECKOUT = Path("/kaggle/working/erasemap-source")
OUTPUT = Path("/kaggle/working/qwen-tofu-v3")


def run(*command: str, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def locate_assets() -> tuple[Path, Path, Path, Path]:
    torch_wheels = list(INPUTS.rglob("torch-2.5.1*cu121*.whl"))
    if len(torch_wheels) != 1:
        raise RuntimeError(f"expected one frozen CUDA Torch wheel, found {torch_wheels}")
    assets = torch_wheels[0].parent
    wheels = assets / "pinned-wheels" / "wheels"
    tofu = assets / "tofu-324592d" / "tofu-source"
    if not wheels.is_dir() or not tofu.is_dir():
        raise RuntimeError("attached frozen wheels or TOFU snapshot are absent")
    return assets, wheels, tofu, torch_wheels[0]


def locate_model(assets: Path) -> Path:
    candidates = [
        config.parent
        for config in INPUTS.rglob("config.json")
        if assets not in config.parents
        and SOURCE_DATASET not in config.parents
        and "qwen2.5" in str(config).lower()
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"expected one attached Qwen model, found {candidates}")
    return candidates[0]


def locate_source() -> tuple[Path, str]:
    markers = list(SOURCE_DATASET.rglob("ERASEMAP_CODE_REVISION"))
    if len(markers) != 1:
        raise RuntimeError(f"expected one source revision marker, found {markers}")
    revision = markers[0].read_text().strip()
    if len(revision) != 40 or any(value not in "0123456789abcdef" for value in revision):
        raise RuntimeError("source revision marker is malformed")
    source = markers[0].parent / "erasemap-source"
    if not (source / "benchmark/qwen-tofu-kaggle-v3.json").is_file():
        raise RuntimeError("v3 source snapshot is incomplete")
    return source, revision


def main() -> int:
    assets, wheels, tofu, frozen_torch_wheel = locate_assets()
    model = locate_model(assets)
    source, revision = locate_source()
    os.environ.update(
        {
            "ERASEMAP_MODEL_PATH": str(model),
            "ERASEMAP_TOFU_PATH": str(tofu),
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
    shutil.copytree(source, CHECKOUT)
    torch_wheel = Path("/kaggle/working/torch-v3.whl")
    shutil.copy2(frozen_torch_wheel, torch_wheel)
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
        str(wheels),
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
        "experiments/run_qwen_tofu_kaggle_v3.py",
        "--protocol",
        "benchmark/qwen-tofu-kaggle-v3.json",
        "--output",
        str(OUTPUT),
        "--code-revision",
        revision,
        cwd=CHECKOUT,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
