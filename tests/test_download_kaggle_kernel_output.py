from pathlib import Path

import pytest

from scripts.download_kaggle_kernel_output import _safe_target, _selected


def test_safe_target_accepts_nested_artifact(tmp_path: Path) -> None:
    assert _safe_target(tmp_path, "qwen-tofu-v1/summary.json") == (
        tmp_path / "qwen-tofu-v1" / "summary.json"
    )


@pytest.mark.parametrize("name", ["../secret", "/absolute", "x/../../secret"])
def test_safe_target_rejects_traversal(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError, match="unsafe Kaggle output path"):
        _safe_target(tmp_path, name)


def test_selected_applies_prefix_filter() -> None:
    prefixes = ("qwen-tofu-v1/",)
    assert _selected("qwen-tofu-v1/summary.json", prefixes)
    assert not _selected("erasemap-source/README.md", prefixes)
