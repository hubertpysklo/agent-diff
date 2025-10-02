from __future__ import annotations

from typing import Any, Literal, Mapping, Sequence
import re


Kind = Literal["added", "removed", "changed", "unchanged"]
Bucket = Literal["inserts", "deletes", "updates"]


def _get_ignore_sets(
    spec: Mapping[str, Any], entity: str, assertion_ignore: Sequence[str] | None
) -> set[str]:
    ignores = set((spec.get("ignore_fields", {}).get("global") or []))
    entity_ignores = spec.get("ignore_fields", {}).get(entity) or []
    ignores.update(entity_ignores)
    if assertion_ignore:
        ignores.update(assertion_ignore)
    return ignores


def _get(row: Mapping[str, Any], key: str) -> Any:
    cur: Any = row
    for part in key.split("."):
        if not isinstance(cur, Mapping) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _matches_predicate(value: Any, pred: Mapping[str, Any]) -> bool:
    if not pred:
        return True
    if len(pred) != 1:
        return all(_matches_predicate(value, {op: v}) for op, v in pred.items())
    op, expected = next(iter(pred.items()))

    if op == "eq":
        return value == expected
    if op in ("ne", "not_eq"):
        return value != expected
    if op == "in":
        try:
            return value in expected
        except TypeError:
            return False
    if op == "not_in":
        try:
            return value not in expected
        except TypeError:
            return False
    if op == "contains":
        return (
            isinstance(value, str) and isinstance(expected, str) and expected in value
        )
    if op == "not_contains":
        return (
            isinstance(value, str)
            and isinstance(expected, str)
            and expected not in value
        )
    if op == "i_contains":
        return (
            isinstance(value, str)
            and isinstance(expected, str)
            and expected.lower() in value.lower()
        )
    if op == "starts_with":
        return (
            isinstance(value, str)
            and isinstance(expected, str)
            and value.startswith(expected)
        )
    if op == "ends_with":
        return (
            isinstance(value, str)
            and isinstance(expected, str)
            and value.endswith(expected)
        )
    if op == "i_starts_with":
        return (
            isinstance(value, str)
            and isinstance(expected, str)
            and value.lower().startswith(expected.lower())
        )
    if op == "i_ends_with":
        return (
            isinstance(value, str)
            and isinstance(expected, str)
            and value.lower().endswith(expected.lower())
        )
    if op == "regex":
        try:
            return isinstance(value, str) and re.search(expected, value) is not None
        except re.error:
            return False
    if op == "gt":
        try:
            return value > expected
        except Exception:
            return False
    if op == "gte":
        try:
            return value >= expected
        except Exception:
            return False
    if op == "lt":
        try:
            return value < expected
        except Exception:
            return False
    if op == "lte":
        try:
            return value <= expected
        except Exception:
            return False
    if op == "exists":
        present = value is not None
        return bool(expected) is present
    if op == "has_any":
        return isinstance(value, Sequence) and any(
            item in value for item in (expected or [])
        )
    if op == "has_all":
        return isinstance(value, Sequence) and all(
            item in value for item in (expected or [])
        )
    return False


def _row_matches_where(row: Mapping[str, Any], where: Mapping[str, Any]) -> bool:
    for key, pred in where.items():
        if not _matches_predicate(_get(row, key), pred):
            return False
    return True


def _changed_keys(
    before: Mapping[str, Any], after: Mapping[str, Any], ignores: set[str]
) -> set[str]:
    keys = set(before.keys()) | set(after.keys())
    return {k for k in keys if k not in ignores and before.get(k) != after.get(k)}


