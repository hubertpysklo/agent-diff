"""Integration tests for SDK client (agent_diff.client.AgentDiff).

Tests verify:
1. API responses match expected schemas
2. Database state reflects operations
3. Authorization and error handling
"""

import pytest
from uuid import UUID

from src.platform.db.schema import (
    TemplateEnvironment,
    TestSuite as DBTestSuite,
    Test as DBTest,
    TestMembership,
    RunTimeEnvironment,
    TestRun,
)


class TestTemplateOperations:
    """Test SDK template listing and retrieval."""

    def test_list_templates_returns_public_templates(
        self, sdk_client, session_manager, cleanup_test_environments
    ):
        """List templates should return all public templates visible to user."""
        resp = sdk_client.list_templates()

        assert resp.templates is not None
        assert isinstance(resp.templates, list)

        # Verify we get slack and linear templates registered during seeding
        template_names = {t.name for t in resp.templates}
        assert "slack_base" in template_names or "slack_default" in template_names

        # Each template should have required fields
        for tmpl in resp.templates:
            assert isinstance(tmpl.id, UUID)
            assert tmpl.service in ["slack", "linear"]
            assert tmpl.name is not None

    def test_get_template_by_id_success(
        self, sdk_client, session_manager, cleanup_test_environments
    ):
        """Get template by ID should return full template detail."""
        # First, list to get a valid template ID
        templates = sdk_client.list_templates()
        assert len(templates.templates) > 0
        template_id = templates.templates[0].id

        # Fetch detail
        detail = sdk_client.get_template(template_id)

        assert detail.id == template_id
        assert detail.version is not None
        assert detail.schemaName is not None

        # Verify in DB
        with session_manager.with_meta_session() as s:
            tmpl = (
                s.query(TemplateEnvironment)
                .filter(TemplateEnvironment.id == template_id)
                .one()
            )
            assert tmpl.location == detail.schemaName
            assert tmpl.version == detail.version

    def test_get_template_not_found(self, sdk_client):
        """Get template with invalid UUID should raise 404."""
        from uuid import uuid4
        import requests

        nonexistent_id = uuid4()
        with pytest.raises(requests.HTTPError) as exc_info:
            sdk_client.get_template(nonexistent_id)

        assert exc_info.value.response.status_code == 404


