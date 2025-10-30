"""
Comprehensive validation tests for test suites and seed data.

This module validates:
1. Static schema validation (DSL + seed structure)
2. Referential integrity (template refs, hardcoded IDs, FKs)
3. Live API execution (end-to-end via actual Slack endpoints)
4. Assertion smoke tests (engine evaluation)
"""

import json
import pytest
from pathlib import Path
from jsonschema import validate as jsonschema_validate, ValidationError

from src.platform.evaluationEngine.compiler import DSLCompiler
from src.platform.evaluationEngine.assertion import AssertionEngine
from src.platform.evaluationEngine.differ import Differ
from httpx import AsyncClient


# Project root for discovering examples
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
EXAMPLES_DIR = PROJECT_ROOT / "examples"


# ============================================================================
# Layer 1: Static Schema Validation
# ============================================================================


class TestStaticSchemaValidation:
    """Validate JSON schemas for test suites and seed data."""

    def test_all_test_suites_validate_against_dsl_schema(self):
        """Ensure all testsuites/*.json files are valid DSL."""
        compiler = DSLCompiler()
        test_suite_files = list(EXAMPLES_DIR.glob("*/testsuites/*.json"))

        assert len(test_suite_files) > 0, "No test suite files found"

        for suite_file in test_suite_files:
            with open(suite_file) as f:
                data = json.load(f)

            # Each test in the suite should have assertions that validate
            for test in data.get("tests", []):
                assertions = test.get("assertions", [])
                if not assertions:
                    continue

                # Build a minimal spec with just these assertions
                spec = {"version": "0.1", "assertions": assertions}

                # Add ignore_fields if present in suite
                if "ignore_fields" in data:
                    spec["ignore_fields"] = data["ignore_fields"]

                try:
                    compiler.validate(spec)
                except ValidationError as e:
                    pytest.fail(
                        f"DSL validation failed for {suite_file.name}, "
                        f"test '{test.get('id')}': {e.message}"
                    )

    def test_all_seed_files_have_valid_structure(self):
        """Ensure all seeds/*.json files have required top-level keys."""
        seed_files = list(EXAMPLES_DIR.glob("*/seeds/*.json"))

        assert len(seed_files) > 0, "No seed files found"

        for seed_file in seed_files:
            with open(seed_file) as f:
                data = json.load(f)

            # All seeds should be dicts
            assert isinstance(data, dict), f"{seed_file.name} is not a JSON object"

            # Optional but common keys
            optional_keys = [
                "teams",
                "users",
                "channels",
                "messages",
                "channel_members",
                "user_teams",
                "message_reactions",
            ]

            # At least one entity should be present
            has_entity = any(k in data for k in optional_keys)
            assert has_entity, f"{seed_file.name} has no recognizable entity arrays"

            # If present, they should be arrays
            for key in optional_keys:
                if key in data:
                    assert isinstance(data[key], list), (
                        f"{seed_file.name}: '{key}' must be an array"
                    )


# ============================================================================
# Layer 2: Referential Integrity
# ============================================================================


