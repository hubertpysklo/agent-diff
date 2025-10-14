import pytest
from src.platform.evaluationEngine.compiler import DSLCompiler
from src.platform.evaluationEngine.assertion import AssertionEngine
from sqlalchemy import text


CHANNEL_GENERAL = "C01ABCD1234"
CHANNEL_RANDOM = "C02EFGH5678"
MESSAGE_1 = "1699564800.000123"
MESSAGE_2 = "1699568400.000456"
MESSAGE_3 = "1699572000.000789"


def execute_sql(engine, schema, sql):
    with engine.begin() as conn:
        conn.execute(text(sql.format(schema=schema)))


class TestAddedAssertions:
    def test_simple_insert_detection(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            INSERT INTO {schema}.messages (message_id, channel_id, user_id, message_text, created_at)
            VALUES ('M_NEW', 'C01ABCD1234', 'U01AGENBOT9', 'hello world', NOW())
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "added",
                    "entity": "messages",
                    "expected_count": 1
                }
            ]
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine_obj = AssertionEngine(compiled)
        result = engine_obj.evaluate(diff.model_dump())

        assert result["passed"] is True
        assert result["score"]["passed"] == 1

    def test_insert_with_where_filters(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            INSERT INTO {schema}.messages (message_id, channel_id, user_id, message_text, created_at)
            VALUES
                ('M_NEW_1', 'C01ABCD1234', 'U01AGENBOT9', 'hello world', NOW()),
                ('M_NEW_2', 'C02EFGH5678', 'U01AGENBOT9', 'goodbye world', NOW())
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "added",
                    "entity": "messages",
                    "where": {
                        "channel_id": "C01ABCD1234",
                        "message_text": {"contains": "hello"}
                    },
                    "expected_count": 1
                }
            ]
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine_obj = AssertionEngine(compiled)
        result = engine_obj.evaluate(diff.model_dump())

        assert result["passed"] is True

    def test_expected_count_range(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            INSERT INTO {schema}.messages (message_id, channel_id, user_id, message_text, created_at)
            VALUES
                ('M_1', 'C01ABCD1234', 'U01AGENBOT9', 'msg1', NOW()),
                ('M_2', 'C01ABCD1234', 'U01AGENBOT9', 'msg2', NOW()),
                ('M_3', 'C01ABCD1234', 'U01AGENBOT9', 'msg3', NOW())
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "added",
                    "entity": "messages",
                    "expected_count": {"min": 2, "max": 5}
                }
            ]
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine_obj = AssertionEngine(compiled)
        result = engine_obj.evaluate(diff.model_dump())

        assert result["passed"] is True

    def test_no_matches_fails_assertion(self, differ_env):
        differ = differ_env["differ"]
        differ.create_snapshot("before")
        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "added",
                    "entity": "messages",
                    "where": {"channel_id": "NONEXISTENT"},
                    "expected_count": 1
                }
            ]
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine_obj = AssertionEngine(compiled)
        result = engine_obj.evaluate(diff.model_dump())

        assert result["passed"] is False
        assert len(result["failures"]) == 1


class TestRemovedAssertions:
    def test_simple_delete_detection(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            DELETE FROM {schema}.messages WHERE message_id = '1699568400.000456'
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "removed",
                    "entity": "messages",
                    "where": {"message_id": MESSAGE_2},
                    "expected_count": 1
                }
            ]
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine_obj = AssertionEngine(compiled)
        result = engine_obj.evaluate(diff.model_dump())

        assert result["passed"] is True

    def test_delete_with_where_filters(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            DELETE FROM {schema}.messages WHERE channel_id = 'C01ABCD1234'
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "removed",
                    "entity": "messages",
                    "where": {"channel_id": CHANNEL_GENERAL},
                    "expected_count": {"min": 1}
                }
            ]
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine_obj = AssertionEngine(compiled)
        result = engine_obj.evaluate(diff.model_dump())

        assert result["passed"] is True

    def test_expected_count_validation(self, differ_env):
        differ = differ_env["differ"]
        differ.create_snapshot("before")
        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "removed",
                    "entity": "messages",
                    "expected_count": 1
                }
            ]
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine_obj = AssertionEngine(compiled)
        result = engine_obj.evaluate(diff.model_dump())

        assert result["passed"] is False