class TestEnvironmentOperations:
    """Test SDK environment initialization and lifecycle."""

    def test_init_env_by_template_id(
        self, sdk_client, session_manager, cleanup_test_environments
    ):
        """Init environment by templateId should create runtime environment."""
        from agent_diff.models import InitEnvRequestBody

        # Get a template ID
        templates = sdk_client.list_templates()
        template = next((t for t in templates.templates if t.service == "slack"), None)
        assert template is not None, "No slack template found"

        # Initialize environment
        req = InitEnvRequestBody(
            templateId=template.id,
            impersonateUserId="U01TEST1234",
            ttlSeconds=600,
        )
        resp = sdk_client.init_env(req)

        assert resp.environmentId is not None
        assert resp.service == "slack"
        assert resp.environmentUrl is not None
        assert resp.expiresAt is not None

        # Verify in DB
        with session_manager.with_meta_session() as s:
            env = (
                s.query(RunTimeEnvironment)
                .filter(RunTimeEnvironment.id == resp.environmentId)
                .one()
            )
            assert env.status == "ready"
            assert env.impersonate_user_id == "U01TEST1234"
            assert env.schema.startswith("state_")

    def test_init_env_by_service_and_name(
        self, sdk_client, session_manager, cleanup_test_environments
    ):
        """Init environment by templateService + templateName."""
        from agent_diff.models import InitEnvRequestBody

        req = InitEnvRequestBody(
            templateService="slack",
            templateName="slack_default",
            impersonateUserId="U01TEST5678",
            ttlSeconds=600,
        )
        resp = sdk_client.init_env(req)

        assert resp.environmentId is not None
        assert resp.service == "slack"

        # Verify in DB
        with session_manager.with_meta_session() as s:
            env = (
                s.query(RunTimeEnvironment)
                .filter(RunTimeEnvironment.id == resp.environmentId)
                .one()
            )
            assert env.status == "ready"
            assert env.impersonate_user_id == "U01TEST5678"

    def test_init_env_legacy_template_schema(
        self, sdk_client, session_manager, cleanup_test_environments
    ):
        """Init environment by legacy templateSchema."""
        from agent_diff.models import InitEnvRequestBody

        req = InitEnvRequestBody(
            templateSchema="slack_default",
            impersonateUserId="U01LEGACY99",
            ttlSeconds=600,
        )
        resp = sdk_client.init_env(req)

        assert resp.environmentId is not None
        assert resp.templateSchema == "slack_default"

        # Verify in DB
        with session_manager.with_meta_session() as s:
            env = (
                s.query(RunTimeEnvironment)
                .filter(RunTimeEnvironment.id == resp.environmentId)
                .one()
            )
            assert env.status == "ready"

    def test_init_env_missing_impersonate_fails(self, sdk_client):
        """Init env without impersonation should fail when no testId."""
        from agent_diff.models import InitEnvRequestBody
        import requests

        req = InitEnvRequestBody(
            templateService="slack",
            templateName="slack_default",
            ttlSeconds=600,
        )
        with pytest.raises(requests.HTTPError) as exc_info:
            sdk_client.init_env(req)

        assert exc_info.value.response.status_code == 400

    def test_delete_env_success(
        self, sdk_client, session_manager, cleanup_test_environments
    ):
        """Delete environment should mark it deleted and drop schema."""
        from agent_diff.models import InitEnvRequestBody
        from sqlalchemy import text

        # Create environment
        req = InitEnvRequestBody(
            templateService="slack",
            templateName="slack_default",
            impersonateUserId="U01DEL1234",
            ttlSeconds=600,
        )
        init_resp = sdk_client.init_env(req)
        env_id = init_resp.environmentId
        schema_name = init_resp.schemaName

        # Verify schema exists
        with session_manager.base_engine.begin() as conn:
            exists_before = conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema)"
                ),
                {"schema": schema_name},
            ).scalar()
        assert exists_before is True

        # Delete
        delete_resp = sdk_client.delete_env(env_id)
        assert delete_resp.environmentId == env_id
        assert delete_resp.status == "deleted"

        # Verify schema dropped
        with session_manager.base_engine.begin() as conn:
            exists_after = conn.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema)"
                ),
                {"schema": schema_name},
            ).scalar()
        assert exists_after is False

        # Verify status in DB
        with session_manager.with_meta_session() as s:
            env = (
                s.query(RunTimeEnvironment)
                .filter(RunTimeEnvironment.id == env_id)
                .one()
            )
            assert env.status == "deleted"


