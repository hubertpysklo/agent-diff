from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import and_, or_
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from uuid import UUID

from src.platform.api.models import (
    InitEnvRequestBody,
    InitEnvResponse,
    TestSuiteListResponse,
    Test as TestModel,
    StartRunRequest,
    StartRunResponse,
    EndRunRequest,
    EndRunResponse,
    TestResultResponse,
    DeleteEnvResponse,
    TestSuiteSummary,
    TestSuiteDetail,
    APIError,
    Principal,
    TemplateEnvironmentSummary,
    TemplateEnvironmentListResponse,
    TemplateEnvironmentDetail,
    CreateTemplateFromEnvRequest,
    CreateTemplateFromEnvResponse,
    Service,
)
from src.platform.api.auth import (
    require_resource_access,
    require_resource_access_with_org,
    check_template_access,
)
from src.platform.db.schema import (
    TestSuite,
    Test,
    TestMembership,
    TestRun,
    RunTimeEnvironment,
    OrganizationMembership,
    TemplateEnvironment,
)
from src.platform.evaluationEngine.core import CoreEvaluationEngine
from src.platform.evaluationEngine.differ import Differ
from src.platform.evaluationEngine.models import DiffResult
from src.platform.isolationEngine.core import CoreIsolationEngine

logger = logging.getLogger(__name__)


def _uuid_from_path_param(path_param: str) -> UUID:
    try:
        return UUID(path_param)
    except ValueError:
        raise ValueError(f"invalid UUID: {path_param}") from None


def _principal_from_request(request: Request) -> Principal:
    principal = getattr(request.state, "principal", None)
    if not principal:
        raise PermissionError("missing principal context")
    return principal


async def list_environment_templates(
    request: Request,
) -> JSONResponse:
    session = request.state.db_session
    principal = _principal_from_request(request)

    query = session.query(TemplateEnvironment)
    if not principal.is_platform_admin:
        query = query.filter(
            or_(
                TemplateEnvironment.owner_scope == "public",
                and_(
                    TemplateEnvironment.owner_scope == "org",
                    TemplateEnvironment.owner_org_id.in_(principal.org_ids),
                ),
                and_(
                    TemplateEnvironment.owner_scope == "user",
                    TemplateEnvironment.owner_user_id == principal.user_id,
                ),
            )
        )

    templates = query.order_by(TemplateEnvironment.created_at.desc()).all()

    response = TemplateEnvironmentListResponse(
        templates=[
            TemplateEnvironmentSummary(
                id=template.id,
                service=template.service,
                description=template.description,
                name=template.name,
            )
            for template in templates
        ]
    )
    return JSONResponse(response.model_dump(mode="json"))


