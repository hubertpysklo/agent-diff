"""Integration tests for environment lifecycle management."""

import time
import pytest
from sqlalchemy import text
from datetime import datetime, timedelta

from src.platform.db.schema import RunTimeEnvironment
from src.services.slack.database.schema import User, Channel, Message


def test_create_environment_creates_schema(test_user_id, 
    core_isolation_engine, session_manager, cleanup_test_environments
):
    
    result = core_isolation_engine.create_environment(
        template_schema="slack_default",
        ttl_seconds=3600,
        created_by=test_user_id,
    )

    schema_name = result.schema_name
    assert schema_name.startswith("state_")

    with session_manager.base_engine.begin() as conn:
        exists = conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.schemata
                    WHERE schema_name = :schema
                )
            """),
            {"schema": schema_name},
        ).scalar()

    assert exists is True


def test_environment_copies_table_structure(
    test_user_id, core_isolation_engine, session_manager, cleanup_test_environments
):
    
    result = core_isolation_engine.create_environment(
        template_schema="slack_default",
        ttl_seconds=3600,
        created_by=test_user_id,
    )

    schema_name = result.schema_name

    with session_manager.base_engine.begin() as conn:
        result = conn.execute(
            text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = :schema
                ORDER BY table_name
            """),
            {"schema": schema_name},
        )
        tables = {row[0] for row in result}

    expected_tables = {
        "users",
        "teams",
        "channels",
        "messages",
        "channel_members",
        "message_reactions",
        "user_teams",
    }
    assert expected_tables.issubset(tables)


def test_environment_seeds_data(
    test_user_id, core_isolation_engine, session_manager, cleanup_test_environments
):
    
    result = core_isolation_engine.create_environment(
        template_schema="slack_default",
        ttl_seconds=3600,
        created_by=test_user_id,
    )

    schema_name = result.schema_name

    with session_manager.with_session_for_schema(schema_name) as session:
        users = session.query(User).all()
        assert len(users) == 3

        channels = session.query(Channel).all()
        assert len(channels) == 2

        messages = session.query(Message).all()
        assert len(messages) == 3

        agent_user = session.query(User).filter(User.user_id == "U01AGENBOT9").first()
        assert agent_user is not None
        assert agent_user.username == "agent1"


def test_environment_isolation(
    test_user_id, core_isolation_engine, session_manager, cleanup_test_environments
):
    
    # Create two environments
    env1 = core_isolation_engine.create_environment(
        template_schema="slack_default",
        ttl_seconds=3600,
        created_by=test_user_id,
    )
    env2 = core_isolation_engine.create_environment(
        template_schema="slack_default",
        ttl_seconds=3600,
        created_by=test_user_id,
    )

    with session_manager.with_session_for_schema(env1.schema_name) as session:
        user = session.query(User).filter(User.user_id == "U01AGENBOT9").first()
        user.real_name = "Modified in Env1"
        session.commit()

    with session_manager.with_session_for_schema(env2.schema_name) as session:
        user = session.query(User).filter(User.user_id == "U01AGENBOT9").first()
        assert user.real_name == "AI Agent"  # Original value


def test_session_manager_routes_to_correct_schema(
    test_user_id, core_isolation_engine, session_manager, cleanup_test_environments
):
    
    env = core_isolation_engine.create_environment(
        template_schema="slack_default",
        ttl_seconds=3600,
        created_by=test_user_id,
    )

    with session_manager.with_session_for_environment(env.environment_id) as session:
        users = session.query(User).all()
        assert len(users) == 3

        user = users[0]
        original_name = user.real_name
        user.real_name = "Test Modified Name"
        session.commit()

    with session_manager.with_session_for_environment(env.environment_id) as session:
        user = session.query(User).filter(User.user_id == users[0].user_id).first()
        assert user.real_name == "Test Modified Name"


def test_concurrent_environment_access(
    test_user_id, core_isolation_engine, session_manager, cleanup_test_environments
):
    
    # Create three environments
    envs = [
        core_isolation_engine.create_environment(
            template_schema="slack_default",
            ttl_seconds=3600,
            created_by=test_user_id,
        )
        for _ in range(3)
    ]

    # Set unique name in each environment
    for idx, env in enumerate(envs):
        with session_manager.with_session_for_environment(env.environment_id) as session:
            user = session.query(User).filter(User.user_id == "U01AGENBOT9").first()
            user.real_name = f"User in Env{idx}"
            session.commit()

    for idx, env in enumerate(envs):
        with session_manager.with_session_for_environment(env.environment_id) as session:
            user = session.query(User).filter(User.user_id == "U01AGENBOT9").first()
            assert user.real_name == f"User in Env{idx}"


def test_runtime_environment_tracking(
    test_user_id, core_isolation_engine, session_manager, cleanup_test_environments
):
    
    result = core_isolation_engine.create_environment(
        template_schema="slack_default",
        ttl_seconds=3600,
        created_by=test_user_id,
        impersonate_user_id="U01AGENBOT9",
        impersonate_email="agent@example.com",
    )

    with session_manager.with_meta_session() as session:
        env = (
            session.query(RunTimeEnvironment)
            .filter(RunTimeEnvironment.id == result.environment_id)
            .first()
        )

        assert env is not None
        assert env.schema == result.schema_name
        assert env.status == "ready"
        assert env.impersonate_user_id == "U01AGENBOT9"
        assert env.impersonate_email == "agent@example.com"
        assert env.expires_at is not None
        assert env.last_used_at is not None


def test_lookup_updates_last_used_at(
    test_user_id, core_isolation_engine, session_manager, cleanup_test_environments
):
    
    result = core_isolation_engine.create_environment(
        template_schema="slack_default",
        ttl_seconds=3600,
        created_by=test_user_id,
    )

    with session_manager.with_meta_session() as session:
        env = (
            session.query(RunTimeEnvironment)
            .filter(RunTimeEnvironment.id == result.environment_id)
            .first()
        )
        initial_last_used = env.last_used_at

    # Wait a moment
    time.sleep(0.1)

    schema, last_used = session_manager.lookup_environment(result.environment_id)

    assert schema == result.schema_name
    assert last_used > initial_last_used


def test_drop_schema_cleanup(
    test_user_id, core_isolation_engine, environment_handler, session_manager
):
    
    result = core_isolation_engine.create_environment(
        template_schema="slack_default",
        ttl_seconds=3600,
        created_by=test_user_id,
    )

    schema_name = result.schema_name

    with session_manager.base_engine.begin() as conn:
        exists_before = conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.schemata
                    WHERE schema_name = :schema
                )
            """),
            {"schema": schema_name},
        ).scalar()
    assert exists_before is True

    environment_handler.drop_schema(schema_name)

    with session_manager.base_engine.begin() as conn:
        exists_after = conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.schemata
                    WHERE schema_name = :schema
                )
            """),
            {"schema": schema_name},
        ).scalar()
    assert exists_after is False