class TestSuiteOperations:
    """Test SDK test suite creation and retrieval."""

    def test_create_test_suite_without_tests(
        self, sdk_client, session_manager, test_user_id
    ):
        """Create test suite without tests should persist suite only."""
        from agent_diff.models import CreateTestSuiteRequest

        req = CreateTestSuiteRequest(
            name="My Test Suite",
            description="A test suite for SDK tests",
            visibility="private",
        )
        resp = sdk_client.create_test_suite(req)

        assert isinstance(resp.id, UUID)
        assert resp.name == "My Test Suite"
        assert resp.description == "A test suite for SDK tests"
        assert resp.visibility == "private"

        # Verify in DB
        with session_manager.with_meta_session() as s:
            suite = s.query(DBTestSuite).filter(DBTestSuite.id == resp.id).one()
            assert suite.name == "My Test Suite"
            assert suite.owner == test_user_id
            assert suite.visibility == "private"

            # No tests should exist
            test_count = (
                s.query(TestMembership)
                .filter(TestMembership.test_suite_id == suite.id)
                .count()
            )
            assert test_count == 0

    def test_create_test_suite_with_tests(
        self, sdk_client, session_manager, test_user_id
    ):
        """Create test suite with embedded tests should persist both."""
        from agent_diff.models import CreateTestSuiteRequest, TestItem

        req = CreateTestSuiteRequest(
            name="Suite with Tests",
            description="Test",
            visibility="public",
            tests=[
                TestItem(
                    name="Test 1",
                    prompt="Do something",
                    type="actionEval",
                    expected_output={
                        "assertions": [
                            {
                                "diff_type": "added",
                                "entity": "messages",
                                "where": {"channel_id": {"eq": "nonexistent"}},
                                "expected_count": 0,
                            }
                        ],
                    },
                    environmentTemplate="slack:slack_default",
                )
            ],
        )
        resp = sdk_client.create_test_suite(req)

        assert isinstance(resp.id, UUID)

        # Verify suite in DB
        with session_manager.with_meta_session() as s:
            suite = s.query(DBTestSuite).filter(DBTestSuite.id == resp.id).one()
            assert suite.name == "Suite with Tests"
            assert suite.visibility == "public"

            # Verify test created
            test_count = (
                s.query(TestMembership)
                .filter(TestMembership.test_suite_id == suite.id)
                .count()
            )
            assert test_count == 1

            # Load the test
            membership = (
                s.query(TestMembership)
                .filter(TestMembership.test_suite_id == suite.id)
                .first()
            )
            test = s.query(DBTest).filter(DBTest.id == membership.test_id).one()
            assert test.name == "Test 1"
            assert test.type == "actionEval"

    def test_list_test_suites_returns_visible_suites(self, sdk_client, session_manager):
        """List test suites should return public suites and user-owned suites."""
        from agent_diff.models import CreateTestSuiteRequest

        # Create a suite
        req = CreateTestSuiteRequest(
            name="Visible Suite",
            description="Test",
            visibility="private",
        )
        created = sdk_client.create_test_suite(req)

        # List
        resp = sdk_client.list_test_suites()

        assert resp.testSuites is not None
        suite_ids = {s.id for s in resp.testSuites}
        assert created.id in suite_ids

    def test_get_test_suite_with_expand(
        self, sdk_client, session_manager, test_user_id
    ):
        """Get test suite with expand=tests should include tests."""
        from agent_diff.models import CreateTestSuiteRequest, TestItem

        # Create suite with tests
        req = CreateTestSuiteRequest(
            name="Suite for Expand Test",
            description="Test",
            visibility="private",
            tests=[
                TestItem(
                    name="Expand Test 1",
                    prompt="Prompt",
                    type="retriEval",
                    expected_output={
                        "assertions": [
                            {
                                "diff_type": "added",
                                "entity": "messages",
                                "where": {"channel_id": {"eq": "nonexistent"}},
                                "expected_count": 0,
                            }
                        ],
                    },
                    environmentTemplate="slack:slack_default",
                )
            ],
        )
        created = sdk_client.create_test_suite(req)

        # Get with expand=tests
        detail = sdk_client.get_test_suite(created.id, include_tests=True)

        assert detail.id == created.id
        assert detail.name == "Suite for Expand Test"
        assert len(detail.tests) == 1
        assert detail.tests[0].name == "Expand Test 1"

        # Get without expand
        summary = sdk_client.get_test_suite(created.id, include_tests=False)
        assert summary.id == created.id
        assert len(summary.tests) == 0