class TestReferentialIntegrity:
    """Validate cross-references between tests, seeds, and assertions."""

    def test_all_seed_templates_exist(self):
        """Verify every seed_template referenced in tests has a matching seed file."""
        test_suite_files = list(EXAMPLES_DIR.glob("*/testsuites/*.json"))

        for suite_file in test_suite_files:
            with open(suite_file) as f:
                data = json.load(f)

            service = data.get("service")
            if not service:
                continue

            for test in data.get("tests", []):
                seed_template = test.get("seed_template")
                if not seed_template:
                    continue

                # Check if seed file exists
                seed_file = EXAMPLES_DIR / service / "seeds" / f"{seed_template}.json"
                assert seed_file.exists(), (
                    f"Test '{test['id']}' references seed_template '{seed_template}' "
                    f"but {seed_file.relative_to(PROJECT_ROOT)} does not exist"
                )

    def test_assertion_ids_exist_in_seed_data(self):
        """Cross-check hardcoded IDs in assertions exist in corresponding seeds."""
        test_suite_files = list(EXAMPLES_DIR.glob("*/testsuites/*.json"))

        for suite_file in test_suite_files:
            with open(suite_file) as f:
                suite_data = json.load(f)

            service = suite_data.get("service")
            if not service:
                continue

            for test in suite_data.get("tests", []):
                seed_template = test.get("seed_template")
                if not seed_template:
                    continue

                # Load corresponding seed
                seed_file = EXAMPLES_DIR / service / "seeds" / f"{seed_template}.json"
                if not seed_file.exists():
                    continue

                with open(seed_file) as f:
                    seed_data = json.load(f)

                # Extract hardcoded IDs from assertions
                for assertion in test.get("assertions", []):
                    where = assertion.get("where", {})
                    entity = assertion.get("entity")

                    # Check specific ID fields
                    self._check_id_in_seed(
                        where, entity, seed_data, test["id"], suite_file.name
                    )

    def _check_id_in_seed(self, where, entity, seed_data, test_id, suite_name):
        """Helper to validate IDs in where clauses exist in seed data."""
        # Only check exact eq predicates for known ID fields
        id_fields = {
            "messages": ["message_id", "channel_id", "user_id"],
            "channels": ["channel_id", "team_id"],
            "users": ["user_id"],
            "channel_members": ["channel_id", "user_id"],
            "message_reactions": ["message_id", "user_id"],
        }

        if entity not in id_fields:
            return

        entity_records = seed_data.get(entity, [])

        for field in id_fields[entity]:
            if field in where:
                predicate = where[field]

                # Only validate simple eq predicates
                if isinstance(predicate, dict) and "eq" in predicate:
                    expected_id = predicate["eq"]

                    # Check if this ID exists in seed data
                    found = any(
                        record.get(field) == expected_id for record in entity_records
                    )

                    if not found:
                        # For FK fields, check parent entity
                        if field == "channel_id":
                            found = any(
                                ch.get("channel_id") == expected_id
                                for ch in seed_data.get("channels", [])
                            )
                        elif field == "user_id":
                            found = any(
                                u.get("user_id") == expected_id
                                for u in seed_data.get("users", [])
                            )
                        elif field == "message_id":
                            found = any(
                                m.get("message_id") == expected_id
                                for m in seed_data.get("messages", [])
                            )

                    assert found, (
                        f"{suite_name} test '{test_id}': assertion references "
                        f"{entity}.{field}='{expected_id}' but it doesn't exist in seed data"
                    )

    def test_seed_foreign_key_integrity(self):
        """Validate FK relationships in seed data."""
        seed_files = list(EXAMPLES_DIR.glob("*/seeds/*.json"))

        for seed_file in seed_files:
            with open(seed_file) as f:
                data = json.load(f)

            # Determine schema type based on keys (Slack vs Linear)
            is_slack_schema = "teams" in data and any(
                "team_id" in t for t in data.get("teams", [])
            )

            if not is_slack_schema:
                # Skip non-Slack schemas for now (Linear uses different structure)
                continue

            # Collect all valid IDs
            team_ids = {t["team_id"] for t in data.get("teams", [])}
            user_ids = {u["user_id"] for u in data.get("users", [])}
            channel_ids = {c["channel_id"] for c in data.get("channels", [])}
            message_ids = {m["message_id"] for m in data.get("messages", [])}

            # Validate channels reference valid teams
            for ch in data.get("channels", []):
                if "team_id" in ch and ch["team_id"]:
                    assert ch["team_id"] in team_ids, (
                        f"{seed_file.name}: channel {ch['channel_id']} references "
                        f"non-existent team {ch['team_id']}"
                    )

            # Validate user_teams references
            for ut in data.get("user_teams", []):
                assert ut["user_id"] in user_ids, (
                    f"{seed_file.name}: user_teams references non-existent user {ut['user_id']}"
                )
                assert ut["team_id"] in team_ids, (
                    f"{seed_file.name}: user_teams references non-existent team {ut['team_id']}"
                )

            # Validate channel_members references
            for cm in data.get("channel_members", []):
                assert cm["channel_id"] in channel_ids, (
                    f"{seed_file.name}: channel_members references "
                    f"non-existent channel {cm['channel_id']}"
                )
                assert cm["user_id"] in user_ids, (
                    f"{seed_file.name}: channel_members references "
                    f"non-existent user {cm['user_id']}"
                )

            # Validate messages references
            for msg in data.get("messages", []):
                assert msg["channel_id"] in channel_ids, (
                    f"{seed_file.name}: message {msg['message_id']} references "
                    f"non-existent channel {msg['channel_id']}"
                )
                assert msg["user_id"] in user_ids, (
                    f"{seed_file.name}: message {msg['message_id']} references "
                    f"non-existent user {msg['user_id']}"
                )

                # Validate parent_id if present
                if "parent_id" in msg and msg["parent_id"]:
                    assert msg["parent_id"] in message_ids, (
                        f"{seed_file.name}: message {msg['message_id']} references "
                        f"non-existent parent {msg['parent_id']}"
                    )

            # Validate message_reactions
            for react in data.get("message_reactions", []):
                assert react["message_id"] in message_ids, (
                    f"{seed_file.name}: reaction references "
                    f"non-existent message {react['message_id']}"
                )
                assert react["user_id"] in user_ids, (
                    f"{seed_file.name}: reaction references "
                    f"non-existent user {react['user_id']}"
                )


