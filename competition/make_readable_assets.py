from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "competition" / "assets"
DATA = ROOT / "benchmark" / "evidence-charts-v1.json"
PAPER = "#FBFAF6"
INK = "#173F38"
MUTED = "#4F6960"
GRID = "#D3DED7"
ERASE = "#079E94"
BLUE = "#2E9BD5"
OCHRE = "#D49B43"
CORAL = "#E8795E"
LILAC = "#7077D7"
BASE = "#557B95"


def chart(data: dict[str, Any], key: str) -> dict[str, Any]:
    return next(item for item in data["charts"] if item["id"] == key)


def setup(axis: Any, title: str, ylabel: str, higher_is_better: bool = False) -> None:
    axis.set_title(title, fontsize=12.5, color=INK, fontweight="bold", pad=11, loc="left")
    axis.set_ylabel(ylabel, fontsize=10, color=MUTED, labelpad=8)
    axis.grid(axis="y", color=GRID, alpha=0.8, linewidth=0.8)
    axis.set_axisbelow(True)
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_color(GRID)
    axis.tick_params(axis="both", colors=MUTED, labelsize=9.5)
    direction = "↑ выше лучше" if higher_is_better else "↓ ниже лучше"
    axis.text(
        0.0,
        1.01,
        direction,
        transform=axis.transAxes,
        fontsize=8.5,
        color=MUTED,
        va="bottom",
    )


def bars(
    axis: Any,
    labels: list[str],
    values: list[float],
    title: str,
    ylabel: str,
    *,
    higher_is_better: bool = False,
) -> None:
    colors = [ERASE, BASE, OCHRE, CORAL, LILAC][: len(values)]
    indices = np.arange(len(values))
    axis.bar(indices, values, color=colors, width=0.68, edgecolor=PAPER, linewidth=0.9)
    axis.set_xticks(indices, labels, rotation=16, ha="right")
    setup(axis, title, ylabel, higher_is_better)
    maximum = max(values) or 1
    axis.set_ylim(0, maximum * 1.23)
    for index, value in enumerate(values):
        label = f"{value:.2f}" if value % 1 else f"{value:.0f}"
        axis.text(
            index,
            value + maximum * 0.035,
            label,
            ha="center",
            va="bottom",
            fontsize=9.5,
            color=INK,
            fontweight="bold",
        )


def save(fig: Any, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        OUT / name,
        dpi=220,
        facecolor=PAPER,
        edgecolor="none",
        bbox_inches="tight",
        pad_inches=0.12,
    )
    plt.close(fig)


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    source = chart(data, "01_source_locked")
    stock = chart(data, "02_stock_services")
    planner = chart(data, "03_planner_cost")
    multi = chart(data, "04_multiservice")
    ghost = chart(data, "05_ghostgraph_v2")
    temporal = chart(data, "06_ghostgraph_t")

    fig, axes = plt.subplots(1, 2, figsize=(14.2, 5.0), constrained_layout=True)
    bars(
        axes[0],
        ["PCUG", "Полный аудит", "Чек-лист", "Только модель", "Только квитанция"],
        source["values"],
        "Скрытая проверка · 100 случаев",
        "false-COMPLETE ↓",
    )
    bars(
        axes[1],
        ["PCUG", "Полный аудит", "Успех сервиса"],
        stock["values"],
        "Внешний перенос · 60 случаев",
        "false-COMPLETE ↓",
    )
    fig.suptitle(
        "Безопасность удаления: чем меньше false-COMPLETE, тем лучше",
        fontsize=16,
        color=INK,
        fontweight="bold",
    )
    save(fig, "readable_pcug.png")

    fig, axes = plt.subplots(1, 4, figsize=(17.2, 5.0), constrained_layout=True)
    bars(
        axes[0],
        ["Точный план", "Жадный план", "Удалить всё"],
        planner["values"],
        "Стоимость действий",
        "средняя стоимость ↓",
    )
    bars(
        axes[1],
        ["Точный план", "Пересобрать всё"],
        multi["time"],
        "Время выполнения",
        "норм. время ↓",
    )
    bars(
        axes[2],
        ["Точный план", "Пересобрать всё"],
        multi["bytes"],
        "Перезаписанные байты",
        "норм. байты ↓",
    )
    bars(
        axes[3],
        ["Точный план", "Пересобрать всё"],
        [100, 100],
        "Завершение удаления",
        "успешные задачи % ↑",
        higher_is_better=True,
    )
    fig.suptitle(
        "Эффективность: одна и та же задача, одинаковый критерий COMPLETE",
        fontsize=16,
        color=INK,
        fontweight="bold",
    )
    save(fig, "readable_cdc.png")

    fig, axes = plt.subplots(2, 2, figsize=(14.2, 8.2), constrained_layout=True)
    bars(
        axes[0, 0],
        ["Активный", "Жадный", "Случайный", "Перебор"],
        ghost["values"],
        "Поиск скрытого пути",
        "активные пробы ↓",
    )
    bars(
        axes[0, 1],
        ["EraSeMap-T", "1 шаг", "Жадный", "Случайный", "Перебор"],
        temporal["probes"],
        "Временная диагностика",
        "средние пробы ↓",
    )
    bars(
        axes[1, 0],
        ["EraSeMap-T", "1 шаг", "Жадный", "Случайный", "Перебор"],
        [100, 100, 100, 95.333, 100],
        "Правильный ответ",
        "доля правильных % ↑",
        higher_is_better=True,
    )
    bars(
        axes[1, 1],
        ["EraSeMap-T", "1 шаг", "Жадный", "Случайный", "Перебор"],
        temporal["false_confident_pct"],
        "Ложная уверенность",
        "false-confidence % ↓",
    )
    fig.suptitle(
        "Диагностика пути восстановления: меньше проб и ложной уверенности",
        fontsize=16,
        color=INK,
        fontweight="bold",
    )
    save(fig, "readable_ghostgraph.png")


if __name__ == "__main__":
    main()