class TestOperations:
    """Test SDK test creation and retrieval."""

    def test_create_tests_batch(self, sdk_client, session_manager, test_user_id):
        """Create multiple tests via batch endpoint."""
        from agent_diff.models import (
            CreateTestSuiteRequest,
            CreateTestsRequest,
            TestItem,
        )

        # Create suite first
        suite_req = CreateTestSuiteRequest(
            name="Batch Test Suite", description="Test", visibility="private"
        )
        suite = sdk_client.create_test_suite(suite_req)

        # Create tests in batch
        tests_req = CreateTestsRequest(
            tests=[
                TestItem(
                    name="Batch Test 1",
                    prompt="Prompt 1",
                    type="actionEval",
                    expected_output={
                        "assertions": [
                            {
                                "diff_type": "added",
                                "entity": "messages",
                                "where": {"channel_id": {"eq": "nonexistent"}},
                                "expected_count": 0,
                            }
                        ],
                    },
                    environmentTemplate="slack:slack_default",
                ),
                TestItem(
                    name="Batch Test 2",
                    prompt="Prompt 2",
                    type="retriEval",
                    expected_output={
                        "assertions": [
                            {
                                "diff_type": "added",
                                "entity": "messages",
                                "where": {"channel_id": {"eq": "nonexistent"}},
                                "expected_count": 0,
                            }
                        ],
                    },
                    environmentTemplate="slack:slack_default",
                ),
            ]
        )
        resp = sdk_client.create_tests(suite.id, tests_req)

        assert len(resp.tests) == 2
        assert resp.tests[0].name == "Batch Test 1"
        assert resp.tests[1].name == "Batch Test 2"

        # Verify in DB
        with session_manager.with_meta_session() as s:
            test_count = (
                s.query(TestMembership)
                .filter(TestMembership.test_suite_id == suite.id)
                .count()
            )
            assert test_count == 2

            # Verify both tests exist
            for test_resp in resp.tests:
                test = s.query(DBTest).filter(DBTest.id == test_resp.id).one()
                assert test.name in ["Batch Test 1", "Batch Test 2"]

    def test_create_test_single(self, sdk_client, session_manager, test_user_id):
        """Create single test (convenience wrapper)."""
        from agent_diff.models import CreateTestSuiteRequest

        # Create suite
        suite_req = CreateTestSuiteRequest(
            name="Single Test Suite", description="Test", visibility="private"
        )
        suite = sdk_client.create_test_suite(suite_req)

        # Create single test
        test_item = {
            "name": "Single Test",
            "prompt": "Do this",
            "type": "compositeEval",
            "expected_output": {
                "assertions": [
                    {
                        "diff_type": "added",
                        "entity": "messages",
                        "where": {},
                        "expected_count": 0,
                    }
                ]
            },
            "environmentTemplate": "slack:slack_default",
        }
        test = sdk_client.create_test(suite.id, test_item)

        assert isinstance(test.id, UUID)
        assert test.name == "Single Test"
        assert test.type == "compositeEval"

        # Verify in DB
        with session_manager.with_meta_session() as s:
            db_test = s.query(DBTest).filter(DBTest.id == test.id).one()
            assert db_test.name == "Single Test"

            membership = (
                s.query(TestMembership)
                .filter(TestMembership.test_id == test.id)
                .first()
            )
            assert membership.test_suite_id == suite.id

    def test_get_test_success(self, sdk_client, session_manager):
        """Get test by ID should return full test detail."""
        from agent_diff.models import CreateTestSuiteRequest, TestItem

        # Create suite with test
        suite_req = CreateTestSuiteRequest(
            name="Get Test Suite",
            description="Test",
            visibility="private",
            tests=[
                TestItem(
                    name="Get Test 1",
                    prompt="Prompt",
                    type="actionEval",
                    expected_output={
                        "assertions": [
                            {
                                "diff_type": "added",
                                "entity": "messages",
                                "where": {"channel_id": {"eq": "nonexistent"}},
                                "expected_count": 0,
                            }
                        ],
                    },
                    environmentTemplate="slack:slack_default",
                )
            ],
        )
        suite = sdk_client.create_test_suite(suite_req)

        # Get suite with tests to find test ID
        detail = sdk_client.get_test_suite(suite.id, include_tests=True)
        test_id = detail.tests[0].id

        # Get individual test
        test = sdk_client.get_test(test_id)

        assert test.id == test_id
        assert test.name == "Get Test 1"
        assert test.type == "actionEval"
        assert "assertions" in test.expected_output
        assert len(test.expected_output["assertions"]) > 0

    def test_get_test_not_found(self, sdk_client):
        """Get test with invalid ID should raise 404."""
        from uuid import uuid4
        import requests

        with pytest.raises(requests.HTTPError) as exc_info:
            sdk_client.get_test(uuid4())

        assert exc_info.value.response.status_code == 404


