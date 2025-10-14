import pytest
from src.platform.evaluationEngine.assertion import (
    AssertionEngine,
    _matches_predicate,
    _row_matches_where,
    _get_ignore_sets,
    _changed_keys
)


class TestStringPredicates:
    def test_contains(self):
        assert _matches_predicate("hello world", {"contains": "world"})
        assert not _matches_predicate("hello world", {"contains": "xyz"})
        assert not _matches_predicate(123, {"contains": "world"})

    def test_not_contains(self):
        assert _matches_predicate("hello world", {"not_contains": "xyz"})
        assert not _matches_predicate("hello world", {"not_contains": "world"})

    def test_i_contains_case_insensitive(self):
        assert _matches_predicate("Hello World", {"i_contains": "WORLD"})
        assert _matches_predicate("Hello World", {"i_contains": "hello"})
        assert not _matches_predicate("Hello World", {"i_contains": "xyz"})

    def test_starts_with(self):
        assert _matches_predicate("hello world", {"starts_with": "hello"})
        assert not _matches_predicate("hello world", {"starts_with": "world"})

    def test_ends_with(self):
        assert _matches_predicate("hello world", {"ends_with": "world"})
        assert not _matches_predicate("hello world", {"ends_with": "hello"})

    def test_i_starts_with_case_insensitive(self):
        assert _matches_predicate("Hello World", {"i_starts_with": "HELLO"})
        assert _matches_predicate("Hello World", {"i_starts_with": "hello"})

    def test_i_ends_with_case_insensitive(self):
        assert _matches_predicate("Hello World", {"i_ends_with": "WORLD"})
        assert _matches_predicate("Hello World", {"i_ends_with": "world"})

    def test_regex(self):
        assert _matches_predicate("test123", {"regex": r"\d+"})
        assert _matches_predicate("abc@example.com", {"regex": r"^[\w\.-]+@[\w\.-]+\.\w+$"})
        assert not _matches_predicate("test", {"regex": r"\d+"})
        assert not _matches_predicate(123, {"regex": r"\d+"})


class TestComparisonPredicates:
    def test_eq(self):
        assert _matches_predicate(5, {"eq": 5})
        assert _matches_predicate("test", {"eq": "test"})
        assert not _matches_predicate(5, {"eq": 6})

    def test_ne(self):
        assert _matches_predicate(5, {"ne": 6})
        assert not _matches_predicate(5, {"ne": 5})

    def test_gt_gte(self):
        assert _matches_predicate(10, {"gt": 5})
        assert not _matches_predicate(5, {"gt": 5})
        assert _matches_predicate(5, {"gte": 5})
        assert _matches_predicate(6, {"gte": 5})

    def test_lt_lte(self):
        assert _matches_predicate(5, {"lt": 10})
        assert not _matches_predicate(10, {"lt": 10})
        assert _matches_predicate(10, {"lte": 10})
        assert _matches_predicate(9, {"lte": 10})

    def test_comparison_with_null(self):
        assert not _matches_predicate(None, {"gt": 5})
        assert not _matches_predicate(None, {"lt": 5})

    def test_comparison_with_non_numeric(self):
        assert not _matches_predicate("text", {"gt": 5})


class TestMembershipPredicates:
    def test_in(self):
        assert _matches_predicate("a", {"in": ["a", "b", "c"]})
        assert not _matches_predicate("d", {"in": ["a", "b", "c"]})
        assert _matches_predicate(1, {"in": [1, 2, 3]})

    def test_not_in(self):
        assert _matches_predicate("d", {"not_in": ["a", "b", "c"]})
        assert not _matches_predicate("a", {"not_in": ["a", "b", "c"]})

    def test_has_any(self):
        assert _matches_predicate(["a", "b", "c"], {"has_any": ["a", "x"]})
        assert not _matches_predicate(["a", "b", "c"], {"has_any": ["x", "y"]})
        assert _matches_predicate("abc", {"has_any": ["a", "x"]})

    def test_has_all(self):
        assert _matches_predicate(["a", "b", "c"], {"has_all": ["a", "b"]})
        assert not _matches_predicate(["a", "b"], {"has_all": ["a", "b", "c"]})

    def test_exists(self):
        assert _matches_predicate("value", {"exists": True})
        assert _matches_predicate(0, {"exists": True})
        assert _matches_predicate(None, {"exists": False})
        assert not _matches_predicate("value", {"exists": False})


