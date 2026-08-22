from __future__ import annotations

import json
from pathlib import Path

from experiments.run_mufac_safe_policy_v2 import choose_method


def test_mufac_failure_triggers_exact_retrain_fallback() -> None:
    protocol = json.loads(Path("benchmark/mufac-external-v2.json").read_text())
    evidence = json.loads(
        Path("benchmark/results/task-agnostic-v3/external-summary.json").read_text()
    )
    result = choose_method(protocol, evidence)
    assert result["selected_method"] == "exact_retrain"
    assert result["decision"] == "SAFE_FALLBACK"
    assert result["gates"]["retained_auc_loss_upper"] is False  # type: ignore[index]
    assert result["selected_retained_cka_mean"] == 1.0
    assert result["selected_speedup_mean"] == 1.0
