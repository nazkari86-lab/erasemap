from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

CASE_KINDS = frozenset(
    {
        "in-catalogue-recurrence",
        "missing-evidence",
        "outside-catalogue",
        "path-equivalent",
        "safe",
    }
)


def canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain an object")
    return cast(dict[str, Any], payload)


def validate_suite(suite: dict[str, Any], *, minimum_cases: int = 5) -> None:
    if suite.get("schema_version") != "erasemap-external-ghostgraph-suite-v1":
        raise ValueError("external GhostGraph suite schema mismatch")
    author = suite.get("author")
    if not isinstance(author, dict):
        raise ValueError("external author identity is required")
    for field in ("name", "contact", "affiliation"):
        if not isinstance(author.get(field), str) or not author[field].strip():
            raise ValueError(f"external author {field} is required")
    if author.get("project_member") is not False:
        raise ValueError("suite author must declare that they are not a project member")
    cases = suite.get("cases")
    if not isinstance(cases, list) or len(cases) < minimum_cases:
        raise ValueError("external suite has too few cases")
    ids = [item.get("case_id") for item in cases if isinstance(item, dict)]
    if len(ids) != len(cases) or any(not isinstance(item, str) or not item for item in ids):
        raise ValueError("every external case needs a non-empty case_id")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate external GhostGraph case ID")
    kinds = {item.get("kind") for item in cases}
    if kinds != CASE_KINDS:
        raise ValueError("external suite must cover all frozen case kinds")
    for case in cases:
        if "truth" not in case or "observations" not in case:
            raise ValueError("external case must contain hidden truth and observations")


def public_suite(suite: dict[str, Any]) -> dict[str, object]:
    return {
        "schema_version": "erasemap-external-ghostgraph-public-v1",
        "author": suite["author"],
        "cases": [
            {
                "case_id": item["case_id"],
                "kind": item["kind"],
                "observations": item["observations"],
                "evidence": item.get("evidence", {}),
            }
            for item in suite["cases"]
        ],
    }