class TestRunLifecycle:
    """Test SDK run creation, evaluation, and result retrieval."""

    def test_start_test_run_creates_run_and_snapshot(
        self, sdk_client, session_manager, cleanup_test_environments
    ):
        """Start test run should create TestRun row and before snapshot."""
        from agent_diff.models import (
            InitEnvRequestBody,
            CreateTestSuiteRequest,
            TestItem,
            StartRunRequest,
        )

        # Setup: create env, suite, and test
        env_resp = sdk_client.init_env(
            InitEnvRequestBody(
                templateService="slack",
                templateName="slack_default",
                impersonateUserId="U01RUN1234",
                ttlSeconds=600,
            )
        )
        suite_req = CreateTestSuiteRequest(
            name="Run Test Suite",
            description="Test",
            visibility="private",
            tests=[
                TestItem(
                    name="Run Test 1",
                    prompt="Prompt",
                    type="actionEval",
                    expected_output={
                        "assertions": [
                            {
                                "diff_type": "added",
                                "entity": "messages",
                                "where": {"channel_id": {"eq": "nonexistent"}},
                                "expected_count": 0,
                            }
                        ],
                    },
                    environmentTemplate="slack:slack_default",
                )
            ],
        )
        suite = sdk_client.create_test_suite(suite_req)
        suite_detail = sdk_client.get_test_suite(suite.id, include_tests=True)
        test_id = suite_detail.tests[0].id

        # Start run
        start_req = StartRunRequest(
            envId=env_resp.environmentId,
            testId=test_id,
            testSuiteId=suite.id,
        )
        run_resp = sdk_client.start_run(start_req)

        assert run_resp.runId is not None
        assert run_resp.status == "running"
        assert run_resp.beforeSnapshot is not None

        # Verify in DB
        with session_manager.with_meta_session() as s:
            run = s.query(TestRun).filter(TestRun.id == run_resp.runId).one()
            assert run.status == "running"
            assert run.test_id == test_id
            assert run.environment_id == UUID(env_resp.environmentId)
            assert run.before_snapshot_suffix == run_resp.beforeSnapshot
            assert run.after_snapshot_suffix is None  # Not taken yet

    def test_end_test_run_evaluates_and_stores_result(
        self, sdk_client, session_manager, cleanup_test_environments
    ):
        """End test run should evaluate, compute diff, and store result."""
        from agent_diff.models import (
            InitEnvRequestBody,
            CreateTestSuiteRequest,
            TestItem,
            StartRunRequest,
            EndRunRequest,
        )

        # Setup
        env_resp = sdk_client.init_env(
            InitEnvRequestBody(
                templateService="slack",
                templateName="slack_default",
                impersonateUserId="U01END1234",
                ttlSeconds=600,
            )
        )
        suite_req = CreateTestSuiteRequest(
            name="End Run Suite",
            description="Test",
            visibility="private",
            tests=[
                TestItem(
                    name="End Run Test",
                    prompt="Prompt",
                    type="actionEval",
                    expected_output={
                        "assertions": [
                            {
                                "diff_type": "added",
                                "entity": "messages",
                                "where": {"channel_id": {"eq": "nonexistent"}},
                                "expected_count": 0,
                            }
                        ],
                    },
                    environmentTemplate="slack:slack_default",
                )
            ],
        )
        suite = sdk_client.create_test_suite(suite_req)
        suite_detail = sdk_client.get_test_suite(suite.id, include_tests=True)
        test_id = suite_detail.tests[0].id

        # Start run
        start_req = StartRunRequest(
            envId=env_resp.environmentId, testId=test_id, testSuiteId=suite.id
        )
        run_resp = sdk_client.start_run(start_req)

        # End run (no actions taken, so diff should be minimal/empty)
        end_req = EndRunRequest(runId=run_resp.runId)
        end_resp = sdk_client.evaluate_run(end_req)

        assert end_resp.runId == run_resp.runId
        assert end_resp.status in ["passed", "failed", "error"]
        assert end_resp.passed is not None
        assert end_resp.score is not None

        # Verify in DB
        with session_manager.with_meta_session() as s:
            run = s.query(TestRun).filter(TestRun.id == run_resp.runId).one()
            assert run.status in ["passed", "failed", "error"]
            assert run.after_snapshot_suffix is not None
            assert run.result is not None
            assert "passed" in run.result
            assert "score" in run.result

    def test_get_run_result_returns_full_detail(
        self, sdk_client, session_manager, cleanup_test_environments
    ):
        """Get run result should return full evaluation with diff."""
        from agent_diff.models import (
            InitEnvRequestBody,
            CreateTestSuiteRequest,
            TestItem,
            StartRunRequest,
            EndRunRequest,
        )

        # Setup and run
        env_resp = sdk_client.init_env(
            InitEnvRequestBody(
                templateService="slack",
                templateName="slack_default",
                impersonateUserId="U01RESULT99",
                ttlSeconds=600,
            )
        )
        suite_req = CreateTestSuiteRequest(
            name="Result Suite",
            description="Test",
            visibility="private",
            tests=[
                TestItem(
                    name="Result Test",
                    prompt="Prompt",
                    type="actionEval",
                    expected_output={
                        "assertions": [
                            {
                                "diff_type": "added",
                                "entity": "messages",
                                "where": {"channel_id": {"eq": "nonexistent"}},
                                "expected_count": 0,
                            }
                        ],
                    },
                    environmentTemplate="slack:slack_default",
                )
            ],
        )
        suite = sdk_client.create_test_suite(suite_req)
        suite_detail = sdk_client.get_test_suite(suite.id, include_tests=True)
        test_id = suite_detail.tests[0].id

        start_resp = sdk_client.start_run(
            StartRunRequest(
                envId=env_resp.environmentId, testId=test_id, testSuiteId=suite.id
            )
        )
        sdk_client.evaluate_run(EndRunRequest(runId=start_resp.runId))

        # Get result
        result = sdk_client.get_results_for_run(start_resp.runId)

        assert result.runId == start_resp.runId
        assert result.status in ["passed", "failed", "error"]
        assert result.passed is not None
        assert result.score is not None
        assert result.failures is not None
        assert result.diff is not None
        assert result.createdAt is not None


