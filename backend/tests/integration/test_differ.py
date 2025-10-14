"""Integration tests for Differ using slack_bench scenarios via raw SQL."""

import pytest
from sqlalchemy import text
from src.platform.evaluationEngine.differ import Differ
from src.platform.db.schema import Diff

MESSAGE_1 = "1699564800.000123"
MESSAGE_2 = "1699568400.000456"
MESSAGE_3 = "1699572000.000789"
CHANNEL_GENERAL = "C01ABCD1234"
CHANNEL_RANDOM = "C02EFGH5678"
USER_AGENT = "U01AGENBOT9"
USER_JOHN = "U02JOHNDOE1"
USER_ROBERT = "U03ROBERT23"


def execute_sql(engine, schema, sql):
    """Execute raw SQL in environment schema."""
    with engine.begin() as conn:
        conn.execute(text(sql.format(schema=schema)))


def query_count(engine, table_path):
    """Get row count from table."""
    with engine.begin() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {table_path}")).scalar()


def query_tables(engine, schema, pattern):
    """Get list of tables matching pattern."""
    with engine.begin() as conn:
        result = conn.execute(text(f"""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = '{schema}' AND table_name LIKE '{pattern}'
        """))
        return [row[0] for row in result]


class TestDifferInserts:
    def test_diff_insert_message_to_channel(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            INSERT INTO {schema}.messages (message_id, channel_id, user_id, message_text, created_at)
            VALUES ('M_NEW_1', 'C01ABCD1234', 'U01AGENBOT9', 'hello from test', NOW())
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        assert len(diff.inserts) == 1
        assert diff.inserts[0]["__table__"] == "messages"
        assert diff.inserts[0]["channel_id"] == CHANNEL_GENERAL
        assert "hello" in diff.inserts[0]["message_text"]
        assert len(diff.updates) == 0
        assert len(diff.deletes) == 0

    def test_diff_insert_new_channel(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            INSERT INTO {schema}.channels (channel_id, channel_name, team_id, is_private, created_at)
            VALUES ('C_NEW_1', 'project-alpha', 'T01WORKSPACE', false, NOW())
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        assert len(diff.inserts) == 1
        assert diff.inserts[0]["__table__"] == "channels"
        assert diff.inserts[0]["channel_name"] == "project-alpha"

    def test_diff_insert_threaded_reply(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            INSERT INTO {schema}.messages (message_id, channel_id, user_id, message_text, parent_id, created_at)
            VALUES ('M_REPLY_1', 'C01ABCD1234', 'U01AGENBOT9', 'Next monday.', '1699568400.000456', NOW())
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        assert len(diff.inserts) == 1
        assert diff.inserts[0]["__table__"] == "messages"
        assert diff.inserts[0]["parent_id"] == MESSAGE_2
        assert "Next monday" in diff.inserts[0]["message_text"]

    def test_diff_insert_reaction(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            INSERT INTO {schema}.message_reactions (message_id, user_id, reaction_type, created_at)
            VALUES ('1699568400.000456', 'U01AGENBOT9', 'thumbsup', NOW())
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        assert len(diff.inserts) == 1
        assert diff.inserts[0]["__table__"] == "message_reactions"
        assert diff.inserts[0]["message_id"] == MESSAGE_2
        assert diff.inserts[0]["user_id"] == USER_AGENT
        assert diff.inserts[0]["reaction_type"] == "thumbsup"

    def test_diff_insert_dm_and_message(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            INSERT INTO {schema}.channels (channel_id, channel_name, team_id, is_private, is_dm, created_at)
            VALUES ('DM_NEW_1', 'dm-U01AGENBOT9-U02JOHNDOE1', 'T01WORKSPACE', true, true, NOW())
        """)

        execute_sql(engine, schema, """
            INSERT INTO {schema}.messages (message_id, channel_id, user_id, message_text, created_at)
            VALUES ('M_DM_1', 'DM_NEW_1', 'U01AGENBOT9', 'Can we sync later?', NOW())
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        assert len(diff.inserts) == 2
        channel_insert = [i for i in diff.inserts if i["__table__"] == "channels"][0]
        message_insert = [i for i in diff.inserts if i["__table__"] == "messages"][0]

        assert channel_insert["is_dm"] is True
        assert "sync later" in message_insert["message_text"]

    def test_diff_insert_mention_message(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            INSERT INTO {schema}.messages (message_id, channel_id, user_id, message_text, created_at)
            VALUES ('M_MENTION_1', 'C01ABCD1234', 'U01AGENBOT9', '@johndoe Please review the pull request', NOW())
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        assert len(diff.inserts) == 1
        assert diff.inserts[0]["__table__"] == "messages"
        assert "@johndoe" in diff.inserts[0]["message_text"]

    def test_diff_insert_multiple_channels(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            INSERT INTO {schema}.messages (message_id, channel_id, user_id, message_text, created_at)
            VALUES
                ('M_MULTI_1', 'C01ABCD1234', 'U01AGENBOT9', 'System maintenance tonight at 10pm', NOW()),
                ('M_MULTI_2', 'C02EFGH5678', 'U01AGENBOT9', 'System maintenance tonight at 10pm', NOW())
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        assert len(diff.inserts) == 2
        message_inserts = [i for i in diff.inserts if i["__table__"] == "messages"]
        assert len(message_inserts) == 2
        assert all("maintenance" in m["message_text"] for m in message_inserts)
        channels = {m["channel_id"] for m in message_inserts}
        assert channels == {CHANNEL_GENERAL, CHANNEL_RANDOM}


class TestDifferUpdates:
    def test_diff_update_channel_topic(self, differ_env):
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

        assert len(diff.updates) == 1
        assert diff.updates[0]["__table__"] == "channels"
        assert diff.updates[0]["after"]["channel_id"] == CHANNEL_GENERAL
        assert "Weekly standup" in diff.updates[0]["after"]["topic_text"]
        assert diff.updates[0]["before"]["topic_text"] != diff.updates[0]["after"]["topic_text"]

    def test_diff_update_message_text(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            UPDATE {schema}.messages
            SET message_text = 'Hello everyone'
            WHERE message_id = '1699564800.000123'
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        assert len(diff.updates) == 1
        assert diff.updates[0]["__table__"] == "messages"
        assert diff.updates[0]["after"]["message_id"] == MESSAGE_1
        assert "Hello everyone" in diff.updates[0]["after"]["message_text"]
        assert diff.updates[0]["before"]["message_text"] != diff.updates[0]["after"]["message_text"]

    def test_diff_update_with_exclude_cols(self, differ_env):
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
        diff_with_exclude = differ.get_updates("before", "after", exclude_cols=["created_at"])

        assert len(diff_with_exclude) == 1
        assert diff_with_exclude[0]["after"]["message_text"] == "Updated text"

    def test_diff_update_null_handling(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            UPDATE {schema}.channels
            SET purpose_text = 'New purpose'
            WHERE channel_id = 'C01ABCD1234'
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        assert len(diff.updates) == 1
        assert diff.updates[0]["before"]["purpose_text"] == "This channel is for team-wide communication and announcements."
        assert diff.updates[0]["after"]["purpose_text"] == "New purpose"


class TestDifferDeletes:
    def test_diff_delete_message(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            DELETE FROM {schema}.messages
            WHERE message_id = '1699568400.000456'
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        assert len(diff.deletes) == 1
        assert diff.deletes[0]["__table__"] == "messages"
        assert diff.deletes[0]["message_id"] == MESSAGE_2

    def test_diff_delete_channel_cascade(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            DELETE FROM {schema}.messages WHERE channel_id = 'C02EFGH5678';
            DELETE FROM {schema}.channel_members WHERE channel_id = 'C02EFGH5678';
            DELETE FROM {schema}.channels WHERE channel_id = 'C02EFGH5678';
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        channel_deletes = [d for d in diff.deletes if d["__table__"] == "channels"]
        message_deletes = [d for d in diff.deletes if d["__table__"] == "messages"]
        assert len(channel_deletes) == 1
        assert channel_deletes[0]["channel_id"] == CHANNEL_RANDOM
        assert len(message_deletes) >= 1

    def test_diff_delete_no_changes(self, differ_env):
        differ = differ_env["differ"]

        differ.create_snapshot("before")
        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        assert len(diff.deletes) == 0


class TestSnapshotManagement:
    def test_create_snapshot_creates_tables(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("test_snapshot")

        tables = query_tables(engine, schema, "%_snapshot_test_snapshot")
        expected = [
            "users_snapshot_test_snapshot",
            "channels_snapshot_test_snapshot",
            "messages_snapshot_test_snapshot",
            "teams_snapshot_test_snapshot",
            "channel_members_snapshot_test_snapshot",
            "message_reactions_snapshot_test_snapshot",
            "user_teams_snapshot_test_snapshot",
        ]
        assert set(expected).issubset(set(tables))

    def test_create_snapshot_copies_data(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("copy_test")

        for table in ["messages", "channels", "users"]:
            orig_count = query_count(engine, f"{schema}.{table}")
            snap_count = query_count(engine, f"{schema}.{table}_snapshot_copy_test")
            assert orig_count == snap_count

    def test_archive_snapshots_drops_tables(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("to_archive")
        differ.archive_snapshots("to_archive")

        tables = query_tables(engine, schema, "%_snapshot_to_archive")
        assert len(tables) == 0

    def test_snapshot_isolation(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        original_count = query_count(engine, f"{schema}.messages")
        differ.create_snapshot("isolated")

        execute_sql(engine, schema, """
            INSERT INTO {schema}.messages (message_id, channel_id, user_id, message_text, created_at)
            VALUES ('M_ISOLATED', 'C01ABCD1234', 'U01AGENBOT9', 'New message', NOW())
        """)

        snap_count = query_count(engine, f"{schema}.messages_snapshot_isolated")
        assert snap_count == original_count


class TestComplexScenarios:
    def test_diff_combined_operations(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            INSERT INTO {schema}.messages (message_id, channel_id, user_id, message_text, created_at)
            VALUES ('M_FWD', 'C01ABCD1234', 'U01AGENBOT9', 'Anyone up for lunch?', NOW())
        """)

        execute_sql(engine, schema, """
            UPDATE {schema}.messages
            SET message_text = '[Forwarded to general]'
            WHERE message_id = '1699572000.000789'
        """)

        execute_sql(engine, schema, """
            DELETE FROM {schema}.messages
            WHERE message_id = '1699564800.000123'
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        assert len(diff.inserts) > 0
        assert len(diff.updates) > 0
        assert len(diff.deletes) > 0

    def test_diff_realistic_agent_workflow(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            INSERT INTO {schema}.channels (channel_id, channel_name, team_id, is_private, created_at)
            VALUES ('C_AGENT', 'agent-workspace', 'T01WORKSPACE', false, NOW())
        """)

        execute_sql(engine, schema, """
            INSERT INTO {schema}.messages (message_id, channel_id, user_id, message_text, created_at)
            VALUES ('M_AGENT_1', 'C_AGENT', 'U01AGENBOT9', 'Project started', NOW())
        """)

        execute_sql(engine, schema, """
            INSERT INTO {schema}.message_reactions (message_id, user_id, reaction_type, created_at)
            VALUES ('M_AGENT_1', 'U01AGENBOT9', 'rocket', NOW())
        """)

        differ.create_snapshot("mid")

        execute_sql(engine, schema, """
            UPDATE {schema}.channels
            SET topic_text = 'Agent workspace for task X'
            WHERE channel_id = 'C_AGENT'
        """)

        execute_sql(engine, schema, """
            DELETE FROM {schema}.messages
            WHERE message_id = '1699572000.000789'
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("mid", "after")

        assert len(diff.inserts) == 0
        assert len(diff.updates) == 1
        assert len(diff.deletes) == 1


class TestDiffStorage:
    def test_store_diff_persists_to_database(self, differ_env):
        differ = differ_env["differ"]
        schema = differ_env["schema"]
        engine = differ_env["engine"]
        env_id = differ_env["env_id"]
        session_manager = differ_env["session_manager"]

        differ.create_snapshot("before")

        execute_sql(engine, schema, """
            INSERT INTO {schema}.messages (message_id, channel_id, user_id, message_text, created_at)
            VALUES ('M_STORE', 'C01ABCD1234', 'U01AGENBOT9', 'Test message', NOW())
        """)

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")
        differ.store_diff(diff, "before", "after")

        with session_manager.with_meta_session() as session:
            stored = session.query(Diff).filter(Diff.environment_id == env_id).first()
            assert stored is not None
            assert stored.before_suffix == "before"
            assert stored.after_suffix == "after"
            assert len(stored.diff["inserts"]) == len(diff.inserts)
            assert len(stored.diff["updates"]) == len(diff.updates)
            assert len(stored.diff["deletes"]) == len(diff.deletes)
