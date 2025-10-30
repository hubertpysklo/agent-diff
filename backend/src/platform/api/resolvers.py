from __future__ import annotations

from sqlalchemy.orm import Session

from src.platform.api.models import (
    TestItem,
    CreateTestsRequest,
)
from src.platform.api.auth import require_resource_access
from src.platform.db.schema import (
    RunTimeEnvironment,
    TestRun,
)
from uuid import UUID


def parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except Exception as exc:
        raise ValueError("invalid uuid") from exc




def require_environment_access(
    session: Session, principal_id: str, env_id: str
) -> RunTimeEnvironment:
    """Check environment access and return environment."""
    env = (
        session.query(RunTimeEnvironment)
        .filter(RunTimeEnvironment.id == env_id)
        .one_or_none()
    )
    if env is None:
        raise ValueError("environment not found")

    require_resource_access(principal_id, env.created_by)
    return env


def require_run_access(session: Session, principal_id: str, run_id: str) -> TestRun:
    """Check test run access and return run."""
    run = session.query(TestRun).filter(TestRun.id == run_id).one_or_none()
    if run is None:
        raise ValueError("run not found")

    require_resource_access(principal_id, run.created_by)
    return run




def resolve_and_validate_test_items(
    session: Session,
    principal_id: str,
    items: list[TestItem],
    default_template: str | None,
    template_manager,  # TemplateManager instance
) -> list[str]:
    """Resolve environment template for each item and validate DSL."""
    from src.platform.testManager.core import CoreTestManager

    core = CoreTestManager()
    resolved_schemas: list[str] = []
    for idx, item in enumerate(items):
        template_ref = item.environmentTemplate or default_template
        if not template_ref:
            raise ValueError(f"tests[{idx}]: environmentTemplate missing")
        schema = template_manager.resolve_template_schema(
            session, principal_id, str(template_ref)
        )
        core.validate_dsl(item.expected_output)
        resolved_schemas.append(schema)
    return resolved_schemas


def to_bulk_test_items(body: CreateTestsRequest) -> list[dict]:
    """Normalize CreateTestsRequest into list of dicts for bulk creation."""
    return [
        {
            "name": item.name,
            "prompt": item.prompt,
            "type": item.type,
            "expected_output": item.expected_output,
            "impersonateUserId": item.impersonateUserId,
        }
        for item in body.tests
    ]
