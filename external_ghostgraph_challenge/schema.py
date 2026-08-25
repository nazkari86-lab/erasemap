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

V2_SCHEMA = "erasemap-external-ghostgraph-suite-v2"


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


def validate_suite_v2(suite: dict[str, Any], *, minimum_cases: int = 5) -> None:
    if suite.get("schema_version") != V2_SCHEMA:
        raise ValueError("external GhostGraph v2 suite schema mismatch")
    author = suite.get("author")
    if not isinstance(author, dict):
        raise ValueError("external v2 author identity is required")
    for field in ("name", "contact", "affiliation"):
        if not isinstance(author.get(field), str) or not author[field].strip():
            raise ValueError(f"external v2 author {field} is required")
    if author.get("project_member") is not False:
        raise ValueError("v2 author must declare that they are not a project member")
    if author.get("authored_hidden_cases") is not True:
        raise ValueError("v2 author must declare hidden-case authorship")
    cases = suite.get("cases")
    if not isinstance(cases, list) or len(cases) < minimum_cases:
        raise ValueError("external v2 suite has too few cases")
    ids = [item.get("case_id") for item in cases if isinstance(item, dict)]
    if len(ids) != len(cases) or any(not isinstance(item, str) or not item for item in ids):
        raise ValueError("every external v2 case needs a case ID")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate external GhostGraph v2 case ID")
    if {item.get("kind") for item in cases} != CASE_KINDS:
        raise ValueError("external v2 suite must cover all frozen case kinds")
    for case in cases:
        truth = case.get("truth_graph_id") or case.get("truth_graph")
        if not truth:
            raise ValueError("external v2 case needs one hidden truth graph")
        evidence = case.get("evidence_overrides", {})
        if not isinstance(evidence, dict):
            raise ValueError("external v2 evidence override must be an object")


def public_suite_v2(suite: dict[str, Any]) -> dict[str, object]:
    return {
        "schema_version": "erasemap-external-ghostgraph-public-v2",
        "author_commitment": {
            "affiliation": suite["author"]["affiliation"],
            "authored_hidden_cases": suite["author"]["authored_hidden_cases"],
            "project_member": suite["author"]["project_member"],
        },
        "cases": [
            {
                "case_id": item["case_id"],
                "kind": item["kind"],
                "evidence_overrides": item.get("evidence_overrides", {}),
            }
            for item in suite["cases"]
        ],
    }