class TestRowMatching:
    def test_row_matches_single_where(self):
        row = {"channel_id": "C123", "text": "hello"}
        assert _row_matches_where(row, {"channel_id": {"eq": "C123"}})
        assert not _row_matches_where(row, {"channel_id": {"eq": "C456"}})

    def test_row_matches_multiple_where(self):
        row = {"channel_id": "C123", "text": "hello world"}
        where = {
            "channel_id": {"eq": "C123"},
            "text": {"contains": "world"}
        }
        assert _row_matches_where(row, where)

    def test_row_matches_all_conditions_required(self):
        row = {"channel_id": "C123", "text": "hello"}
        where = {
            "channel_id": {"eq": "C123"},
            "text": {"contains": "world"}
        }
        assert not _row_matches_where(row, where)

    def test_row_matches_empty_where(self):
        row = {"channel_id": "C123"}
        assert _row_matches_where(row, {})

    def test_row_matches_nested_field(self):
        row = {"user": {"id": "U123", "name": "John"}}
        assert _row_matches_where(row, {"user.id": {"eq": "U123"}})
        assert not _row_matches_where(row, {"user.id": {"eq": "U456"}})


class TestIgnoreSets:
    def test_global_ignores(self):
        spec = {
            "ignore_fields": {
                "global": ["created_at", "updated_at"]
            }
        }
        ignores = _get_ignore_sets(spec, "messages", None)
        assert ignores == {"created_at", "updated_at"}

    def test_entity_ignores(self):
        spec = {
            "ignore_fields": {
                "messages": ["id", "temp"]
            }
        }
        ignores = _get_ignore_sets(spec, "messages", None)
        assert ignores == {"id", "temp"}

    def test_combined_ignores(self):
        spec = {
            "ignore_fields": {
                "global": ["created_at"],
                "messages": ["id"]
            }
        }
        ignores = _get_ignore_sets(spec, "messages", None)
        assert ignores == {"created_at", "id"}

    def test_assertion_level_ignores(self):
        spec = {
            "ignore_fields": {
                "global": ["created_at"]
            }
        }
        ignores = _get_ignore_sets(spec, "messages", ["temp_field"])
        assert ignores == {"created_at", "temp_field"}


class TestChangedKeys:
    def test_changed_keys_detects_changes(self):
        before = {"a": 1, "b": 2, "c": 3}
        after = {"a": 1, "b": 999, "c": 3}
        changed = _changed_keys(before, after, set())
        assert changed == {"b"}

    def test_changed_keys_ignores_specified_fields(self):
        before = {"a": 1, "b": 2, "c": 3}
        after = {"a": 1, "b": 999, "c": 999}
        changed = _changed_keys(before, after, {"c"})
        assert changed == {"b"}

    def test_changed_keys_detects_added_fields(self):
        before = {"a": 1}
        after = {"a": 1, "b": 2}
        changed = _changed_keys(before, after, set())
        assert changed == {"b"}

    def test_changed_keys_detects_removed_fields(self):
        before = {"a": 1, "b": 2}
        after = {"a": 1}
        changed = _changed_keys(before, after, set())
        assert changed == {"b"}


class TestCountMatching:
    def test_exact_count_match(self):
        engine = AssertionEngine({"version": "0.1", "assertions": []})
        assert engine._count_matches(5, 5)
        assert not engine._count_matches(5, 3)

    def test_range_min_only(self):
        engine = AssertionEngine({"version": "0.1", "assertions": []})
        assert engine._count_matches({"min": 3}, 5)
        assert engine._count_matches({"min": 3}, 3)
        assert not engine._count_matches({"min": 3}, 2)

    def test_range_max_only(self):
        engine = AssertionEngine({"version": "0.1", "assertions": []})
        assert engine._count_matches({"max": 10}, 5)
        assert engine._count_matches({"max": 10}, 10)
        assert not engine._count_matches({"max": 10}, 11)

    def test_range_min_and_max(self):
        engine = AssertionEngine({"version": "0.1", "assertions": []})
        assert engine._count_matches({"min": 3, "max": 10}, 5)
        assert engine._count_matches({"min": 3, "max": 10}, 3)
        assert engine._count_matches({"min": 3, "max": 10}, 10)
        assert not engine._count_matches({"min": 3, "max": 10}, 2)
        assert not engine._count_matches({"min": 3, "max": 10}, 11)


