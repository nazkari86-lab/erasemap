from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

METHODS = ("stale", "head_only", "gradient_ascent", "lineage_guided", "exact_retrain")
LABELS = ("Stale", "Head only", "Gradient ascent", "EraseMap-LGU", "Exact")
COLORS = ("#d1495b", "#edae49", "#457b9d", "#7b2cbf", "#2a9d8f")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development", default="outputs/task-agnostic-v2-development/result.json")
    parser.add_argument("--evaluation", default="outputs/task-agnostic-v2-evaluation/result.json")
    parser.add_argument("--output", default="docs/assets/task-agnostic-v2.png")
    args = parser.parse_args()
    runs = [json.loads(Path(path).read_text()) for path in (args.development, args.evaluation)]
    titles = ("Olivetti development: 100 deletions", "LFW evaluation: 100 deletions")
    metrics = (
        ("retained_verification_auc", "Retained verification AUC", 100),
        ("retained_tar_at_far", "TAR at FAR 1%", 100),
        ("membership_attack_auc", "MIA deviation from chance", 100),
        ("speedup_vs_exact", "Update speedup vs exact", 1),
    )
    figure, axes = plt.subplots(2, 4, figsize=(15, 7), constrained_layout=True)
    for row, (run, title) in enumerate(zip(runs, titles, strict=True)):
        for column, (metric, label, scale) in enumerate(metrics):
            values = [float(run["summary"][method][metric]["mean"]) for method in METHODS]
            if metric == "membership_attack_auc":
                values = [abs(value - 0.5) for value in values]
            if metric == "speedup_vs_exact":
                values[0] = 0.0
            values = [value * scale for value in values]
            axis = axes[row, column]
            axis.bar(np.arange(len(METHODS)), values, color=COLORS)
            axis.set_xticks(np.arange(len(METHODS)), LABELS, rotation=25, ha="right")
            axis.set_title(f"{title}\n{label}")
            axis.grid(axis="y", alpha=0.25)
            if scale == 100:
                axis.set_ylabel("percent")
            for index, value in enumerate(values):
                axis.text(index, value, f"{value:.2f}", ha="center", va="bottom", fontsize=8)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
