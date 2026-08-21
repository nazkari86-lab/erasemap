from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

METHODS = ("stale", "head_only", "gradient_ascent", "exact_retrain")
LABELS = ("Stale", "Head only", "Gradient ascent", "Exact retrain")
COLORS = ("#d1495b", "#edae49", "#457b9d", "#2a9d8f")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", default="outputs/advanced-face-unlearning-v1/result.json")
    parser.add_argument("--holdout", default="outputs/lfw-holdout-v1/result.json")
    parser.add_argument("--output", default="docs/assets/unlearning-comparison.png")
    args = parser.parse_args()
    runs = [json.loads(Path(args.dev).read_text()), json.loads(Path(args.holdout).read_text())]
    titles = ("Olivetti development", "LFW locked holdout")
    metrics = (
        ("forgotten_label_probability", "Forgotten-label probability", 100),
        ("retained_accuracy", "Retained accuracy", 100),
        ("membership_attack_auc", "Membership attack AUC", 100),
        ("encoder_parameter_l2_to_exact", "Encoder distance to exact", 1),
    )
    figure, axes = plt.subplots(2, 4, figsize=(15, 7), constrained_layout=True)
    for row, (run, title) in enumerate(zip(runs, titles, strict=True)):
        for column, (metric, label, scale) in enumerate(metrics):
            values = [float(run["methods"][method][metric]) * scale for method in METHODS]
            axis = axes[row, column]
            axis.bar(np.arange(4), values, color=COLORS)
            axis.set_xticks(np.arange(4), LABELS, rotation=25, ha="right")
            axis.set_title(f"{title}\n{label}")
            axis.grid(axis="y", alpha=0.25)
            if scale == 100:
                axis.set_ylabel("percent")
            for index, value in enumerate(values):
                axis.text(index, value, f"{value:.1f}", ha="center", va="bottom", fontsize=8)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
