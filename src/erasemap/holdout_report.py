from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import asdict

from erasemap.external_cases import ExternalCase
from erasemap.external_evaluator import EvaluationRecord
from erasemap.pcug_domain import PCUGVerdict


def wilson95(successes: int, trials: int) -> tuple[float, float] | None:
    if trials == 0:
        return None
    z = 1.959963984540054
    proportion = successes / trials
    denominator = 1 + z * z / trials
    centre = (proportion + z * z / (2 * trials)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / trials + z * z / (4 * trials**2))
    margin /= denominator
    return max(0.0, centre - margin), min(1.0, centre + margin)


def score_holdout(
    cases: tuple[ExternalCase, ...], records: tuple[EvaluationRecord, ...]
) -> dict[str, object]:
    truth = {case.id: case for case in cases}
    expected = len(cases) * 5
    if (
        len(records) != expected
        or len({(record.case_id, record.method) for record in records}) != expected
    ):
        raise ValueError("missing or duplicate evaluator record")
    by_method: dict[str, list[EvaluationRecord]] = defaultdict(list)
    for record in records:
        case = truth.get(record.case_id)
        if case is None:
            raise ValueError("unknown evaluator case")
        by_method[record.method].append(record)
    metrics: dict[str, object] = {}
    for method, items in sorted(by_method.items()):
        noncomplete = [
            item for item in items if truth[item.case_id].truth_verdict is not PCUGVerdict.COMPLETE
        ]
        false_complete = sum(item.verdict == PCUGVerdict.COMPLETE.value for item in noncomplete)
        detected = len(noncomplete) - false_complete
        complete = [
            item for item in items if truth[item.case_id].truth_verdict is PCUGVerdict.COMPLETE
        ]
        true_complete = sum(item.verdict == PCUGVerdict.COMPLETE.value for item in complete)
        interval = wilson95(false_complete, len(noncomplete))
        metrics[method] = {
            "detected_noncomplete": detected,
            "exceptions": sum(bool(item.exception) for item in items),
            "false_complete": false_complete,
            "false_complete_rate": false_complete / len(noncomplete),
            "false_complete_wilson95": list(interval) if interval else None,
            "noncomplete": len(noncomplete),
            "specificity": true_complete / len(complete),
            "trials": len(items),
        }
    pcug = metrics["pcug"]
    assert isinstance(pcug, dict)
    interval_value = pcug["false_complete_wilson95"]
    passed = (
        pcug["false_complete"] == 0
        and isinstance(interval_value, list)
        and interval_value[1] <= 0.05
        and pcug["exceptions"] == 0
    )
    return {
        "case_count": len(cases),
        "decision": "PASS" if passed else "FAIL",
        "metrics": metrics,
        "records": [asdict(record) for record in records],
    }
