from __future__ import annotations

import json
import logging
from datetime import datetime

from pydantic import ValidationError
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from src.platform.api.models import (
    InitEnvRequestBody,
    InitEnvResponse,
    TestSuiteListResponse,
    Test as TestModel,
    CreateTestSuiteRequest,
    CreateTestSuiteResponse,
    StartRunRequest,
    StartRunResponse,
    EndRunRequest,
    EndRunResponse,
    TestResultResponse,
    DiffRunRequest,
    DiffRunResponse,
    DeleteEnvResponse,
    TestSuiteSummary,
    TestSuiteDetail,
    Principal,
    TemplateEnvironmentSummary,
    TemplateEnvironmentListResponse,
    TemplateEnvironmentDetail,
    CreateTemplateFromEnvRequest,
    CreateTemplateFromEnvResponse,
    Service,
    Visibility,
    CreateTestsRequest,
    CreateTestsResponse,
)
from src.platform.api.auth import (
    require_resource_access_with_org,
    check_template_access,
)
from src.platform.db.schema import (
    Test,
    TestRun,
    RunTimeEnvironment,
    OrganizationMembership,
    TemplateEnvironment,
)
from src.platform.evaluationEngine.core import CoreEvaluationEngine
from src.platform.evaluationEngine.differ import Differ
from src.platform.evaluationEngine.models import DiffResult
from src.platform.isolationEngine.core import CoreIsolationEngine
from src.platform.testManager.core import CoreTestManager
from src.platform.api.resolvers import (
    resolve_template_schema,
    list_templates_for_principal,
    require_environment_access,
    resolve_init_template,
    require_run_access,
    parse_uuid,
    resolve_owner_ids,
    resolve_and_validate_test_items,
    to_bulk_test_items,
)
from src.platform.api.errors import bad_request, not_found, unauthorized