class TestAssertionEngineEvaluate:
    def test_added_assertion_passes(self):
        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "added",
                    "entity": "messages",
                    "where": {"text": {"contains": "hello"}},
                    "expected_count": 1
                }
            ]
        }
        diff = {
            "inserts": [
                {"__table__": "messages", "text": "hello world"}
            ],
            "updates": [],
            "deletes": []
        }
        engine = AssertionEngine(spec)
        result = engine.evaluate(diff)

        assert result["passed"] is True
        assert result["score"]["passed"] == 1
        assert result["score"]["total"] == 1

    def test_added_assertion_fails_count(self):
        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "added",
                    "entity": "messages",
                    "expected_count": 2
                }
            ]
        }
        diff = {
            "inserts": [
                {"__table__": "messages", "text": "hello"}
            ],
            "updates": [],
            "deletes": []
        }
        engine = AssertionEngine(spec)
        result = engine.evaluate(diff)

        assert result["passed"] is False
        assert result["score"]["passed"] == 0
        assert len(result["failures"]) == 1

    def test_removed_assertion_passes(self):
        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "removed",
                    "entity": "messages",
                    "where": {"message_id": {"eq": "M123"}},
                    "expected_count": 1
                }
            ]
        }
        diff = {
            "inserts": [],
            "updates": [],
            "deletes": [
                {"__table__": "messages", "message_id": "M123"}
            ]
        }
        engine = AssertionEngine(spec)
        result = engine.evaluate(diff)

        assert result["passed"] is True

    def test_changed_assertion_strict_mode(self):
        spec = {
            "version": "0.1",
            "strict": True,
            "assertions": [
                {
                    "diff_type": "changed",
                    "entity": "channels",
                    "where": {"channel_id": {"eq": "C123"}},
                    "expected_changes": {
                        "topic": {"to": {"contains": "new"}}
                    },
                    "expected_count": 1
                }
            ]
        }
        diff = {
            "inserts": [],
            "updates": [
                {
                    "__table__": "channels",
                    "before": {"channel_id": "C123", "topic": "old topic"},
                    "after": {"channel_id": "C123", "topic": "new topic"}
                }
            ],
            "deletes": []
        }
        engine = AssertionEngine(spec)
        result = engine.evaluate(diff)

        assert result["passed"] is True

    def test_changed_assertion_strict_mode_fails_unexpected_change(self):
        spec = {
            "version": "0.1",
            "strict": True,
            "assertions": [
                {
                    "diff_type": "changed",
                    "entity": "channels",
                    "expected_changes": {
                        "topic": {"to": "new"}
                    }
                }
            ]
        }
        diff = {
            "inserts": [],
            "updates": [
                {
                    "__table__": "channels",
                    "before": {"channel_id": "C123", "topic": "old", "name": "old name"},
                    "after": {"channel_id": "C123", "topic": "new", "name": "new name"}
                }
            ],
            "deletes": []
        }
        engine = AssertionEngine(spec)
        result = engine.evaluate(diff)

        assert result["passed"] is False

    def test_unchanged_assertion_passes_no_changes(self):
        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "unchanged",
                    "entity": "messages",
                    "where": {"channel_id": {"eq": "C123"}}
                }
            ]
        }
        diff = {
            "inserts": [],
            "updates": [],
            "deletes": []
        }
        engine = AssertionEngine(spec)
        result = engine.evaluate(diff)

        assert result["passed"] is True

    def test_unchanged_assertion_fails_with_changes(self):
        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "unchanged",
                    "entity": "messages"
                }
            ]
        }
        diff = {
            "inserts": [
                {"__table__": "messages", "text": "new"}
            ],
            "updates": [],
            "deletes": []
        }
        engine = AssertionEngine(spec)
        result = engine.evaluate(diff)

        assert result["passed"] is False
