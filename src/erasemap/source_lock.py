from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

SOURCE_SCHEMA = "erasemap-external-sources-v1"
ALLOWED_RELATIONS = frozenset(
    {
        "ALTERNATE_COPY",
        "ARTIFACT_OF",
        "BACKUP_OF",
        "DERIVED_FROM",
        "IDENTITY_BOUND",
        "RECOVERABLE_FROM",
    }
)


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class RelationMapping:
    id: str
    relation: str
    source_kind: str
    target_kind: str
    rationale: str


@dataclass(frozen=True, slots=True)
class SourceExcerpt:
    id: str
    family: str
    title: str
    url: str
    retrieved_at: str
    excerpt: str
    excerpt_sha256: str
    mappings: tuple[RelationMapping, ...]


@dataclass(frozen=True, slots=True)
class SourceManifest:
    schema_version: str
    sources: tuple[SourceExcerpt, ...]

    @property
    def digest(self) -> str:
        return sha256_text(canonical_json(to_payload(self)))


def _exact_fields(payload: dict[str, Any], expected: set[str], where: str) -> None:
    missing = sorted(expected - set(payload))
    extra = sorted(set(payload) - expected)
    if missing or extra:
        detail = f"missing={missing}" if missing else f"unknown={extra}"
        raise ValueError(f"invalid fields at {where}: {detail}")


def load_source_manifest(path: str | Path) -> SourceManifest:
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ValueError("source manifest must be an object")
    payload = cast(dict[str, Any], raw)
    _exact_fields(payload, {"schema_version", "sources"}, "manifest")
    if payload["schema_version"] != SOURCE_SCHEMA:
        raise ValueError("unsupported source manifest schema")
    if not isinstance(payload["sources"], list) or not payload["sources"]:
        raise ValueError("sources must be a non-empty array")
    sources: list[SourceExcerpt] = []
    source_ids: set[str] = set()
    mapping_ids: set[str] = set()
    for index, raw_source in enumerate(payload["sources"]):
        if not isinstance(raw_source, dict):
            raise ValueError(f"source[{index}] must be an object")
        source = cast(dict[str, Any], raw_source)
        _exact_fields(
            source,
            {
                "excerpt",
                "excerpt_sha256",
                "family",
                "id",
                "mappings",
                "retrieved_at",
                "title",
                "url",
            },
            f"source[{index}]",
        )
        source_id = str(source["id"])
        if not source_id or source_id in source_ids:
            raise ValueError("source ids must be unique and non-empty")
        source_ids.add(source_id)
        url = str(source["url"])
        if urlparse(url).scheme != "https":
            raise ValueError(f"source {source_id} must use HTTPS")
        excerpt = str(source["excerpt"])
        if sha256_text(excerpt) != source["excerpt_sha256"]:
            raise ValueError(f"excerpt hash mismatch for {source_id}")
        raw_mappings = source["mappings"]
        if not isinstance(raw_mappings, list) or not raw_mappings:
            raise ValueError(f"source {source_id} needs mappings")
        mappings: list[RelationMapping] = []
        for raw_mapping in raw_mappings:
            if not isinstance(raw_mapping, dict):
                raise ValueError("mapping must be an object")
            mapping = cast(dict[str, Any], raw_mapping)
            _exact_fields(
                mapping, {"id", "rationale", "relation", "source_kind", "target_kind"}, "mapping"
            )
            mapping_id = str(mapping["id"])
            relation = str(mapping["relation"])
            if not mapping_id or mapping_id in mapping_ids:
                raise ValueError("mapping ids must be globally unique")
            if relation not in ALLOWED_RELATIONS:
                raise ValueError(f"unsupported relation {relation}")
            mapping_ids.add(mapping_id)
            mappings.append(
                RelationMapping(
                    id=mapping_id,
                    relation=relation,
                    source_kind=str(mapping["source_kind"]),
                    target_kind=str(mapping["target_kind"]),
                    rationale=str(mapping["rationale"]),
                )
            )
        sources.append(
            SourceExcerpt(
                id=source_id,
                family=str(source["family"]),
                title=str(source["title"]),
                url=url,
                retrieved_at=str(source["retrieved_at"]),
                excerpt=excerpt,
                excerpt_sha256=str(source["excerpt_sha256"]),
                mappings=tuple(mappings),
            )
        )
    return SourceManifest(SOURCE_SCHEMA, tuple(sources))


def to_payload(manifest: SourceManifest) -> dict[str, object]:
    return {
        "schema_version": manifest.schema_version,
        "sources": [
            {
                "excerpt": source.excerpt,
                "excerpt_sha256": source.excerpt_sha256,
                "family": source.family,
                "id": source.id,
                "mappings": [
                    {
                        "id": mapping.id,
                        "rationale": mapping.rationale,
                        "relation": mapping.relation,
                        "source_kind": mapping.source_kind,
                        "target_kind": mapping.target_kind,
                    }
                    for mapping in source.mappings
                ],
                "retrieved_at": source.retrieved_at,
                "title": source.title,
                "url": source.url,
            }
            for source in manifest.sources
        ],
    }