class TestDiffOperations:
    """Test SDK diff-only operations (no evaluation)."""

    def test_diff_run_by_run_id(
        self, sdk_client, session_manager, cleanup_test_environments
    ):
        """Diff run by runId should use stored before snapshot."""
        from agent_diff.models import (
            InitEnvRequestBody,
            CreateTestSuiteRequest,
            TestItem,
            StartRunRequest,
            DiffRunRequest,
        )

        # Setup
        env_resp = sdk_client.init_env(
            InitEnvRequestBody(
                templateService="slack",
                templateName="slack_default",
                impersonateUserId="U01DIFF1234",
                ttlSeconds=600,
            )
        )
        suite_req = CreateTestSuiteRequest(
            name="Diff Run Suite",
            description="Test",
            visibility="private",
            tests=[
                TestItem(
                    name="Diff Test",
                    prompt="Prompt",
                    type="actionEval",
                    expected_output={
                        "assertions": [
                            {
                                "diff_type": "added",
                                "entity": "messages",
                                "where": {"channel_id": {"eq": "nonexistent"}},
                                "expected_count": 0,
                            }
                        ],
                    },
                    environmentTemplate="slack:slack_default",
                )
            ],
        )
        suite = sdk_client.create_test_suite(suite_req)
        suite_detail = sdk_client.get_test_suite(suite.id, include_tests=True)
        test_id = suite_detail.tests[0].id

        # Start run to get before snapshot
        start_resp = sdk_client.start_run(
            StartRunRequest(
                envId=env_resp.environmentId, testId=test_id, testSuiteId=suite.id
            )
        )

        # Compute diff by runId
        diff_req = DiffRunRequest(runId=start_resp.runId)
        diff_resp = sdk_client.diff_run(diff_req)

        assert diff_resp.beforeSnapshot == start_resp.beforeSnapshot
        assert diff_resp.afterSnapshot is not None
        assert diff_resp.diff is not None

    def test_diff_run_by_before_suffix(
        self, sdk_client, session_manager, cleanup_test_environments
    ):
        """Diff run by envId + beforeSuffix should compute diff."""
        from agent_diff.models import (
            InitEnvRequestBody,
            CreateTestSuiteRequest,
            TestItem,
            StartRunRequest,
            DiffRunRequest,
        )

        # Setup
        env_resp = sdk_client.init_env(
            InitEnvRequestBody(
                templateService="slack",
                templateName="slack_default",
                impersonateUserId="U01DIFF5678",
                ttlSeconds=600,
            )
        )
        suite_req = CreateTestSuiteRequest(
            name="Diff Before Suite",
            description="Test",
            visibility="private",
            tests=[
                TestItem(
                    name="Diff Before Test",
                    prompt="Prompt",
                    type="actionEval",
                    expected_output={
                        "assertions": [
                            {
                                "diff_type": "added",
                                "entity": "messages",
                                "where": {"channel_id": {"eq": "nonexistent"}},
                                "expected_count": 0,
                            }
                        ],
                    },
                    environmentTemplate="slack:slack_default",
                )
            ],
        )
        suite = sdk_client.create_test_suite(suite_req)
        suite_detail = sdk_client.get_test_suite(suite.id, include_tests=True)
        test_id = suite_detail.tests[0].id

        # Start run to capture before
        start_resp = sdk_client.start_run(
            StartRunRequest(
                envId=env_resp.environmentId, testId=test_id, testSuiteId=suite.id
            )
        )
        before_suffix = start_resp.beforeSnapshot

        # Compute diff using explicit before
        diff_req = DiffRunRequest(
            envId=env_resp.environmentId, beforeSuffix=before_suffix
        )
        diff_resp = sdk_client.diff_run(diff_req)

        assert diff_resp.beforeSnapshot == before_suffix
        assert diff_resp.afterSnapshot is not None
        assert diff_resp.diff is not None