logger = logging.getLogger(__name__)


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

    templates = list_templates_for_principal(session, principal)

    response = TemplateEnvironmentListResponse(
        templates=[
            TemplateEnvironmentSummary(
                id=template.id,
                service=Service(template.service),
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
        parsed_id = parse_uuid(template_id)
    except ValueError:
        return bad_request("invalid template id")

    template = (
        session.query(TemplateEnvironment)
        .filter(TemplateEnvironment.id == parsed_id)
        .one_or_none()
    )
    if template is None:
        return not_found("template not found")

    try:
        check_template_access(principal, template)
    except PermissionError:
        return unauthorized()

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
        return bad_request(
            "invalid JSON" if isinstance(e, json.JSONDecodeError) else str(e)
        )

    principal = _principal_from_request(request)
    session = request.state.db_session

    try:
        env_uuid = parse_uuid(payload.environmentId)
    except ValueError:
        return bad_request("invalid environment id")

    env = (
        session.query(RunTimeEnvironment)
        .filter(RunTimeEnvironment.id == env_uuid)
        .one_or_none()
    )
    if env is None:
        return not_found("environment not found")
    creator_org_ids = [
        m.organization_id
        for m in session.query(OrganizationMembership).filter_by(user_id=env.created_by)
    ]
    try:
        require_resource_access_with_org(principal, env.created_by, creator_org_ids)
    except PermissionError:
        return unauthorized()

    try:
        owner_user_id, owner_org_id = resolve_owner_ids(principal, payload.ownerScope)
    except ValueError as e:
        logger.warning(f"Validation error in create_template_from_environment: {e}")
        return bad_request(str(e))

    core: CoreIsolationEngine = request.app.state.coreIsolationEngine
    try:
        result = core.create_template_from_environment(
            environment_id=payload.environmentId,
            service=payload.service.value,
            name=payload.name,
            description=payload.description,
            owner_scope=payload.ownerScope.value,
            owner_user_id=owner_user_id,
            owner_org_id=owner_org_id,
            version=payload.version or "v1",
        )
    except ValueError as e:
        logger.warning(f"Template creation failed: {e}")
        return bad_request(str(e))

    return JSONResponse(
        CreateTemplateFromEnvResponse(
            templateId=result.template_id,
            templateName=result.name,
            service=Service(result.service),
        ).model_dump(mode="json")
    )


async def get_test(request: Request) -> JSONResponse:
    test_id = request.path_params["test_id"]
    session = request.state.db_session
    principal = _principal_from_request(request)
    core_tests: CoreTestManager = request.app.state.coreTestManager

    try:
        test_uuid = parse_uuid(test_id)
    except ValueError:
        return bad_request("invalid test id")

    try:
        test = core_tests.get_test(session, principal, str(test_uuid))
    except ValueError as e:
        return not_found(str(e))
    except PermissionError:
        logger.warning(f"Unauthorized test access: test_id={test_uuid}")
        return unauthorized()

    response = TestModel(
        id=test.id,
        name=test.name,
        prompt=test.prompt,
        type=test.type,
        expected_output=test.expected_output,
        created_at=test.created_at,
        updated_at=test.updated_at,
    )
    return JSONResponse(response.model_dump(mode="json"))


async def create_test_suite(request: Request) -> JSONResponse:
    try:
        body = CreateTestSuiteRequest(**(await request.json()))
    except (json.JSONDecodeError, ValidationError) as e:
        return bad_request(
            "invalid JSON" if isinstance(e, json.JSONDecodeError) else str(e)
        )

    session = request.state.db_session
    principal = _principal_from_request(request)
    core_tests: CoreTestManager = request.app.state.coreTestManager
    suite = core_tests.create_test_suite(
        session,
        principal,
        name=body.name,
        description=body.description,
        visibility=Visibility(body.visibility),
    )
    if body.tests:
        for t in body.tests:
            try:
                schema = resolve_template_schema(
                    session, principal, str(t.environmentTemplate)
                )
                core_tests.create_test(
                    session,
                    principal,
                    test_suite_id=str(suite.id),
                    name=t.name,
                    prompt=t.prompt,
                    type=t.type,
                    expected_output=t.expected_output,
                    template_schema=schema,
                    impersonate_user_id=t.impersonateUserId,
                )
            except ValueError as e:
                logger.warning(f"Test creation in suite failed: {e}")
                return bad_request(str(e))
            except PermissionError:
                logger.warning("Unauthorized test creation in suite")
                return unauthorized()
    response = CreateTestSuiteResponse(
        id=suite.id,
        name=suite.name,
        description=suite.description,
        visibility=Visibility(suite.visibility),
    )
    return JSONResponse(
        response.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
    )


async def list_test_suites(request: Request) -> JSONResponse:
    session = request.state.db_session
    principal = _principal_from_request(request)
    core_tests: CoreTestManager = request.app.state.coreTestManager
    suites = core_tests.list_test_suites(session, principal)
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
    core_tests: CoreTestManager = request.app.state.coreTestManager
    expand_param = request.query_params.get("expand", "")
    include_tests = "tests" in {p.strip() for p in expand_param.split(",") if p}
    try:
        suite, tests = core_tests.get_test_suite(session, principal, suite_id)
    except PermissionError:
        return unauthorized()
    if suite is None:
        return not_found("test suite not found")
    payload = TestSuiteDetail(
        id=suite.id,
        name=suite.name,
        description=suite.description,
        owner=suite.owner,
        visibility=Visibility(suite.visibility),
        created_at=suite.created_at,
        updated_at=suite.updated_at,
        tests=(
            [
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
            ]
            if include_tests
            else []
        ),
    )
    return JSONResponse(payload.model_dump(mode="json"))


async def init_environment(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return bad_request("invalid JSON in request body")

    try:
        body = InitEnvRequestBody(**data)
    except ValidationError as e:
        return bad_request(str(e))

    session = request.state.db_session
    principal = _principal_from_request(request)

    try:
        schema, selected_template_service = resolve_init_template(
            session, principal, body
        )
    except PermissionError:
        logger.warning("Unauthorized template access in init_environment")
        return unauthorized()
    except ValueError as e:
        logger.warning(f"Template resolution failed in init_environment: {e}")
        return bad_request(str(e))

    if not body.testId and not body.impersonateUserId and not body.impersonateEmail:
        return bad_request(
            "impersonateUserId or impersonateEmail must be provided when initializing without a testId"
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
        logger.warning(f"Environment creation failed: {e}")
        return bad_request(str(e))

    service = selected_template_service
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


async def create_tests_in_suite(request: Request) -> JSONResponse:
    suite_id = request.path_params["suite_id"]
    session = request.state.db_session
    principal = _principal_from_request(request)
    core_tests: CoreTestManager = request.app.state.coreTestManager

    try:
        body = CreateTestsRequest(**(await request.json()))
    except (json.JSONDecodeError, ValidationError) as e:
        return bad_request(str(e))

    try:
        suite, _ = core_tests.get_test_suite(session, principal, suite_id)
    except PermissionError:
        return unauthorized()
    if suite is None:
        return not_found("test suite not found")

    try:
        resolved_schemas = resolve_and_validate_test_items(
            session,
            principal,
            body.tests,
            str(body.defaultEnvironmentTemplate)
            if body.defaultEnvironmentTemplate
            else None,
        )
    except ValueError as e:
        logger.warning(f"Test item resolution/validation failed: {e}")
        return bad_request(str(e))
    except PermissionError:
        logger.warning("Unauthorized template access in bulk test creation")
        return unauthorized()

    try:
        created_tests = core_tests.create_tests_bulk(
            session,
            principal,
            test_suite_id=str(suite.id),
            items=to_bulk_test_items(body),
            resolved_schemas=resolved_schemas,
        )
    except ValueError as e:
        logger.warning(f"Bulk test persistence failed: {e}")
        return bad_request(str(e))
    except PermissionError:
        logger.warning("Unauthorized bulk test creation")
        return unauthorized()

    response = CreateTestsResponse(
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
            for t in created_tests
        ]
    )
    return JSONResponse(
        response.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
    )


async def start_run(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return bad_request("invalid JSON in request body")

    try:
        body = StartRunRequest(**data)
    except ValidationError as e:
        return bad_request(str(e))

    session = request.state.db_session
    principal = _principal_from_request(request)

    if body.testId:
        test = session.query(Test).filter(Test.id == body.testId).one_or_none()
        if test is None:
            return not_found("test not found")

    try:
        env_uuid = parse_uuid(body.envId)
    except ValueError:
        return bad_request("invalid environment id")

    try:
        _ = require_environment_access(session, principal, str(env_uuid))
    except ValueError as e:
        return not_found(str(e))
    except PermissionError:
        logger.warning(
            f"Unauthorized environment access in start_run: env_id={body.envId}"
        )
        return unauthorized()

    core_eval: CoreEvaluationEngine = request.app.state.coreEvaluationEngine
    schema = request.app.state.coreIsolationEngine.get_schema_for_environment(
        body.envId
    )
    before_result = core_eval.take_before(schema=schema, environment_id=body.envId)

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


async def evaluate_run(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return bad_request("invalid JSON in request body")

    try:
        body = EndRunRequest(**data)
    except ValidationError as e:
        return bad_request(str(e))

    session = request.state.db_session
    principal = _principal_from_request(request)

    try:
        run_uuid = parse_uuid(body.runId)
    except ValueError:
        return bad_request("invalid run id")

    try:
        run = require_run_access(session, principal, str(run_uuid))
    except ValueError as e:
        return not_found(str(e))
    except PermissionError:
        logger.warning(f"Unauthorized run access in end_run: run_id={body.runId}")
        return unauthorized()

    core_eval: CoreEvaluationEngine = request.app.state.coreEvaluationEngine
    rte = (
        session.query(RunTimeEnvironment)
        .filter(RunTimeEnvironment.id == run.environment_id)
        .one()
    )

    after = core_eval.take_after(
        schema=rte.schema, environment_id=str(run.environment_id)
    )
    diff_payload: DiffResult | None = None
    try:
        if run.before_snapshot_suffix is None:
            raise ValueError("before snapshot missing")
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
        evaluation.setdefault("diff", diff_payload.model_dump(mode="python"))
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

    try:
        run_uuid = parse_uuid(run_id)
    except ValueError:
        return bad_request("invalid run id")

    try:
        run = require_run_access(session, principal, str(run_uuid))
    except ValueError as e:
        return not_found(str(e))
    except PermissionError:
        logger.warning(f"Unauthorized run access in get_run_result: run_id={run_id}")
        return unauthorized()

    payload = TestResultResponse(
        runId=str(run.id),
        status=run.status,
        passed=bool(run.result.get("passed") if run.result else False),
        score=run.result.get("score") if run.result else None,
        failures=run.result.get("failures", []) if run.result else [],
        diff=run.result.get("diff") if run.result else None,
        createdAt=run.created_at,
    )
    return JSONResponse(payload.model_dump(mode="json"))


async def diff_run(request: Request) -> JSONResponse:
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return bad_request("invalid JSON in request body")

    try:
        body = DiffRunRequest(**data)
    except ValidationError as e:
        return bad_request(str(e))

    session = request.state.db_session
    principal = _principal_from_request(request)

    core_eval: CoreEvaluationEngine = request.app.state.coreEvaluationEngine

    has_run = bool(body.runId)
    has_pair = bool(body.envId and body.beforeSuffix)
    if has_run == has_pair:
        return bad_request("provide exactly one of runId or (envId and beforeSuffix)")

    if body.runId:
        try:
            run_uuid = parse_uuid(body.runId)
        except ValueError:
            return bad_request("invalid run id")
        try:
            run = require_run_access(session, principal, str(run_uuid))
        except ValueError as e:
            return not_found(str(e))
        except PermissionError:
            return unauthorized()
        env = (
            session.query(RunTimeEnvironment)
            .filter(RunTimeEnvironment.id == run.environment_id)
            .one()
        )
        before_suffix = run.before_snapshot_suffix
        if before_suffix is None:
            return bad_request("before snapshot missing for run")
    else:
        try:
            env_uuid = parse_uuid(body.envId or "")
        except ValueError:
            return bad_request("invalid environment id")
        try:
            env = require_environment_access(session, principal, str(env_uuid))
        except ValueError as e:
            return not_found(str(e))
        except PermissionError:
            return unauthorized()
        before_suffix = body.beforeSuffix or ""

    after = core_eval.take_after(schema=env.schema, environment_id=str(env.id))
    diff_payload = core_eval.compute_diff(
        schema=env.schema,
        environment_id=str(env.id),
        before_suffix=before_suffix,
        after_suffix=after.suffix,
    )

    response = DiffRunResponse(
        beforeSnapshot=before_suffix,
        afterSnapshot=after.suffix,
        diff=diff_payload,
    )
    return JSONResponse(response.model_dump(mode="json"))


async def delete_environment(request: Request) -> JSONResponse:
    env_id = request.path_params["env_id"]
    session = request.state.db_session
    principal = _principal_from_request(request)

    try:
        env_uuid = parse_uuid(env_id)
    except ValueError:
        return bad_request("invalid environment id")

    try:
        env = require_environment_access(session, principal, str(env_uuid))
    except ValueError as e:
        return not_found(str(e))
    except PermissionError:
        logger.warning(f"Unauthorized environment access: env_id={env_id}")
        return unauthorized()

    core: CoreIsolationEngine = request.app.state.coreIsolationEngine
    core.environment_handler.drop_schema(env.schema)
    core.environment_handler.mark_environment_status(env_id, "deleted")

    response = DeleteEnvResponse(environmentId=str(env_id), status="deleted")
    return JSONResponse(response.model_dump(mode="json"))


async def health_check(request: Request) -> JSONResponse:
    time = datetime.now()
    return JSONResponse(
        {
            "status": "healthy",
            "service": "diff-the-universe",
            "time": time.isoformat(),
        }
    )


routes = [
    Route("/health", health_check, methods=["GET"]),
    Route("/testSuites", list_test_suites, methods=["GET"]),
    Route("/testSuites", create_test_suite, methods=["POST"]),
    Route("/testSuites/{suite_id}", get_test_suite, methods=["GET"]),
    Route("/testSuites/{suite_id}/tests", create_tests_in_suite, methods=["POST"]),
    Route("/templates", list_environment_templates, methods=["GET"]),
    Route("/templates/{template_id}", get_environment_template, methods=["GET"]),
    Route(
        "/templates/from-environment",
        create_template_from_environment,
        methods=["POST"],
    ),
    Route("/initEnv", init_environment, methods=["POST"]),
    Route("/startRun", start_run, methods=["POST"]),
    Route("/evaluateRun", evaluate_run, methods=["POST"]),
    Route("/results/{run_id}", get_run_result, methods=["GET"]),
    Route("/diffRun", diff_run, methods=["POST"]),
    Route("/env/{env_id}", delete_environment, methods=["DELETE"]),
    Route("/tests/{test_id}", get_test, methods=["GET"]),
]
