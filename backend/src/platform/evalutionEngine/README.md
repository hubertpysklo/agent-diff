

# Diff Universe Assertions (JSON)

Define expected state changes as JSON that the engine validates against `dsl_schema.json`, then evaluate against diffs produced by `Differ`.

---

## Quick Example (JSON)

```json
{
  "version": "0.1",
  "scenario": "at_risk_project_updates",
  "task": "Add 'At Risk' comments to at-risk projects",
  "ignore_fields": {
    "global": ["createdAt", "updatedAt", "id"]
  },
  "assertions": [
    {
      "diff_type": "added",
      "entity": "comments",
      "where": { "projectId": {"eq": 1}, "body": {"contains": "At Risk"} },
      "expected_count": 3,
      "description": "Alpha project gets 3 comments"
    },
    {
      "diff_type": "added",
      "entity": "comments",
      "where": { "projectId": {"eq": 3}, "body": {"contains": "At Risk"} },
      "expected_count": 2,
      "description": "Gamma project gets 2 comments"
    },
    {
      "diff_type": "added",
      "entity": "comments",
      "where": { "projectId": {"eq": 2} },
      "expected_count": 0,
      "description": "Beta project unchanged"
    }
  ]
}
```

---

## Core Concepts

- **version**: schema version (currently `0.1`).
- **ignore_fields**: fields to ignore globally and per-entity when diffing.
- **assertions**: list of checks. Each assertion has:
  - **diff_type**: `added` | `removed` | `changed` | `unchanged`.
  - **entity**: table/resource name (matches `__table__` in diff rows).
  - **where**: field predicates to match rows; primitives imply `eq`.
  - **expected_count**: exact number or `{min,max}` range. If omitted, defaults to “at least 1” for added/removed/changed, and “0” for unchanged.
  - **expected_changes** (changed only): `{ field: { from, to } }` where `from`/`to` accept primitives or predicates. With `strict=true` (default), only listed fields may change.

---

## Predicates

Operators supported in predicates (in `where` and in `expected_changes.from/to`):

- **eq**, **ne**
- **in**, **not_in**
- **contains**, **not_contains**, **i_contains**, **starts_with**, **ends_with**, **i_starts_with**, **i_ends_with**, **regex**
- **gt**, **gte**, **lt**, **lte**
- **exists** (boolean), **has_any**, **has_all** (for arrays)

See full contract in `dsl_schema.json`.