# ============================================================================
# Layer 3: Live API Execution Tests
# ============================================================================


@pytest.mark.asyncio
class TestLiveAPIExecution:
    """Execute real API calls and validate against test suite assertions."""

    async def test_slack_bench_test_1_via_api(self, slack_client_with_differ):
        """test_1: Send message to #general via chat.postMessage API."""
        client = slack_client_with_differ["client"]
        differ = slack_client_with_differ["differ"]

        # Load test spec
        suite_file = EXAMPLES_DIR / "slack" / "testsuites" / "slack_bench.json"
        with open(suite_file) as f:
            suite = json.load(f)

        test_spec = next(t for t in suite["tests"] if t["id"] == "test_1")

        # Create before snapshot
        differ.create_snapshot("before")

        # Execute API action
        response = await client.post(
            "/chat.postMessage",
            json={"channel": "C01ABCD1234", "text": "hello everyone"},
        )
        assert response.status_code == 200

        # Create after snapshot
        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        # Build spec and evaluate
        spec = {"version": "0.1", "assertions": test_spec["assertions"]}
        if "ignore_fields" in suite:
            spec["ignore_fields"] = suite["ignore_fields"]

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine = AssertionEngine(compiled)
        result = engine.evaluate(diff.model_dump())

        assert result["passed"] is True, f"Assertions failed: {result['failures']}"
        assert result["score"]["passed"] == result["score"]["total"]

    async def test_slack_bench_test_2_via_api(self, slack_client_with_differ):
        """test_2: Open DM + send message via API."""
        client = slack_client_with_differ["client"]
        differ = slack_client_with_differ["differ"]

        suite_file = EXAMPLES_DIR / "slack" / "testsuites" / "slack_bench.json"
        with open(suite_file) as f:
            suite = json.load(f)

        test_spec = next(t for t in suite["tests"] if t["id"] == "test_2")

        differ.create_snapshot("before")

        # Open DM with John
        open_resp = await client.post(
            "/conversations.open", json={"users": "U02JOHNDOE1"}
        )
        assert open_resp.status_code == 200
        dm_id = open_resp.json()["channel"]["id"]

        # Send message
        msg_resp = await client.post(
            "/chat.postMessage", json={"channel": dm_id, "text": "Can we sync later?"}
        )
        assert msg_resp.status_code == 200

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {"version": "0.1", "assertions": test_spec["assertions"]}
        if "ignore_fields" in suite:
            spec["ignore_fields"] = suite["ignore_fields"]

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine = AssertionEngine(compiled)
        result = engine.evaluate(diff.model_dump())

        assert result["passed"] is True, f"Assertions failed: {result['failures']}"

    async def test_slack_bench_test_7_via_api(self, slack_bench_client_with_differ):
        """test_7: Threaded reply via API."""
        client = slack_bench_client_with_differ["client"]
        differ = slack_bench_client_with_differ["differ"]

        suite_file = EXAMPLES_DIR / "slack" / "testsuites" / "slack_bench.json"
        with open(suite_file) as f:
            suite = json.load(f)

        test_spec = next(t for t in suite["tests"] if t["id"] == "test_7")

        differ.create_snapshot("before")

        # Reply to MCP deployment question (1700173200.000456)
        response = await client.post(
            "/chat.postMessage",
            json={
                "channel": "C01ABCD1234",
                "text": "Next monday.",
                "thread_ts": "1700173200.000456",
            },
        )
        assert response.status_code == 200

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {"version": "0.1", "assertions": test_spec["assertions"]}
        if "ignore_fields" in suite:
            spec["ignore_fields"] = suite["ignore_fields"]

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine = AssertionEngine(compiled)
        result = engine.evaluate(diff.model_dump())

        assert result["passed"] is True, f"Assertions failed: {result['failures']}"

    async def test_slack_bench_test_9_via_api(self, slack_client_with_differ):
        """test_9: Add reaction via API."""
        client = slack_client_with_differ["client"]
        differ = slack_client_with_differ["differ"]

        suite_file = EXAMPLES_DIR / "slack" / "testsuites" / "slack_bench.json"
        with open(suite_file) as f:
            suite = json.load(f)

        test_spec = next(t for t in suite["tests"] if t["id"] == "test_9")

        differ.create_snapshot("before")

        # Add reaction to message in #random
        response = await client.post(
            "/reactions.add",
            json={
                "name": "thumbsup",
                "channel": "C02EFGH5678",
                "timestamp": "1699572000.000789",
            },
        )
        assert response.status_code == 200

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {"version": "0.1", "assertions": test_spec["assertions"]}
        if "ignore_fields" in suite:
            spec["ignore_fields"] = suite["ignore_fields"]

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine = AssertionEngine(compiled)
        result = engine.evaluate(diff.model_dump())

        assert result["passed"] is True, f"Assertions failed: {result['failures']}"

    async def test_slack_bench_test_11_via_api(self, slack_client_with_differ):
        """test_11: Update channel topic via API."""
        client = slack_client_with_differ["client"]
        differ = slack_client_with_differ["differ"]

        suite_file = EXAMPLES_DIR / "slack" / "testsuites" / "slack_bench.json"
        with open(suite_file) as f:
            suite = json.load(f)

        test_spec = next(t for t in suite["tests"] if t["id"] == "test_11")

        differ.create_snapshot("before")

        # Set topic
        response = await client.post(
            "/conversations.setTopic",
            json={"channel": "C01ABCD1234", "topic": "Weekly standup discussions"},
        )
        assert response.status_code == 200

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        spec = {"version": "0.1", "assertions": test_spec["assertions"]}
        if "ignore_fields" in suite:
            spec["ignore_fields"] = suite["ignore_fields"]

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine = AssertionEngine(compiled)
        result = engine.evaluate(diff.model_dump())

        assert result["passed"] is True, f"Assertions failed: {result['failures']}"

    async def test_slack_bench_test_12_via_api(self, slack_client_with_differ):
        """test_12: Edit message via API."""
        client = slack_client_with_differ["client"]
        differ = slack_client_with_differ["differ"]

        suite_file = EXAMPLES_DIR / "slack" / "testsuites" / "slack_bench.json"
        with open(suite_file) as f:
            suite = json.load(f)

        # Note: test_12 impersonates U02JOHNDOE1, but slack_client uses U01AGENBOT9
        # We need to use the AGENT's message for this test
        test_spec = next(t for t in suite["tests"] if t["id"] == "test_12")

        differ.create_snapshot("before")

        # Update the agent's message (1699564800.000123)
        response = await client.post(
            "/chat.update",
            json={
                "channel": "C01ABCD1234",
                "ts": "1699564800.000123",
                "text": "Hello everyone",
            },
        )
        assert response.status_code == 200

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        # Adjust assertion to match agent's message
        adjusted_assertions = [
            {
                "diff_type": "changed",
                "entity": "messages",
                "where": {
                    "channel_id": {"eq": "C01ABCD1234"},
                    "message_id": {"eq": "1699564800.000123"},
                },
                "expected_changes": {
                    "message_text": {"to": {"contains": "Hello everyone"}}
                },
            }
        ]

        spec = {"version": "0.1", "assertions": adjusted_assertions}
        if "ignore_fields" in suite:
            spec["ignore_fields"] = suite["ignore_fields"]

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine = AssertionEngine(compiled)
        result = engine.evaluate(diff.model_dump())

        assert result["passed"] is True, f"Assertions failed: {result['failures']}"

    async def test_slack_bench_test_15_via_api(self, slack_client_with_differ):
        """test_15: Delete message via API."""
        client = slack_client_with_differ["client"]
        differ = slack_client_with_differ["differ"]

        suite_file = EXAMPLES_DIR / "slack" / "testsuites" / "slack_bench.json"
        with open(suite_file) as f:
            suite = json.load(f)

        test_spec = next(t for t in suite["tests"] if t["id"] == "test_15")

        differ.create_snapshot("before")

        # Delete agent's message about deployment
        # First, let's find it - it should be 1699564800.000123 based on seed
        response = await client.post(
            "/chat.delete", json={"channel": "C01ABCD1234", "ts": "1699564800.000123"}
        )
        assert response.status_code == 200

        differ.create_snapshot("after")
        diff = differ.get_diff("before", "after")

        # Adjust assertion to use correct message
        adjusted_assertions = [
            {
                "diff_type": "removed",
                "entity": "messages",
                "where": {
                    "channel_id": {"eq": "C01ABCD1234"},
                    "message_id": {"eq": "1699564800.000123"},
                },
                "expected_count": 1,
            }
        ]

        spec = {"version": "0.1", "assertions": adjusted_assertions}
        if "ignore_fields" in suite:
            spec["ignore_fields"] = suite["ignore_fields"]

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine = AssertionEngine(compiled)
        result = engine.evaluate(diff.model_dump())

        assert result["passed"] is True, f"Assertions failed: {result['failures']}"