class TestTemplateCreation:
    """Test SDK template creation from environments."""

    def test_create_template_from_environment_success(
        self, sdk_client, session_manager, test_user_id, cleanup_test_environments
    ):
        """Create template from environment should register new template."""
        from agent_diff.models import (
            InitEnvRequestBody,
            CreateTemplateFromEnvRequest,
        )

        # Create environment
        env_resp = sdk_client.init_env(
            InitEnvRequestBody(
                templateService="slack",
                templateName="slack_default",
                impersonateUserId="U01TMPL1234",
                ttlSeconds=600,
            )
        )

        # Create template from environment
        tmpl_req = CreateTemplateFromEnvRequest(
            environmentId=env_resp.environmentId,
            service="slack",
            name="my_custom_template",
            description="Custom template from test",
            visibility="private",
            version="v1",
        )
        tmpl_resp = sdk_client.create_template_from_environment(tmpl_req)

        assert tmpl_resp.templateId is not None
        assert tmpl_resp.templateName == "my_custom_template"
        assert tmpl_resp.service == "slack"

        # Verify in DB
        with session_manager.with_meta_session() as s:
            tmpl = (
                s.query(TemplateEnvironment)
                .filter(TemplateEnvironment.id == tmpl_resp.templateId)
                .one()
            )
            assert tmpl.name == "my_custom_template"
            assert tmpl.service == "slack"
            assert tmpl.visibility == "private"
            assert tmpl.owner_id == test_user_id
            assert tmpl.description == "Custom template from test"
            assert tmpl.kind == "schema"
            assert tmpl.location is not None


