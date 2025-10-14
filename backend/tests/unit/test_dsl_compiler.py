import pytest
from jsonschema.exceptions import ValidationError
from src.platform.evaluationEngine.compiler import DSLCompiler


class TestDSLSchemaValidation:
    def test_valid_minimal_spec(self):
        compiler = DSLCompiler()
        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "added",
                    "entity": "messages"
                }
            ]
        }
        compiler.validate(spec)

    def test_invalid_version_rejected(self):
        compiler = DSLCompiler()
        spec = {
            "version": "999.0",
            "assertions": [
                {
                    "diff_type": "added",
                    "entity": "messages"
                }
            ]
        }
        with pytest.raises(ValidationError):
            compiler.validate(spec)

    def test_missing_version_rejected(self):
        compiler = DSLCompiler()
        spec = {
            "assertions": [
                {
                    "diff_type": "added",
                    "entity": "messages"
                }
            ]
        }
        with pytest.raises(ValidationError):
            compiler.validate(spec)

    def test_missing_assertions_rejected(self):
        compiler = DSLCompiler()
        spec = {
            "version": "0.1"
        }
        with pytest.raises(ValidationError):
            compiler.validate(spec)

    def test_invalid_diff_type_rejected(self):
        compiler = DSLCompiler()
        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "modified",
                    "entity": "messages"
                }
            ]
        }
        with pytest.raises(ValidationError):
            compiler.validate(spec)

    def test_invalid_predicate_operator_rejected(self):
        compiler = DSLCompiler()
        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "added",
                    "entity": "messages",
                    "where": {
                        "text": {"invalid_op": "value"}
                    }
                }
            ]
        }
        with pytest.raises(ValidationError):
            compiler.validate(spec)

    def test_changed_requires_expected_changes(self):
        compiler = DSLCompiler()
        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "changed",
                    "entity": "messages",
                    "expected_changes": {
                        "text": {"to": "new value"}
                    }
                }
            ]
        }
        compiler.validate(spec)

    def test_extra_properties_rejected(self):
        compiler = DSLCompiler()
        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "added",
                    "entity": "messages"
                }
            ],
            "unknown_field": "should fail"
        }
        with pytest.raises(ValidationError):
            compiler.validate(spec)


class TestDSLNormalization:
    def test_shorthand_values_to_eq_predicate(self):
        compiler = DSLCompiler()
        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "added",
                    "entity": "messages",
                    "where": {
                        "channel_id": "C123",
                        "user_id": "U456"
                    }
                }
            ]
        }
        normalized = compiler.normalize(spec)
        assertion = normalized["assertions"][0]

        assert assertion["where"]["channel_id"] == {"eq": "C123"}
        assert assertion["where"]["user_id"] == {"eq": "U456"}

    def test_where_clause_normalization(self):
        compiler = DSLCompiler()
        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "added",
                    "entity": "messages",
                    "where": {
                        "text": {"contains": "hello"},
                        "count": 5
                    }
                }
            ]
        }
        normalized = compiler.normalize(spec)
        assertion = normalized["assertions"][0]

        assert assertion["where"]["text"] == {"contains": "hello"}
        assert assertion["where"]["count"] == {"eq": 5}

    def test_expected_changes_normalization_with_from_to(self):
        compiler = DSLCompiler()
        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "changed",
                    "entity": "channels",
                    "expected_changes": {
                        "topic": {
                            "from": "old topic",
                            "to": {"contains": "new"}
                        }
                    }
                }
            ]
        }
        normalized = compiler.normalize(spec)
        assertion = normalized["assertions"][0]

        assert assertion["expected_changes"]["topic"]["from"] == {"eq": "old topic"}
        assert assertion["expected_changes"]["topic"]["to"] == {"contains": "new"}

    def test_expected_changes_shorthand_to_only(self):
        compiler = DSLCompiler()
        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "changed",
                    "entity": "messages",
                    "expected_changes": {
                        "text": "Updated text"
                    }
                }
            ]
        }
        normalized = compiler.normalize(spec)
        assertion = normalized["assertions"][0]

        assert assertion["expected_changes"]["text"] == {"to": {"eq": "Updated text"}}

    def test_ignore_fields_preserved(self):
        compiler = DSLCompiler()
        spec = {
            "version": "0.1",
            "ignore_fields": {
                "global": ["created_at", "updated_at"],
                "messages": ["id"]
            },
            "assertions": [
                {
                    "diff_type": "added",
                    "entity": "messages",
                    "ignore": ["temp_field"]
                }
            ]
        }
        normalized = compiler.normalize(spec)

        assert normalized["ignore_fields"]["global"] == ["created_at", "updated_at"]
        assert normalized["ignore_fields"]["messages"] == ["id"]
        assert normalized["assertions"][0]["ignore"] == ["temp_field"]


class TestDSLCompile:
    def test_compile_validates_and_normalizes(self):
        compiler = DSLCompiler()
        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "added",
                    "entity": "messages",
                    "where": {
                        "channel_id": "C123"
                    }
                }
            ]
        }
        compiled = compiler.compile(spec)

        assert compiled["version"] == "0.1"
        assert compiled["assertions"][0]["where"]["channel_id"] == {"eq": "C123"}

    def test_compile_rejects_invalid_spec(self):
        compiler = DSLCompiler()
        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "invalid_type",
                    "entity": "messages"
                }
            ]
        }
        with pytest.raises(ValidationError):
            compiler.compile(spec)