class TestChangedAssertions:
    def test_update_detection_with_expected_changes(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            UPDATE {schema}.channels
            SET topic_text = 'New weekly standup discussions'
            WHERE channel_id = 'C01ABCD1234'
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "changed",
                    "entity": "channels",
                    "where": {"channel_id": CHANNEL_GENERAL},
                    "expected_changes": {
                        "topic_text": {"to": {"contains": "standup"}}
                    }
                }
            ]
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine_obj = AssertionEngine(compiled)
        result = engine_obj.evaluate(diff.model_dump())

        assert result["passed"] is True

    def test_strict_mode_unexpected_field_fails(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            UPDATE {schema}.channels
            SET topic_text = 'New topic', purpose_text = 'New purpose'
            WHERE channel_id = 'C01ABCD1234'
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {
            "version": "0.1",
            "strict": True,
            "assertions": [
                {
                    "diff_type": "changed",
                    "entity": "channels",
                    "expected_changes": {
                        "topic_text": {"to": "New topic"}
                    }
                }
            ]
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine_obj = AssertionEngine(compiled)
        result = engine_obj.evaluate(diff.model_dump())

        assert result["passed"] is False

    def test_non_strict_mode_allows_extra_changes(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            UPDATE {schema}.channels
            SET topic_text = 'New topic', purpose_text = 'New purpose'
            WHERE channel_id = 'C01ABCD1234'
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {
            "version": "0.1",
            "strict": False,
            "assertions": [
                {
                    "diff_type": "changed",
                    "entity": "channels",
                    "expected_changes": {
                        "topic_text": {"to": "New topic"}
                    }
                }
            ]
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine_obj = AssertionEngine(compiled)
        result = engine_obj.evaluate(diff.model_dump())

        assert result["passed"] is True

    def test_from_to_predicates(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            UPDATE {schema}.channels
            SET topic_text = 'Updated discussions topic'
            WHERE channel_id = 'C01ABCD1234'
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "changed",
                    "entity": "channels",
                    "expected_changes": {
                        "topic_text": {
                            "from": {"contains": "announcements"},
                            "to": {"contains": "discussions"}
                        }
                    }
                }
            ]
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine_obj = AssertionEngine(compiled)
        result = engine_obj.evaluate(diff.model_dump())

        assert result["passed"] is True

    def test_ignore_fields_respected(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            UPDATE {schema}.messages
            SET message_text = 'Updated text', created_at = NOW()
            WHERE message_id = '1699564800.000123'
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {
            "version": "0.1",
            "ignore_fields": {
                "global": ["created_at"]
            },
            "assertions": [
                {
                    "diff_type": "changed",
                    "entity": "messages",
                    "expected_changes": {
                        "message_text": {"to": "Updated text"}
                    }
                }
            ]
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine_obj = AssertionEngine(compiled)
        result = engine_obj.evaluate(diff.model_dump())

        assert result["passed"] is True

    def test_multiple_field_changes(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            UPDATE {schema}.channels
            SET topic_text = 'New topic', purpose_text = 'New purpose'
            WHERE channel_id = 'C01ABCD1234'
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "changed",
                    "entity": "channels",
                    "expected_changes": {
                        "topic_text": {"to": "New topic"},
                        "purpose_text": {"to": "New purpose"}
                    }
                }
            ]
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine_obj = AssertionEngine(compiled)
        result = engine_obj.evaluate(diff.model_dump())

        assert result["passed"] is True


class TestUnchangedAssertions:
    def test_no_changes_passes(self, differ_env):
        differ = differ_env["differ"]
        differ.create_snapshot("before")
        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "unchanged",
                    "entity": "messages"
                }
            ]
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine_obj = AssertionEngine(compiled)
        result = engine_obj.evaluate(diff.model_dump())

        assert result["passed"] is True

    def test_any_change_fails_assertion(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            INSERT INTO {schema}.messages (message_id, channel_id, user_id, message_text, created_at)
            VALUES ('M_NEW', 'C01ABCD1234', 'U01AGENBOT9', 'test', NOW())
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "unchanged",
                    "entity": "messages"
                }
            ]
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine_obj = AssertionEngine(compiled)
        result = engine_obj.evaluate(diff.model_dump())

        assert result["passed"] is False


class TestSlackBenchScenarios:
    def test_slack_bench_test_1_send_message(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            INSERT INTO {schema}.messages (message_id, channel_id, user_id, message_text, created_at)
            VALUES ('M_HELLO', 'C01ABCD1234', 'U01AGENBOT9', 'hello everyone', NOW())
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "added",
                    "entity": "messages",
                    "where": {
                        "channel_id": {"eq": "C01ABCD1234"},
                        "message_text": {"contains": "hello"}
                    },
                    "expected_count": 1
                }
            ]
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine_obj = AssertionEngine(compiled)
        result = engine_obj.evaluate(diff.model_dump())

        assert result["passed"] is True

    def test_slack_bench_test_5_update_channel_topic(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            UPDATE {schema}.channels
            SET topic_text = 'Weekly standup discussions'
            WHERE channel_id = 'C01ABCD1234'
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "changed",
                    "entity": "channels",
                    "where": {"channel_id": {"eq": "C01ABCD1234"}},
                    "expected_changes": {
                        "topic_text": {"to": {"contains": "Weekly standup"}}
                    }
                }
            ]
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine_obj = AssertionEngine(compiled)
        result = engine_obj.evaluate(diff.model_dump())

        assert result["passed"] is True

    def test_slack_bench_test_10_delete_message(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            DELETE FROM {schema}.messages
            WHERE channel_id = 'C01ABCD1234' AND message_text LIKE '%deployment%'
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "removed",
                    "entity": "messages",
                    "where": {
                        "channel_id": {"eq": "C01ABCD1234"},
                        "message_text": {"contains": "deployment"}
                    },
                    "expected_count": 1
                }
            ]
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine_obj = AssertionEngine(compiled)
        result = engine_obj.evaluate(diff.model_dump())

        assert result["passed"] is True
