from __future__ import annotations

from typing import Any, Mapping
import json
from pathlib import Path
from jsonschema import validate as jsonschema_validate


SCHEMA_PATH = Path(__file__).with_name("dsl_schema.json")


def _load_schema(schema_path: str | Path | None = None) -> dict:
    p = Path(schema_path) if schema_path else SCHEMA_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def _as_predicate(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    return {"eq": value}


def _normalize_where(where: Mapping[str, Any] | None) -> dict:
    if not where:
        return {}
    return {field: _as_predicate(pred) for field, pred in where.items()}


def _normalize_expected_changes(changes: Mapping[str, Any] | None) -> dict:
    if not changes:
        return {}
    normalized: dict[str, dict] = {}
    for field, spec in changes.items():
        if not isinstance(spec, dict):
            normalized[field] = {"to": _as_predicate(spec)}
            continue
        out: dict[str, Any] = {}
        if "from" in spec:
            out["from"] = _as_predicate(spec["from"])
        if "to" in spec:
            out["to"] = _as_predicate(spec["to"])
        normalized[field] = out
    return normalized


class DSLCompiler:
    def __init__(self, schema_path: str | Path | None = None):
        self.schema = _load_schema(schema_path)

    def validate(self, spec: Mapping[str, Any]) -> None:
        jsonschema_validate(instance=spec, schema=self.schema)

    def normalize(self, spec: Mapping[str, Any]) -> dict:
        normalized: dict[str, Any] = dict(spec)
        assertions = []
        for a in spec.get("assertions", []):
            aa = dict(a)
            aa["where"] = _normalize_where(aa.get("where"))
            if aa.get("diff_type") == "changed":
                aa["expected_changes"] = _normalize_expected_changes(
                    aa.get("expected_changes")
                )
            assertions.append(aa)
        normalized["assertions"] = assertions
        return normalized

    def compile(self, spec: Mapping[str, Any]) -> dict:
        self.validate(spec)
        return self.normalize(spec)
