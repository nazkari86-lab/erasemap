from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

COLORS = ("#d1495b", "#edae49", "#457b9d", "#2a9d8f")


def _annotated_bars(
    axis: Any,
    labels: tuple[str, ...],
    values: tuple[float, ...],
    *,
    title: str,
    ylabel: str,
    suffix: str = "",
) -> None:
    positions = np.arange(len(values))
    axis.bar(positions, values, color=COLORS[: len(values)])
    axis.set_xticks(positions, labels, rotation=25, ha="right")
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.grid(axis="y", alpha=0.25)
    ceiling = max(values) if max(values) > 0 else 1.0
    axis.set_ylim(0, ceiling * 1.18)
    for index, value in enumerate(values):
        label = f"{value:.2f}{suffix}" if value % 1 else f"{value:.0f}{suffix}"
        axis.text(index, value + ceiling * 0.015, label, ha="center", va="bottom", fontsize=8)


def _chart(data: dict[str, Any], chart_id: str) -> dict[str, Any]:
    return next(chart for chart in data["charts"] if chart["id"] == chart_id)


def render_system_comparison(data: dict[str, Any], output: Path) -> None:
    stress = _chart(data, "01_false_complete_stress")
    stock = _chart(data, "02_false_complete_stock_services")
    efficiency = _chart(data, "03_targeted_cdc_efficiency")
    ghostgraph = _chart(data, "04_ghostgraph_probe_budget")
    ghostgraph_t = _chart(data, "05_ghostgraph_t_action_identification")
    temporal = _chart(data, "06_temporal_rse")

    figure, axes = plt.subplots(2, 4, figsize=(15, 7), constrained_layout=True)
    panels = (
        (
            axes[0, 0],
            tuple(stress["labels"]),
            tuple(float(value) for value in stress["values"]),
            "Mechanism stress\nFalse COMPLETE",
            "cases (lower is safer)",
        ),
        (
            axes[0, 1],
            tuple(stock["labels"]),
            tuple(float(value) for value in stock["values"]),
            "Live stock services\nFalse COMPLETE",
            "cases (lower is safer)",
        ),
        (
            axes[0, 2],
            ("Rebuild-all", "Targeted CDC"),
            (100.0, float(efficiency["series"]["Targeted CDC"][0])),
            "Multi-service holdout\nWall-clock work",
            "normalized percent",
        ),
        (
            axes[0, 3],
            ("Rebuild-all", "Targeted CDC"),
            (100.0, float(efficiency["series"]["Targeted CDC"][1])),
            "Multi-service holdout\nBytes written",
            "normalized percent",
        ),
        (
            axes[1, 0],
            tuple(ghostgraph["labels"]),
            tuple(float(value) for value in ghostgraph["values"]),
            "GhostGraph v2\nProbe budget",
            "probes (lower is better)",
        ),
        (
            axes[1, 1],
            tuple(ghostgraph_t["labels"]),
            tuple(float(value) for value in ghostgraph_t["values"]),
            "GhostGraph-T\nAverage probes",
            "probes (lower is better)",
        ),
        (
            axes[1, 2],
            ("RSE", "Snapshot PCUG"),
            (float(temporal["series"]["RSE"][0]), 0.0),
            "Temporal benchmark\nFuture-risk detection",
            "correct cases",
        ),
        (
            axes[1, 3],
            ("RSE", "Blanket carrier"),
            (float(temporal["series"]["RSE"][1]), 0.0),
            "Temporal benchmark\nGuarded-safe specificity",
            "correct cases",
        ),
    )
    for axis, labels, values, title, ylabel in panels:
        _annotated_bars(axis, labels, values, title=title, ylabel=ylabel)
    figure.suptitle(
        "EraSeMap committed comparisons — each panel keeps its own frozen scope",
        fontsize=15,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180)
    plt.close(figure)


def render_unlearning_comparison(data: dict[str, Any], output: Path) -> None:
    chart = _chart(data, "07_unlearning_tradeoff")
    metrics = chart["metrics"]
    figure, axes = plt.subplots(1, 3, figsize=(15, 3.8), constrained_layout=True)
    _annotated_bars(
        axes[0],
        ("Candidate", "Exact retrain"),
        (
            float(metrics["retained_verification_auc"]["candidate"]) * 100,
            float(metrics["retained_verification_auc"]["exact"]) * 100,
        ),
        title="MUFAC v3.2\nRetained verification AUC",
        ylabel="percent (higher is better)",
    )
    _annotated_bars(
        axes[1],
        ("Candidate", "Exact retrain"),
        (
            float(metrics["speedup"]["candidate"]),
            float(metrics["speedup"]["exact"]),
        ),
        title="MUFAC v3.2\nSpeedup",
        ylabel="times (higher is better)",
        suffix="x",
    )
    _annotated_bars(
        axes[2],
        ("Candidate", "Frozen gate"),
        (
            float(metrics["privacy_upper_bound"]["candidate"]),
            float(metrics["privacy_upper_bound"]["gate"]),
        ),
        title="MUFAC v3.2\nPrivacy upper bound",
        ylabel="advantage (lower is better)",
    )
    figure.suptitle(
        "Model-unlearning trade-off — the candidate passes its gate; exact remains the reference",
        fontsize=14,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180)
    plt.close(figure)


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
