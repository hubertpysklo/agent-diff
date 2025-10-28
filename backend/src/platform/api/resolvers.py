"""TODO: This is AI slop code, will need to be cleaned up and refactored after MVP"""

from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from src.platform.api.models import (
    Principal,
    OwnerScope,
    InitEnvRequestBody,
    TestItem,
    CreateTestsRequest,
)
from src.platform.api.auth import (
    require_resource_access,
    check_template_access,
    require_resource_access_with_org,
)
from src.platform.db.schema import (
    TestSuite,
    TemplateEnvironment,
    RunTimeEnvironment,
    OrganizationMembership,
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
    """Parse a UUID or raise ValueError("invalid uuid")."""
    try:
        return UUID(value)
    except Exception as exc:
        raise ValueError("invalid uuid") from exc


def resolve_test_suite(
    session: Session, principal: Principal, suite_ref: str
) -> TestSuite:
    # UUID first
    maybe_uuid = _try_parse_uuid(suite_ref)
    suite: TestSuite | None = None
    if maybe_uuid:
        suite = (
            session.query(TestSuite).filter(TestSuite.id == maybe_uuid).one_or_none()
        )
        if suite is None:
            raise ValueError("test suite not found")
        if suite.visibility == "private":
            require_resource_access(principal, suite.owner)
        return suite

    # Name lookup within caller visibility
    query = session.query(TestSuite).filter(TestSuite.name == suite_ref)
    if not principal.is_platform_admin:
        query = query.filter(
            or_(TestSuite.owner == principal.user_id, TestSuite.visibility == "public")
        )
    suites = query.order_by(TestSuite.created_at.desc()).all()
    if not suites:
        raise ValueError("test suite not found")
    if len(suites) > 1:
        raise ValueError("multiple suites match name; use suite id")
    suite = suites[0]
    if suite.visibility == "private":
        require_resource_access(principal, suite.owner)
    return suite


def resolve_template_schema(
    session: Session, principal: Principal, template_ref: str
) -> str:
    # UUID first
    maybe_uuid = _try_parse_uuid(template_ref)
    if maybe_uuid:
        t = (
            session.query(TemplateEnvironment)
            .filter(TemplateEnvironment.id == maybe_uuid)
            .one_or_none()
        )
        if t is None:
            raise ValueError("template not found")
        check_template_access(principal, t)
        return t.location

    # service:name support; else name only
    service: str | None = None
    name = template_ref
    if ":" in template_ref:
        service, name = template_ref.split(":", 1)

    query = session.query(TemplateEnvironment).filter(TemplateEnvironment.name == name)
    if service:
        query = query.filter(TemplateEnvironment.service == service)
    if not principal.is_platform_admin:
        query = query.filter(
            or_(
                TemplateEnvironment.owner_scope == OwnerScope.public,
                and_(
                    TemplateEnvironment.owner_scope == OwnerScope.org,
                    TemplateEnvironment.owner_org_id.in_(principal.org_ids),
                ),
                and_(
                    TemplateEnvironment.owner_scope == OwnerScope.user,
                    TemplateEnvironment.owner_user_id == principal.user_id,
                ),
            )
        )
    matches = query.order_by(TemplateEnvironment.created_at.desc()).all()
    if not matches:
        raise ValueError("template not found")

    return matches[0].location


def list_templates_for_principal(session: Session, principal: Principal):
    """List templates accessible to principal, deduplicated by (service, name) - returns latest."""
    query = session.query(TemplateEnvironment)
    if not principal.is_platform_admin:
        query = query.filter(
            or_(
                TemplateEnvironment.owner_scope == OwnerScope.public,
                and_(
                    TemplateEnvironment.owner_scope == OwnerScope.org,
                    TemplateEnvironment.owner_org_id.in_(principal.org_ids),
                ),
                and_(
                    TemplateEnvironment.owner_scope == OwnerScope.user,
                    TemplateEnvironment.owner_user_id == principal.user_id,
                ),
            )
        )

    all_templates = query.order_by(TemplateEnvironment.created_at.desc()).all()

    # Deduplicate by (service, name) - keep only the latest (first due to desc order)
    seen = set()
    deduplicated = []
    for t in all_templates:
        key = (t.service, t.name)
        if key not in seen:
            seen.add(key)
            deduplicated.append(t)

    return deduplicated


def require_environment_access(
    session: Session, principal: Principal, env_id: str
) -> RunTimeEnvironment:
    env = (
        session.query(RunTimeEnvironment)
        .filter(RunTimeEnvironment.id == env_id)
        .one_or_none()
    )
    if env is None:
        raise ValueError("environment not found")

    creator_org_ids = [
        m.organization_id
        for m in session.query(OrganizationMembership).filter_by(user_id=env.created_by)
    ]
    require_resource_access_with_org(principal, env.created_by, creator_org_ids)
    return env


def require_run_access(session: Session, principal: Principal, run_id: str) -> TestRun:
    run = session.query(TestRun).filter(TestRun.id == run_id).one_or_none()
    if run is None:
        raise ValueError("run not found")

    creator_org_ids = [
        m.organization_id
        for m in session.query(OrganizationMembership).filter_by(user_id=run.created_by)
    ]
    require_resource_access_with_org(principal, run.created_by, creator_org_ids)
    return run


def resolve_owner_ids(
    principal: Principal, owner_scope: OwnerScope
) -> tuple[str | None, str | None]:
    """Return (owner_user_id, owner_org_id) based on scope and principal.
    Raises ValueError if org scope requires explicit org and principal has multiple.
    """
    if owner_scope == OwnerScope.user:
        return principal.user_id, None
    if owner_scope == OwnerScope.org:
        if len(principal.org_ids) != 1:
            raise ValueError(
                "ownerScope=org requires membership in exactly one org or explicit ownerOrgId (not yet supported)"
            )
        return None, principal.org_ids[0]
    if owner_scope == OwnerScope.public:
        return None, None
    raise ValueError("invalid ownerScope")


def resolve_init_template(
    session: Session, principal: Principal, body: InitEnvRequestBody
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
            require_resource_access(principal, suite.owner)

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
        check_template_access(principal, t)
        return t.location, t.service

    # Path 3: service + name
    if body.templateService and body.templateName:
        query = session.query(TemplateEnvironment).filter(
            TemplateEnvironment.service == body.templateService,
            TemplateEnvironment.name == body.templateName,
        )
        if not principal.is_platform_admin:
            query = query.filter(
                or_(
                    TemplateEnvironment.owner_scope == OwnerScope.public,
                    and_(
                        TemplateEnvironment.owner_scope == OwnerScope.org,
                        TemplateEnvironment.owner_org_id.in_(principal.org_ids),
                    ),
                    and_(
                        TemplateEnvironment.owner_scope == OwnerScope.user,
                        TemplateEnvironment.owner_user_id == principal.user_id,
                    ),
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
    principal: Principal,
    items: list[TestItem],
    default_template: str | None,
) -> list[str]:
    """Resolve environment template for each item and validate DSL. Returns list of schemas.
    Raises ValueError/PermissionError on failure.
    """
    from src.platform.testManager.core import CoreTestManager

    core = CoreTestManager()
    resolved_schemas: list[str] = []
    for idx, item in enumerate(items):
        template_ref = item.environmentTemplate or default_template
        if not template_ref:
            raise ValueError(f"tests[{idx}]: environmentTemplate missing")
        schema = resolve_template_schema(session, principal, str(template_ref))
        core.validate_dsl(item.expected_output)
        resolved_schemas.append(schema)
    return resolved_schemas


def to_bulk_test_items(body: CreateTestsRequest) -> list[dict]:
    """Normalize CreateTestsRequest into list of dicts for bulk creation.
    Keys: name, prompt, type, expected_output, impersonateUserId
    """
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