async def get_environment_template(
    request: Request,
) -> JSONResponse:
    template_id = request.path_params["template_id"]
    session = request.state.db_session
    principal = _principal_from_request(request)

    try:
        parsed_id = _uuid_from_path_param(template_id)
    except ValueError:
        return JSONResponse(
            APIError(detail="invalid template id").model_dump(),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    template = (
        session.query(TemplateEnvironment)
        .filter(TemplateEnvironment.id == parsed_id)
        .one_or_none()
    )
    if template is None:
        return JSONResponse(
            APIError(detail="template not found").model_dump(),
            status_code=status.HTTP_404_NOT_FOUND,
        )

    try:
        check_template_access(principal, template)
    except PermissionError:
        return JSONResponse(
            APIError(detail="unauthorized").model_dump(),
            status_code=status.HTTP_403_FORBIDDEN,
        )

    response = TemplateEnvironmentDetail(
        id=template.id,
        service=template.service,
        description=template.description,
        name=template.name,
        version=template.version,
        schemaName=template.location,
    )
    return JSONResponse(response.model_dump(mode="json"))


async def create_template_from_environment(request: Request) -> JSONResponse:
    try:
        payload = CreateTemplateFromEnvRequest(**(await request.json()))
    except (json.JSONDecodeError, ValidationError) as e:
        return JSONResponse(
            APIError(detail=str(e)).model_dump(),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    principal = _principal_from_request(request)
    owner_scope = payload.ownerScope
    owner_user_id: str | None = None
    owner_org_id: str | None = None
    if owner_scope == "user":
        owner_user_id = principal.user_id
    elif owner_scope == "org":
        if len(principal.org_ids) == 1:
            owner_org_id = principal.org_ids[0]
        else:
            return JSONResponse(
                APIError(
                    detail="ownerScope=org requires membership in exactly one org or explicit ownerOrgId (not yet supported)"
                ).model_dump(),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    elif owner_scope == "public":
        pass
    else:
        return JSONResponse(
            APIError(detail="invalid ownerScope").model_dump(),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    core: CoreIsolationEngine = request.app.state.coreIsolationEngine
    try:
        result = core.create_template_from_environment(
            environment_id=payload.environmentId,
            service=payload.service,
            name=payload.name,
            description=payload.description,
            owner_scope=owner_scope,
            owner_user_id=owner_user_id,
            owner_org_id=owner_org_id,
            version=payload.version or "v1",
        )
    except ValueError as e:
        return JSONResponse(
            APIError(detail=str(e)).model_dump(),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return JSONResponse(
        CreateTemplateFromEnvResponse(
            templateId=result.template_id,
            schemaName=result.schema_name,
            service=Service(result.service),
            name=result.name,
        ).model_dump(mode="json")
    )


async def list_test_suites(request: Request) -> JSONResponse:
    session = request.state.db_session
    principal = _principal_from_request(request)
    suites = (
        session.query(TestSuite)
        .order_by(TestSuite.created_at.desc())
        .filter(
            or_(
                TestSuite.visibility == "public",
                TestSuite.owner == principal.user_id,
            )
        )
        .all()
    )
    response = TestSuiteListResponse(
        testSuites=[
            TestSuiteSummary(
                id=s.id,
                name=s.name,
                description=s.description,
            )
            for s in suites
        ]
    )
    return JSONResponse(response.model_dump(mode="json"))


async def get_test_suite(request: Request) -> JSONResponse:
    suite_id = request.path_params["suite_id"]
    session = request.state.db_session
    principal = _principal_from_request(request)

    suite = session.query(TestSuite).filter(TestSuite.id == suite_id).one_or_none()
    if suite is None:
        return JSONResponse(
            APIError(detail="test suite not found").model_dump(),
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if suite.visibility == "private":
        try:
            require_resource_access(principal, suite.owner)
        except PermissionError:
            return JSONResponse(
                APIError(detail="unauthorized").model_dump(),
                status_code=status.HTTP_403_FORBIDDEN,
            )

    tests = (
        session.query(Test)
        .join(TestMembership, TestMembership.test_id == Test.id)
        .filter(TestMembership.test_suite_id == suite_id)
        .all()
    )
    payload = TestSuiteDetail(
        id=suite.id,
        name=suite.name,
        description=suite.description,
        owner=suite.owner,
        visibility=suite.visibility,
        created_at=suite.created_at,
        updated_at=suite.updated_at,
        tests=[
            TestModel(
                id=t.id,
                name=t.name,
                prompt=t.prompt,
                type=t.type,
                expected_output=t.expected_output,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in tests
        ],
    )
    return JSONResponse(payload.model_dump(mode="json"))


async def init_environment(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(
            APIError(detail="invalid JSON in request body").model_dump(),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        body = InitEnvRequestBody(**data)
    except ValidationError as e:
        return JSONResponse(
            APIError(detail=str(e)).model_dump(),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    session = request.state.db_session
    principal = _principal_from_request(request)

    # Resolve template via testId, templateId, or service+name. Fallback to legacy templateSchema.
    if body.testId:
        test = session.query(Test).filter(Test.id == body.testId).one_or_none()
        if test is None:
            return JSONResponse(
                APIError(detail="test not found").model_dump(),
                status_code=status.HTTP_404_NOT_FOUND,
            )

        test_suite = (
            session.query(TestSuite)
            .join(TestMembership, TestMembership.test_suite_id == TestSuite.id)
            .filter(TestMembership.test_id == body.testId)
            .first()
        )
        if test_suite and test_suite.visibility == "private":
            try:
                require_resource_access(principal, test_suite.owner)
            except PermissionError:
                return JSONResponse(
                    APIError(detail="unauthorized").model_dump(),
                    status_code=status.HTTP_403_FORBIDDEN,
                )
        schema = body.templateSchema or test.template_schema

    else:
        schema = None
        # Preferred: templateId
        if body.templateId is not None:
            template = (
                session.query(TemplateEnvironment)
                .filter(TemplateEnvironment.id == body.templateId)
                .one_or_none()
            )
            if template is None:
                return JSONResponse(
                    APIError(detail="template not found").model_dump(),
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            try:
                check_template_access(principal, template)
            except PermissionError:
                return JSONResponse(
                    APIError(detail="unauthorized").model_dump(),
                    status_code=status.HTTP_403_FORBIDDEN,
                )
            schema = template.location
        # Next: service + name
        elif body.templateService and body.templateName:
            query = session.query(TemplateEnvironment).filter(
                TemplateEnvironment.service == body.templateService,
                TemplateEnvironment.name == body.templateName,
            )
            if not principal.is_platform_admin:
                query = query.filter(
                    or_(
                        TemplateEnvironment.owner_scope == "public",
                        and_(
                            TemplateEnvironment.owner_scope == "org",
                            TemplateEnvironment.owner_org_id.in_(principal.org_ids),
                        ),
                        and_(
                            TemplateEnvironment.owner_scope == "user",
                            TemplateEnvironment.owner_user_id == principal.user_id,
                        ),
                    )
                )
            matches = query.order_by(TemplateEnvironment.created_at.desc()).all()
            if len(matches) == 0:
                return JSONResponse(
                    APIError(detail="template not found").model_dump(),
                    status_code=status.HTTP_404_NOT_FOUND,
                )
            if len(matches) > 1:
                return JSONResponse(
                    APIError(
                        detail="multiple templates match service+name; use templateId"
                    ).model_dump(),
                    status_code=status.HTTP_409_CONFLICT,
                )
            schema = matches[0].location
        # Legacy fallback: templateSchema
        elif body.templateSchema:
            schema = body.templateSchema
        else:
            return JSONResponse(
                APIError(
                    detail="one of templateId, (templateService+templateName), templateSchema, or testId must be provided"
                ).model_dump(),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # When not using a testId and not impersonating through a test, require impersonation hints
        if not body.impersonateUserId and not body.impersonateEmail:
            return JSONResponse(
                APIError(
                    detail="impersonateUserId or impersonateEmail must be provided when initializing without a testId"
                ).model_dump(),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    core: CoreIsolationEngine = request.app.state.coreIsolationEngine

    try:
        result = core.create_environment(
            template_schema=schema,
            ttl_seconds=body.ttlSeconds or 1800,
            created_by=principal.user_id,
            impersonate_user_id=body.impersonateUserId,
            impersonate_email=body.impersonateEmail,
        )
    except ValueError as e:
        return JSONResponse(
            APIError(detail=str(e)).model_dump(),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    service = schema.split("_")[0]
    env_url = f"/api/env/{result.environment_id}/services/{service}/"
    response = InitEnvResponse(
        environmentId=result.environment_id,
        templateSchema=schema,
        environmentUrl=env_url,
        expiresAt=result.expires_at,
        schemaName=result.schema_name,
        service=Service(service),
    )
    return JSONResponse(
        response.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
    )


async def start_run(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(
            APIError(detail="invalid JSON in request body").model_dump(),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        body = StartRunRequest(**data)
    except ValidationError as e:
        return JSONResponse(
            APIError(detail=str(e)).model_dump(),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    session = request.state.db_session
    principal = _principal_from_request(request)

    test = session.query(Test).filter(Test.id == body.testId).one_or_none()
    if test is None:
        return JSONResponse(
            APIError(detail="test not found").model_dump(),
            status_code=status.HTTP_404_NOT_FOUND,
        )

    test_suite = (
        session.query(TestSuite)
        .join(TestMembership, TestMembership.test_suite_id == TestSuite.id)
        .filter(TestMembership.test_id == body.testId)
        .first()
    )
    if test_suite and test_suite.visibility == "private":
        try:
            require_resource_access(principal, test_suite.owner)
        except PermissionError:
            return JSONResponse(
                APIError(detail="unauthorized").model_dump(),
                status_code=status.HTTP_403_FORBIDDEN,
            )

    core_eval: CoreEvaluationEngine = request.app.state.coreEvaluationEngine
    schema = request.app.state.coreIsolationEngine.get_schema_for_environment(
        body.envId
    )
    before_result = core_eval.take_before(
        schema=schema,
        environment_id=body.envId,
    )

    run = TestRun(
        test_id=body.testId,
        test_suite_id=body.testSuiteId,
        environment_id=body.envId,
        status="running",
        result=None,
        before_snapshot_suffix=before_result.suffix,
        created_by=principal.user_id,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    session.add(run)
    session.flush()

    logger.info(
        f"Started test run {run.id} for test {body.testId} in environment {body.envId}"
    )

    response = StartRunResponse(
        runId=str(run.id),
        status=run.status,
        beforeSnapshot=before_result.suffix,
    )
    return JSONResponse(
        response.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
    )


async def end_run(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(
            APIError(detail="invalid JSON in request body").model_dump(),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    try:
        body = EndRunRequest(**data)
    except ValidationError as e:
        return JSONResponse(
            APIError(detail=str(e)).model_dump(),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    session = request.state.db_session
    principal = _principal_from_request(request)

    run = session.query(TestRun).filter(TestRun.id == body.runId).one_or_none()
    if run is None:
        return JSONResponse(
            APIError(detail="run not found").model_dump(),
            status_code=status.HTTP_404_NOT_FOUND,
        )

    creator_org_ids = [
        m.organization_id
        for m in session.query(OrganizationMembership).filter_by(user_id=run.created_by)
    ]
    try:
        require_resource_access_with_org(principal, run.created_by, creator_org_ids)
    except PermissionError:
        return JSONResponse(
            APIError(detail="unauthorized").model_dump(),
            status_code=status.HTTP_403_FORBIDDEN,
        )

    core_eval: CoreEvaluationEngine = request.app.state.coreEvaluationEngine
    rte = (
        session.query(RunTimeEnvironment)
        .filter(RunTimeEnvironment.id == run.environment_id)
        .one()
    )

    after = core_eval.take_after(
        schema=rte.schema, environment_id=str(run.environment_id)
    )
    evaluation: dict[str, Any]
    diff_payload: DiffResult | None = None
    try:
        diff_payload = core_eval.compute_diff(
            schema=rte.schema,
            environment_id=str(run.environment_id),
            before_suffix=run.before_snapshot_suffix,
            after_suffix=after.suffix,
        )
        differ = Differ(
            schema=rte.schema,
            environment_id=str(run.environment_id),
            session_manager=request.app.state.sessions,
        )
        differ.store_diff(
            diff_payload,
            before_suffix=run.before_snapshot_suffix,
            after_suffix=after.suffix,
        )
        spec = session.query(Test).filter(Test.id == run.test_id).one()
        evaluation = core_eval.evaluate(
            compiled_spec=spec.expected_output,
            diff=diff_payload,
        )
        run.status = "passed" if evaluation.get("passed") else "failed"
        logger.info(f"Test run {run.id} completed with status {run.status}")
    except Exception as exc:  # snapshot/diff/eval failure
        logger.error(f"Test run {run.id} failed with error: {exc}")
        run.status = "error"
        evaluation = {
            "passed": False,
            "score": {"passed": 0, "total": 0, "percent": 0.0},
            "failures": [
                f"Runtime error during evaluation: {exc.__class__.__name__}: {exc}"
            ],
        }
    if diff_payload is not None:
        evaluation.setdefault("diff", diff_payload)
    run.result = evaluation
    run.after_snapshot_suffix = after.suffix
    run.updated_at = datetime.now()

    response = EndRunResponse(
        runId=str(run.id),
        status=run.status,
        passed=bool(evaluation.get("passed")),
        score=evaluation.get("score"),
    )
    return JSONResponse(response.model_dump(mode="json"))


async def get_run_result(request: Request) -> JSONResponse:
    run_id = request.path_params["run_id"]
    session = request.state.db_session
    principal = _principal_from_request(request)

    run = session.query(TestRun).filter(TestRun.id == run_id).one_or_none()
    if run is None:
        return JSONResponse(
            APIError(detail="run not found").model_dump(),
            status_code=status.HTTP_404_NOT_FOUND,
        )

    creator_org_ids = [
        m.organization_id
        for m in session.query(OrganizationMembership).filter_by(user_id=run.created_by)
    ]
    try:
        require_resource_access_with_org(principal, run.created_by, creator_org_ids)
    except PermissionError:
        return JSONResponse(
            APIError(detail="unauthorized").model_dump(),
            status_code=status.HTTP_403_FORBIDDEN,
        )

    payload = TestResultResponse(
        runId=str(run.id),
        status=run.status,
        passed=bool(run.result.get("passed") if run.result else False),
        score=run.result.get("score") if run.result else None,
        failures=run.result.get("failures") if run.result else [],
        diff=run.result.get("diff") if run.result else None,
        createdAt=run.created_at,
    )
    return JSONResponse(payload.model_dump(mode="json"))


async def delete_environment(request: Request) -> JSONResponse:
    env_id = request.path_params["env_id"]
    session = request.state.db_session
    principal = _principal_from_request(request)

    env = (
        session.query(RunTimeEnvironment)
        .filter(RunTimeEnvironment.id == env_id)
        .one_or_none()
    )
    if env is None:
        return JSONResponse(
            APIError(detail="environment not found").model_dump(),
            status_code=status.HTTP_404_NOT_FOUND,
        )

    creator_org_ids = [
        m.organization_id
        for m in session.query(OrganizationMembership).filter_by(user_id=env.created_by)
    ]
    try:
        require_resource_access_with_org(principal, env.created_by, creator_org_ids)
    except PermissionError:
        return JSONResponse(
            APIError(detail="unauthorized").model_dump(),
            status_code=status.HTTP_403_FORBIDDEN,
        )

    core: CoreIsolationEngine = request.app.state.coreIsolationEngine
    core.environment_handler.drop_schema(env.schema)
    core.environment_handler.mark_environment_status(env_id, "deleted")

    response = DeleteEnvResponse(environmentId=str(env_id), status="deleted")
    return JSONResponse(response.model_dump(mode="json"))


async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "healthy", "service": "diff-the-universe"})


routes = [
    Route("/health", health_check, methods=["GET"]),
    Route("/testSuites", list_test_suites, methods=["GET"]),
    Route("/testSuites/{suite_id}", get_test_suite, methods=["GET"]),
    Route("/templates", list_environment_templates, methods=["GET"]),
    Route("/templates/{template_id}", get_environment_template, methods=["GET"]),
    Route(
        "/templates/from-environment",
        create_template_from_environment,
        methods=["POST"],
    ),
    Route("/initEnv", init_environment, methods=["POST"]),
    Route("/startRun", start_run, methods=["POST"]),
    Route("/endRun", end_run, methods=["POST"]),
    Route("/results/{run_id}", get_run_result, methods=["GET"]),
    Route("/env/{env_id}", delete_environment, methods=["DELETE"]),
]