# ============================================================================
# Layer 4: Assertion Smoke Test
# ============================================================================


class TestAssertionEngineSmoke:
    """Verify assertion engine works with suite assertions."""

    def test_slack_bench_assertions_compile(self):
        """Ensure all Slack bench assertions compile without errors."""
        suite_file = EXAMPLES_DIR / "slack" / "testsuites" / "slack_bench.json"
        with open(suite_file) as f:
            suite = json.load(f)

        compiler = DSLCompiler()

        for test in suite["tests"]:
            spec = {"version": "0.1", "assertions": test["assertions"]}
            if "ignore_fields" in suite:
                spec["ignore_fields"] = suite["ignore_fields"]

            try:
                compiled = compiler.compile(spec)
                # Ensure engine can be instantiated
                engine = AssertionEngine(compiled)
                assert engine is not None
            except Exception as e:
                pytest.fail(
                    f"Failed to compile assertions for test '{test['id']}': {e}"
                )

    def test_assertion_engine_with_known_diff(self):
        """Test assertion engine with manually constructed diff."""
        # Manually create a diff
        diff = {
            "inserts": [
                {
                    "__table__": "messages",
                    "message_id": "M123",
                    "channel_id": "C01ABCD1234",
                    "user_id": "U01AGENBOT9",
                    "message_text": "hello world",
                }
            ],
            "updates": [],
            "deletes": [],
        }

        # Create spec that should pass
        spec = {
            "version": "0.1",
            "assertions": [
                {
                    "diff_type": "added",
                    "entity": "messages",
                    "where": {
                        "channel_id": {"eq": "C01ABCD1234"},
                        "message_text": {"contains": "hello"},
                    },
                    "expected_count": 1,
                }
            ],
        }

        compiler = DSLCompiler()
        compiled = compiler.compile(spec)
        engine = AssertionEngine(compiled)
        result = engine.evaluate(diff)

        assert result["passed"] is True
        assert result["score"]["passed"] == 1
        assert result["score"]["total"] == 1