class TestNameResolution:
    """Test resolution of resources by name (not just UUID)."""

    def test_init_env_by_service_name_resolves_correctly(
        self, sdk_client, session_manager, cleanup_test_environments
    ):
        """Init environment by service:name should resolve to correct template."""
        from agent_diff.models import InitEnvRequestBody

        req = InitEnvRequestBody(
            templateService="slack",
            templateName="slack_default",
            impersonateUserId="U01NAME1234",
            ttlSeconds=600,
        )
        resp = sdk_client.init_env(req)

        assert resp.service == "slack"
        assert "slack" in resp.templateSchema.lower()

        # Verify correct template was used
        with session_manager.with_meta_session() as s:
            env = (
                s.query(RunTimeEnvironment)
                .filter(RunTimeEnvironment.id == resp.environmentId)
                .one()
            )
            # Schema should be derived from slack_default template
            assert env.schema.startswith("state_")

    def test_create_test_with_template_by_name(
        self, sdk_client, session_manager, cleanup_test_environments
    ):
        """Create test using template name (service:name) should resolve."""
        from agent_diff.models import CreateTestSuiteRequest, TestItem

        suite_req = CreateTestSuiteRequest(
            name="Name Resolution Suite",
            description="Test",
            visibility="private",
            tests=[
                TestItem(
                    name="Name Test",
                    prompt="Prompt",
                    type="actionEval",
                    expected_output={
                        "assertions": [
                            {
                                "diff_type": "added",
                                "entity": "messages",
                                "where": {"channel_id": {"eq": "nonexistent"}},
                                "expected_count": 0,
                            }
                        ],
                    },
                    environmentTemplate="slack:slack_default",  # Using service:name
                )
            ],
        )
        suite = sdk_client.create_test_suite(suite_req)

        # Verify test was created with resolved template
        suite_detail = sdk_client.get_test_suite(suite.id, include_tests=True)
        assert len(suite_detail.tests) == 1

        with session_manager.with_meta_session() as s:
            test = s.query(DBTest).filter(DBTest.id == suite_detail.tests[0].id).one()
            # template_schema should be the resolved location
            assert test.template_schema is not None
            assert "slack" in test.template_schema.lower()

    def test_create_test_with_template_ambiguous_name_fails(
        self, sdk_client, session_manager, cleanup_test_environments
    ):
        """Create test with ambiguous template name should fail."""
        from agent_diff.models import CreateTestSuiteRequest, TestItem
        import requests

        # Create suite with test using only name (if multiple exist)
        suite_req = CreateTestSuiteRequest(
            name="Ambiguous Suite",
            description="Test",
            visibility="private",
            tests=[
                TestItem(
                    name="Ambiguous Test",
                    prompt="Prompt",
                    type="actionEval",
                    expected_output={
                        "assertions": [
                            {
                                "diff_type": "added",
                                "entity": "messages",
                                "where": {"channel_id": {"eq": "nonexistent"}},
                                "expected_count": 0,
                            }
                        ],
                    },
                    # Using just name without service prefix - will fail if multiple templates share name
                    environmentTemplate="nonexistent_template",
                )
            ],
        )

        with pytest.raises(requests.HTTPError) as exc_info:
            sdk_client.create_test_suite(suite_req)

        # Should be 400 (template not found)
        assert exc_info.value.response.status_code == 400
