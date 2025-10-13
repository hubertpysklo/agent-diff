"""
Shared pytest fixtures for all tests.

Provides database connections, session managers, and test utilities
that can be used across all test files.
"""

import os
from pathlib import Path
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from starlette.testclient import TestClient
from uuid import uuid4

env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from src.platform.isolationEngine.session import SessionManager
from src.platform.isolationEngine.environment import EnvironmentHandler
from src.platform.isolationEngine.core import CoreIsolationEngine
from src.platform.evaluationEngine.core import CoreEvaluationEngine


@pytest.fixture(scope="session")
def db_url():
    """Database URL from environment."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    return url


@pytest.fixture(scope="session")
def db_engine(db_url):
    """SQLAlchemy engine for the test database."""
    engine = create_engine(db_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def session_manager(db_engine):
    """SessionManager instance for tests."""
    return SessionManager(db_engine)


@pytest.fixture(scope="session")
def environment_handler(session_manager):
    """EnvironmentHandler instance for tests."""
    return EnvironmentHandler(session_manager)


@pytest.fixture(scope="session")
def core_isolation_engine(session_manager, environment_handler):
    """CoreIsolationEngine instance for tests."""
    return CoreIsolationEngine(
        sessions=session_manager, environment_handler=environment_handler
    )


@pytest.fixture(scope="session")
def core_evaluation_engine(session_manager):
    """CoreEvaluationEngine instance for tests."""
    return CoreEvaluationEngine(sessions=session_manager)


@pytest.fixture(scope="function")
def test_client(session_manager):
    """Starlette TestClient with full application."""
    from src.platform.api.main import create_app
    app = create_app()
    return TestClient(app)


@pytest.fixture(scope="session")
def test_user_id(session_manager):
    """Get or create a test user and return their ID."""
    from src.platform.db.schema import User
    from datetime import datetime

    with session_manager.with_meta_session() as session:
        # Try to find existing dev user
        user = session.query(User).filter(User.email == "dev@localhost").first()
        if user:
            return user.id

        # Create test user if not exists
        user_id = str(uuid4())
        test_user = User(
            id=user_id,
            email="test@test.com",
            username="test",
            password="test",
            name="Test User",
            is_platform_admin=True,
            is_organization_admin=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        session.add(test_user)
        session.commit()
        return user_id


@pytest.fixture(scope="function")
def test_env_id():
    """Generate a unique test environment ID."""
    return uuid4().hex


@pytest.fixture(scope="function")
def created_schemas(db_engine):
    """Track and cleanup schemas created during test."""
    schemas = []

    yield schemas

    # Cleanup: drop all created schemas
    with db_engine.begin() as conn:
        for schema in schemas:
            try:
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            except Exception:
                pass  # Schema might not exist


@pytest.fixture(scope="function")
def cleanup_test_environments(session_manager, created_schemas):
    """Auto-cleanup fixture that drops all state_* schemas created during test."""
    yield

    # Find all state_* schemas
    with session_manager.base_engine.begin() as conn:
        result = conn.execute(
            text("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name LIKE 'state_%'
        """)
        )
        schemas = [row[0] for row in result]

    # Drop them
    with session_manager.base_engine.begin() as conn:
        for schema in schemas:
            try:
                conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            except Exception:
                pass


@pytest_asyncio.fixture
async def slack_client(test_user_id, core_isolation_engine, session_manager, environment_handler):
    """Create an AsyncClient for testing Slack API as U01AGENBOT9 (agent1)."""
    from httpx import AsyncClient, ASGITransport
    from src.services.slack.api.methods import SLACK_HANDLERS, slack_endpoint
    from starlette.routing import Route
    from starlette.applications import Starlette

    env_result = core_isolation_engine.create_environment(
        template_schema="slack_default",
        ttl_seconds=3600,
        created_by=test_user_id,
        impersonate_user_id="U01AGENBOT9",
        impersonate_email="agent@example.com",
    )

    async def add_db_session(request, call_next):
        with session_manager.with_session_for_environment(env_result.environment_id) as session:
            request.state.db_session = session
            request.state.impersonate_user_id = "U01AGENBOT9"
            request.state.impersonate_email = "agent@example.com"
            response = await call_next(request)
            return response

    routes = [Route("/{endpoint}", slack_endpoint, methods=["GET", "POST"])]
    app = Starlette(routes=routes, middleware=[])
    app.middleware("http")(add_db_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    environment_handler.drop_schema(env_result.schema_name)


@pytest_asyncio.fixture
async def slack_client_john(test_user_id, core_isolation_engine, session_manager, environment_handler):
    """Create an AsyncClient for testing Slack API as U02JOHNDOE1 (johndoe)."""
    from httpx import AsyncClient, ASGITransport
    from src.services.slack.api.methods import slack_endpoint
    from starlette.routing import Route
    from starlette.applications import Starlette

    env_result = core_isolation_engine.create_environment(
        template_schema="slack_default",
        ttl_seconds=3600,
        created_by=test_user_id,
        impersonate_user_id="U02JOHNDOE1",
        impersonate_email="john@example.com",
    )

    async def add_db_session(request, call_next):
        with session_manager.with_session_for_environment(env_result.environment_id) as session:
            request.state.db_session = session
            request.state.impersonate_user_id = "U02JOHNDOE1"
            request.state.impersonate_email = "john@example.com"
            response = await call_next(request)
            return response

    routes = [Route("/{endpoint}", slack_endpoint, methods=["GET", "POST"])]
    app = Starlette(routes=routes, middleware=[])
    app.middleware("http")(add_db_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    environment_handler.drop_schema(env_result.schema_name)


def create_test_environment(
    core_isolation_engine: CoreIsolationEngine,
    template_schema: str = "slack_default",
    ttl_seconds: int = 3600,
    created_by: str = "test_user",
    impersonate_user_id: str = "U01AGENBOT9",
    impersonate_email: str | None = None,
):
    
    return core_isolation_engine.create_environment(
        template_schema=template_schema,
        ttl_seconds=ttl_seconds,
        created_by=created_by,
        impersonate_user_id=impersonate_user_id,
        impersonate_email=impersonate_email,
    )


# Make helper function available as a fixture
@pytest.fixture
def create_env(core_isolation_engine):
    """Fixture that provides the create_test_environment helper."""

    def _create(**kwargs):
        return create_test_environment(core_isolation_engine, **kwargs)

    return _create
