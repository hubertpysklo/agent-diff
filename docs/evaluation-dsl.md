# Evaluation DSL

The evaluation engine consumes a small JSON-based DSL to describe the expected state of the database after an agent run. Each expectation is expressed as an "assertion" evaluated against the diff between the before/after snapshots.

## Anatomy of a spec

```json
{
  "strict": true,
  "assertions": [
    {
      "diff_type": "added",
      "entity": "messages",
      "where": {
        "channelId": {"eq": 123},
        "body": {"contains": "hello"}
      },
      "expected_count": 1
    },
    {
      "diff_type": "changed",
      "entity": "issues",
      "where": {"id": {"eq": 42}},
      "expected_changes": {
        "status": {"to": {"eq": "Done"}}
      }
    }
  ]
}
```

- `diff_type` – one of `added`, `removed`, `changed`, `unchanged`.
- `entity` – table name (as it appears in the service schema).
- `where` – field predicates composed from the operator set below.
- `expected_count` – optional exact or bounded (`{"min":1}` / `{"max":2}`) match on results.
- `expected_changes` – for `changed`, lists fields and optional `from`/`to` predicates.
- `strict` – when true, the engine fails if it observes additional field changes beyond `expected_changes`.

## Operators

Scalar comparisons:

| Operator | Meaning                  |
|----------|--------------------------|
| `eq`     | equality                 |
| `neq`    | inequality               |
| `gt`/`gte` | greater than / or equal |
| `lt`/`lte` | less than / or equal    |

Collection / string helpers:

| Operator          | Meaning                                         |
|-------------------|-------------------------------------------------|
| `in` / `not_in`   | membership check on sequences                   |
| `contains`        | substring match (case sensitive)                |
| `not_contains`    | substring miss                                  |
| `starts_with`     | prefix check                                    |
| `ends_with`       | suffix check                                    |
| `has_any`         | any overlapping element in arrays               |
| `has_all`         | all elements present in arrays                  |

Null handling:

| Operator   | Meaning                        |
|------------|--------------------------------|
| `is_null`  | field is `NULL`                 |
| `not_null` | field is not `NULL`             |

Predicates can be nested with logical combinators:

```json
{"where": {"and": [{"status": {"neq": "archived"}}, {"or": [{"channelId": {"eq": 1}}, {"channelId": {"eq": 2}}]}]}}
```

## Resources

- JSON schema: `backend/src/platform/evaluationEngine/dsl_schema.json`
- Engine implementation: `backend/src/platform/evaluationEngine/assertion.py`
- Example specs: `examples/` (coming soon)

