from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

COLORS = ("#2a9d8f", "#457b9d", "#edae49", "#d1495b", "#8d99ae")


def _chart(data: dict[str, Any], chart_id: str) -> dict[str, Any]:
    return next(chart for chart in data["charts"] if chart["id"] == chart_id)


def _bars(axis: Any, labels: list[str], values: list[float], title: str, ylabel: str) -> None:
    x = np.arange(len(values))
    axis.bar(x, values, color=COLORS[: len(values)])
    axis.set_xticks(x, labels, rotation=24, ha="right", fontsize=8)
    axis.set_title(title, fontsize=10)
    axis.set_ylabel(ylabel, fontsize=8)
    axis.grid(axis="y", alpha=0.25)
    ceiling = max(values) or 1
    axis.set_ylim(0, ceiling * 1.20)
    for i, value in enumerate(values):
        text = f"{value:.2f}" if value % 1 else f"{value:.0f}"
        axis.text(i, value + ceiling * 0.02, text, ha="center", fontsize=7)


def render_system_comparison(data: dict[str, Any], output: Path) -> None:
    source = _chart(data, "01_source_locked")
    stock = _chart(data, "02_stock_services")
    planner = _chart(data, "03_planner_cost")
    multi = _chart(data, "04_multiservice")
    ghost = _chart(data, "05_ghostgraph_v2")
    ghost_t = _chart(data, "06_ghostgraph_t")
    temporal = _chart(data, "07_temporal")
    fig, ax = plt.subplots(2, 4, figsize=(16, 7.5), constrained_layout=True)
    panels = [
        (
            source["labels"],
            source["values"],
            "Source-locked: false COMPLETE",
            "cases / 100 incomplete ↓",
        ),
        (stock["labels"], stock["values"], "Stock services: false COMPLETE", "cases / 60 ↓"),
        (planner["labels"], planner["values"], "Deletion planner cost", "mean cost ↓"),
        (multi["labels"], multi["time"], "Multi-service wall time", "normalized % ↓"),
        (multi["labels"], multi["bytes"], "Multi-service bytes written", "normalized % ↓"),
        (ghost["labels"], ghost["values"], "GhostGraph v2 probe budget", "probes ↓"),
        (ghost_t["labels"], ghost_t["probes"], "GhostGraph-T probe budget", "mean probes ↓"),
        (
            temporal["labels"],
            temporal["correct_pct"],
            "Temporal decision correctness*",
            "percent ↑",
        ),
    ]
    for axis, (labels, values, title, ylabel) in zip(ax.flat, panels, strict=True):
        _bars(axis, list(labels), [float(v) for v in values], title, ylabel)
    fig.suptitle("EraSeMap vs same-protocol baselines — wins, ties and limitations", fontsize=15)
    fig.text(
        0.5,
        0.002,
        "* RSE risk detection; Snapshot risk detection; Blanket safe-case specificity.",
        ha="center",
        fontsize=8,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def render_unlearning_comparison(data: dict[str, Any], output: Path) -> None:
    chart = _chart(data, "08_unlearning")
    labels = chart["labels"]
    fig, ax = plt.subplots(1, 4, figsize=(17, 4.2), constrained_layout=True)
    _bars(ax[0], labels, chart["retained_auc_pct"], "Retained verification utility", "AUC % ↑")
    _bars(
        ax[1],
        labels,
        chart["worst_privacy_advantage_pct"],
        "Worst privacy attack",
        "advantage % ↓",
    )
    _bars(
        ax[2],
        labels,
        chart["functional_mse_x1000"],
        "Distance from exact behavior",
        "functional MSE x1000 ↓",
    )
    runtime_labels = labels[:-1]
    runtime = [float(v) for v in chart["runtime_seconds"][:-1]]
    _bars(ax[3], runtime_labels, runtime, "Measured update runtime", "seconds ↓")
    fig.suptitle("MUFAC v3.2 — direct same-model unlearning algorithm comparison", fontsize=14)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="benchmark/evidence-charts-v1.json")
    parser.add_argument("--system-output", default="docs/assets/erasemap-system-comparisons.png")
    parser.add_argument(
        "--unlearning-output",
        default="docs/assets/erasemap-unlearning-v3-comparison.png",
    )
    args = parser.parse_args()
    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    render_system_comparison(data, Path(args.system_output))
    render_unlearning_comparison(data, Path(args.unlearning_output))
    print(args.system_output)
    print(args.unlearning_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
