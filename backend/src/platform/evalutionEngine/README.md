

# Diff Universe DSL

Diff Universe DSL is a lightweight, human-readable format for describing expected state changes in isolated environments.
It is designed for evaluating LLM agents and system behaviors by comparing before/after snapshots.
Think of it as a Git diff for your data.

---

## Quick Example

```yaml
dsl_version: "0.1"

masks:                # global fields to ignore in all diffs
  - updated_at
  - archived_at

added:
  - entity: issue
    where: { project: Frontend }
    assert:
      title.eq: Artem
    increment:
      count: 1

removed:
  - entity: issue
    where: { id: 2 }
    increment:
      count: -1

changed:
  - entity: issue
    where: { name: Artem }
    assert:
      description.contains: hi
    ignore:            # local ignore for this block
      - sort_order
```

---

## Core Concepts

* **entity** – the table or resource (e.g. `issues`, `users`, `messages`)
* **where** – filters to identify records by business keys
* **assert** – expected after-state using predicates
* **increment** – expected row-count delta (`+1` for add, `-1` for remove)
* **masks** – global fields to ignore in all diffs
* **ignore** – per-block fields to ignore

---

## Predicates

Available operators inside `assert`:

| Operator        | Example                         | Meaning                        |
| --------------- | ------------------------------- | ------------------------------ |
| `eq`            | `status.eq: done`               | value must equal               |
| `ne` / `not_eq` | `priority.ne: low`              | value must not equal           |
| `in`            | `status.in: [open, backlog]`    | value must be in list          |
| `not_in`        | `status.not_in: [done, closed]` | value must not be in list      |
| `contains`      | `description.contains: hi`      | string contains substring      |
| `not_contains`  | `title.not_contains: draft`     | string must not contain string |

