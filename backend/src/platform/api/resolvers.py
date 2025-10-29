from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import or_

from src.platform.api.models import (
    InitEnvRequestBody,
    TestItem,
    CreateTestsRequest,
)
from src.platform.api.auth import (
    require_resource_access,
    check_template_access,
)
from src.platform.db.schema import (
    TestSuite,
    TemplateEnvironment,
    RunTimeEnvironment,
    Test,
    TestMembership,
    TestRun,
)
from uuid import UUID


def _try_parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except Exception:
        return None


def parse_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except Exception as exc:
        raise ValueError("invalid uuid") from exc


def resolve_test_suite(
    session: Session, principal_id: str, suite_ref: str
) -> TestSuite:
    maybe_uuid = _try_parse_uuid(suite_ref)
    if maybe_uuid:
        suite = (
            session.query(TestSuite).filter(TestSuite.id == maybe_uuid).one_or_none()
        )
        if suite is None:
            raise ValueError("test suite not found")
        if suite.visibility == "private":
            require_resource_access(principal_id, suite.owner)
        return suite

    query = (
        session.query(TestSuite)
        .filter(TestSuite.name == suite_ref)
        .filter(or_(TestSuite.owner == principal_id, TestSuite.visibility == "public"))
    )
    suites = query.order_by(TestSuite.created_at.desc()).all()
    if not suites:
        raise ValueError("test suite not found")
    if len(suites) > 1:
        raise ValueError("multiple suites match name; use suite id")
    suite = suites[0]
    if suite.visibility == "private":
        require_resource_access(principal_id, suite.owner)
    return suite


def resolve_template_schema(
    session: Session, principal_id: str, template_ref: str
) -> str:
    maybe_uuid = _try_parse_uuid(template_ref)
    if maybe_uuid:
        t = (
            session.query(TemplateEnvironment)
            .filter(TemplateEnvironment.id == maybe_uuid)
            .one_or_none()
        )
        if t is None:
            raise ValueError("template not found")
        check_template_access(principal_id, t)
        return t.location

    service: str | None = None
    name = template_ref
    if ":" in template_ref:
        service, name = template_ref.split(":", 1)

    query = session.query(TemplateEnvironment).filter(TemplateEnvironment.name == name)
    if service:
        query = query.filter(TemplateEnvironment.service == service)

    # Filter by visibility
    query = query.filter(
        or_(
            TemplateEnvironment.visibility == "public",
            TemplateEnvironment.owner_id == principal_id,
        )
    )
    matches = query.order_by(TemplateEnvironment.created_at.desc()).all()
    if not matches:
        raise ValueError("template not found")

    return matches[0].location


def list_templates_for_principal(session: Session, principal_id: str):
    """List templates accessible to principal_id."""
    query = session.query(TemplateEnvironment).filter(
        or_(
            TemplateEnvironment.visibility == "public",
            TemplateEnvironment.owner_id == principal_id,
        )
    )

    all_templates = query.order_by(TemplateEnvironment.created_at.desc()).all()

    seen = set()
    deduplicated = []
    for t in all_templates:
        key = (t.service, t.name)
        if key not in seen:
            seen.add(key)
            deduplicated.append(t)

    return deduplicated


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


def resolve_init_template(
    session: Session, principal_id: str, body: InitEnvRequestBody
) -> tuple[str, str]:
    """Return (schema, service) for environment init selection."""
    # Path 1: testId provided
    if body.testId:
        test = session.query(Test).filter(Test.id == body.testId).one_or_none()
        if test is None:
            raise ValueError("test not found")

        # Validate access to its suite if private
        suite = (
            session.query(TestSuite)
            .join(TestMembership, TestMembership.test_suite_id == TestSuite.id)
            .filter(TestMembership.test_id == body.testId)
            .first()
        )
        if suite and suite.visibility == "private":
            require_resource_access(principal_id, suite.owner)

        schema = body.templateSchema or test.template_schema
        t = (
            session.query(TemplateEnvironment)
            .filter(TemplateEnvironment.location == schema)
            .order_by(TemplateEnvironment.created_at.desc())
            .first()
        )
        if t is None:
            raise ValueError("template schema not registered")
        return t.location, t.service

    # Path 2: templateId
    if body.templateId is not None:
        t = (
            session.query(TemplateEnvironment)
            .filter(TemplateEnvironment.id == body.templateId)
            .one_or_none()
        )
        if t is None:
            raise ValueError("template not found")
        check_template_access(principal_id, t)
        return t.location, t.service

    # Path 3: service + name
    if body.templateService and body.templateName:
        query = (
            session.query(TemplateEnvironment)
            .filter(
                TemplateEnvironment.service == body.templateService,
                TemplateEnvironment.name == body.templateName,
            )
            .filter(
                or_(
                    TemplateEnvironment.visibility == "public",
                    TemplateEnvironment.owner_id == principal_id,
                )
            )
        )
        matches = query.order_by(TemplateEnvironment.created_at.desc()).all()
        if len(matches) == 0:
            raise ValueError("template not found")

        t = matches[0]
        return t.location, t.service

    # Path 4: templateSchema
    if body.templateSchema:
        t = (
            session.query(TemplateEnvironment)
            .filter(TemplateEnvironment.location == body.templateSchema)
            .order_by(TemplateEnvironment.created_at.desc())
            .first()
        )
        if t is None:
            raise ValueError("template schema not registered")
        return t.location, t.service

    raise ValueError(
        "one of templateId, (templateService+templateName), templateSchema, or testId must be provided"
    )


def resolve_and_validate_test_items(
    session: Session,
    principal_id: str,
    items: list[TestItem],
    default_template: str | None,
) -> list[str]:
    """Resolve environment template for each item and validate DSL."""
    from src.platform.testManager.core import CoreTestManager

    core = CoreTestManager()
    resolved_schemas: list[str] = []
    for idx, item in enumerate(items):
        template_ref = item.environmentTemplate or default_template
        if not template_ref:
            raise ValueError(f"tests[{idx}]: environmentTemplate missing")
        schema = resolve_template_schema(session, principal_id, str(template_ref))
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
