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


def _save(figure: Any, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(figure)


def render_pcug(data: dict[str, Any], output: Path) -> None:
    source = _chart(data, "01_source_locked")
    stock = _chart(data, "02_stock_services")
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6), constrained_layout=True)
    _bars(
        ax[0],
        source["labels"],
        source["values"],
        "Does an audit wrongly say deletion is complete?\n"
        "Source-locked holdout; fewer errors are better",
        "false-COMPLETE cases / 100 ↓",
    )
    _bars(
        ax[1],
        stock["labels"],
        stock["values"],
        "Does the result transfer to stock services?\n"
        "Keycloak + MLflow + Qdrant; fewer errors are better",
        "false-COMPLETE cases / 60 ↓",
    )
    fig.suptitle(
        "OUR ALGORITHM 1 — PCUG: verifies that every required deletion condition holds", fontsize=14
    )
    _save(fig, output)


def render_cdc(data: dict[str, Any], output: Path) -> None:
    planner = _chart(data, "03_planner_cost")
    multi = _chart(data, "04_multiservice")
    fig, ax = plt.subplots(1, 4, figsize=(17, 4.5), constrained_layout=True)
    _bars(
        ax[0],
        planner["labels"],
        planner["values"],
        "How expensive is the deletion plan?\nLower cost means fewer unnecessary actions",
        "mean action cost ↓",
    )
    _bars(
        ax[1],
        multi["labels"],
        multi["time"],
        "How fast is deletion?\nSmaller wall time is faster",
        "normalized time % ↓",
    )
    _bars(
        ax[2],
        multi["labels"],
        multi["bytes"],
        "How much data is rewritten?\nSmaller means less infrastructure work",
        "normalized bytes % ↓",
    )
    _bars(
        ax[3],
        multi["labels"],
        [100, 100],
        "Do both methods actually finish deletion?\nBoth reached replayed COMPLETE in 20/20 trials",
        "successful trials % ↑",
    )
    fig.suptitle(
        "OUR ALGORITHM 2 — CDC: finds the least-cost sufficient deletion action set", fontsize=14
    )
    _save(fig, output)


def render_ghostgraph(data: dict[str, Any], output: Path) -> None:
    ghost = _chart(data, "05_ghostgraph_v2")
    temporal = _chart(data, "06_ghostgraph_t")
    fig, ax = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    _bars(
        ax[0, 0],
        ghost["labels"],
        ghost["values"],
        "How many active checks find a hidden path?\nFewer probes mean faster diagnosis",
        "probes ↓",
    )
    _bars(
        ax[0, 1],
        temporal["labels"],
        temporal["probes"],
        "How many checks identify the needed action?\n300 temporal cases; fewer are better",
        "mean probes ↓",
    )
    accuracy = [100, 100, 100, 95.333, 100]
    _bars(
        ax[1, 0],
        temporal["labels"],
        accuracy,
        "How often is the answer correct?\nRandom misses family-held-out cases",
        "correct cases % ↑",
    )
    _bars(
        ax[1, 1],
        temporal["labels"],
        temporal["false_confident_pct"],
        "How often is a wrong answer stated confidently?\nZero is safest",
        "false-confidence rate % ↓",
    )
    fig.suptitle(
        "OUR ALGORITHM 3 — GhostGraph: discovers hidden recovery paths with active probes",
        fontsize=14,
    )
    _save(fig, output)


def render_rse(data: dict[str, Any], output: Path) -> None:
    chart = _chart(data, "07_temporal")
    fig, ax = plt.subplots(1, 3, figsize=(14, 4.5), constrained_layout=True)
    _bars(
        ax[0],
        ["RSE", "Snapshot PCUG"],
        chart["risk_detection_pct"],
        "Can it predict data returning later?\n30 delayed-regeneration cases",
        "future risks detected % ↑",
    )
    _bars(
        ax[1],
        ["RSE", "Blanket carrier"],
        chart["safe_specificity_pct"],
        "Does it avoid blocking safe deletion?\n10 guarded-safe cases",
        "safe cases accepted % ↑",
    )
    _bars(
        ax[2],
        ["RSE controls", "No temporal control"],
        chart["post_control_recurrences"],
        "Does deleted data reappear afterward?\nFewer recurrences are safer",
        "recurrences / 30 ↓",
    )
    fig.suptitle(
        "OUR ALGORITHM 4 — RSE: prevents future regeneration, not only current presence",
        fontsize=14,
    )
    _save(fig, output)


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
    fig, ax = plt.subplots(2, 3, figsize=(15, 8), constrained_layout=True)
    _bars(
        ax[0, 0],
        labels,
        chart["retained_auc_pct"],
        "Does the model still work for retained users?\nHigher verification AUC is better",
        "retained AUC % ↑",
    )
    _bars(
        ax[0, 1],
        labels,
        chart["retained_tar_pct"],
        "Does it recognize retained users at strict FAR?\nHigher true-accept rate is better",
        "retained TAR % ↑",
    )
    _bars(
        ax[0, 2],
        labels,
        chart["forgotten_auc_pct"],
        "What happens on the forgotten identity?\nShown for transparency; not sufficient alone",
        "forgotten AUC %",
    )
    _bars(
        ax[1, 0],
        labels,
        chart["worst_privacy_advantage_pct"],
        "Can an attack distinguish deleted influence?\nLower worst-case advantage is safer",
        "advantage % ↓",
    )
    _bars(
        ax[1, 1],
        labels,
        chart["functional_mse_x1000"],
        "How close is behavior to exact retraining?\nLower functional distance is better",
        "functional MSE x1000 ↓",
    )
    runtime_labels = labels[:-1]
    runtime = [float(v) for v in chart["runtime_seconds"][:-1]]
    _bars(
        ax[1, 2],
        runtime_labels,
        runtime,
        "How long does the model update take?\nLower measured runtime is faster",
        "seconds ↓",
    )
    fig.suptitle(
        "OUR ALGORITHM 5 — gated unlearning candidate: speed, utility and privacy together",
        fontsize=14,
    )
    _save(fig, output)


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
    render_pcug(data, Path("docs/assets/comparison-pcug.png"))
    render_cdc(data, Path("docs/assets/comparison-cdc.png"))
    render_ghostgraph(data, Path("docs/assets/comparison-ghostgraph.png"))
    render_rse(data, Path("docs/assets/comparison-rse.png"))
    render_unlearning_comparison(data, Path(args.unlearning_output))
    print(args.system_output)
    print(args.unlearning_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