class AssertionEngine:
    def __init__(self, compiled_spec: Mapping[str, Any]):
        self.spec = compiled_spec
        self.strict = bool(compiled_spec.get("strict", True))

    def evaluate(self, diff: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict:
        failures: list[str] = []
        failed_indexes: set[int] = set()

        assertions_list = list(self.spec.get("assertions", []))
        for idx, a in enumerate(assertions_list, start=1):
            diff_type: Kind = a["diff_type"]
            entity = a["entity"]
            where = a.get("where", {})
            ignore = _get_ignore_sets(self.spec, entity, a.get("ignore", []))

            if diff_type == "added":
                rows = [
                    r
                    for r in (diff.get("inserts", []) or [])
                    if r.get("__table__") == entity
                ]
                matched = [r for r in rows if _row_matches_where(r, where)]
                self._check_count(
                    a, len(matched), failures, failed_indexes, idx, entity, diff_type
                )

            elif diff_type == "removed":
                rows = [
                    r
                    for r in (diff.get("deletes", []) or [])
                    if r.get("__table__") == entity
                ]
                matched = [r for r in rows if _row_matches_where(r, where)]
                self._check_count(
                    a, len(matched), failures, failed_indexes, idx, entity, diff_type
                )

            elif diff_type == "changed":
                updates = [
                    r
                    for r in (diff.get("updates", []) or [])
                    if r.get("__table__") == entity
                ]
                matched_updates = []
                for r in updates:
                    before = r.get("before", {})
                    after = r.get("after", {})
                    if not (
                        _row_matches_where(after, where)
                        or _row_matches_where(before, where)
                    ):
                        continue
                    changed = _changed_keys(before, after, ignore)
                    expected_changes: dict = a.get("expected_changes", {})
                    expected_keys = set(expected_changes.keys())
                    if self.strict:
                        if not changed.issubset(expected_keys):
                            self._add_failure(
                                failures,
                                failed_indexes,
                                idx,
                                f"assertion#{idx} {entity} changed fields {sorted(changed)} not subset of expected {sorted(expected_keys)}",
                            )
                            continue
                    ok = True
                    for field, spec_chg in expected_changes.items():
                        if field not in changed:
                            ok = False
                            break
                        pred_from = spec_chg.get("from")
                        pred_to = spec_chg.get("to")
                        if pred_from is not None and not _matches_predicate(
                            before.get(field), pred_from
                        ):
                            ok = False
                            break
                        if pred_to is not None and not _matches_predicate(
                            after.get(field), pred_to
                        ):
                            ok = False
                            break
                    if ok:
                        matched_updates.append(r)
                self._check_count(
                    a,
                    len(matched_updates),
                    failures,
                    failed_indexes,
                    idx,
                    entity,
                    diff_type,
                )

            elif diff_type == "unchanged":
                ins = [
                    r
                    for r in (diff.get("inserts", []) or [])
                    if r.get("__table__") == entity and _row_matches_where(r, where)
                ]
                dels = [
                    r
                    for r in (diff.get("deletes", []) or [])
                    if r.get("__table__") == entity and _row_matches_where(r, where)
                ]
                ups = [
                    r
                    for r in (diff.get("updates", []) or [])
                    if r.get("__table__") == entity
                    and (
                        _row_matches_where(r.get("after", {}), where)
                        or _row_matches_where(r.get("before", {}), where)
                    )
                ]
                total = len(ins) + len(dels) + len(ups)
                expected = a.get("expected_count")
                if expected is None:
                    if total != 0:
                        self._add_failure(
                            failures,
                            failed_indexes,
                            idx,
                            f"assertion#{idx} {entity} expected no changes but found {total}",
                        )
                else:
                    if not self._count_matches(expected, total):
                        self._add_failure(
                            failures,
                            failed_indexes,
                            idx,
                            f"assertion#{idx} {entity} expected count {expected} but got {total} (unchanged)",
                        )

            else:
                self._add_failure(
                    failures,
                    failed_indexes,
                    idx,
                    f"assertion#{idx} has unknown diff_type: {diff_type}",
                )

        total = len(assertions_list)
        failed_count = len(failed_indexes)
        passed_count = max(total - failed_count, 0)
        percent = float(passed_count) / total * 100.0 if total else 100.0

        return {
            "passed": failed_count == 0,
            "failures": failures,
            "score": {
                "passed": passed_count,
                "total": total,
                "percent": percent,
            },
        }

    @staticmethod
    def _count_matches(expected: Any, actual: int) -> bool:
        if isinstance(expected, int):
            return actual == expected
        if isinstance(expected, Mapping):
            mn = expected.get("min")
            mx = expected.get("max")
            if mn is not None and actual < mn:
                return False
            if mx is not None and actual > mx:
                return False
            return True
        return False

    def _check_count(
        self,
        a: Mapping[str, Any],
        actual: int,
        failures: list[str],
        failed_indexes: set[int],
        idx: int,
        entity: str,
        kind: str,
    ) -> None:
        expected = a.get("expected_count")
        if expected is None:
            if kind in ("added", "removed", "changed") and actual < 1:
                self._add_failure(
                    failures,
                    failed_indexes,
                    idx,
                    f"assertion#{idx} {entity} expected at least 1 match but got {actual}",
                )
            return
        if not self._count_matches(expected, actual):
            self._add_failure(
                failures,
                failed_indexes,
                idx,
                f"assertion#{idx} {entity} expected count {expected} but got {actual}",
            )

    @staticmethod
    def _add_failure(
        failures: list[str], failed_indexes: set[int], idx: int, message: str
    ) -> None:
        failed_indexes.add(idx)
        failures.append(message)
