from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import or_
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from src.platform.api.models import (
    InitEnvRequestBody,
    InitEnvResponse,
    StartRunRequest,
    StartRunResponse,
    EndRunRequest,
    EndRunResponse,
    TestResultResponse,
    DeleteEnvResponse,
    TestSuiteSummary,
    TestSuiteDetail,
    TestSummary,
    APIError,
)
from src.platform.db.schema import (
    TestSuite,
    Test,
    TestMembership,
    TestRun,
    RunTimeEnvironment,
)
from src.platform.evaluationEngine.core import CoreEvaluationEngine
from src.platform.evaluationEngine.differ import Differ
from src.platform.isolationEngine.core import CoreIsolationEngine


def _principal_from_request(request: Request) -> dict[str, Any]:
    principal = getattr(request.state, "principal", None)
    if not principal:
        raise PermissionError("missing principal context")
    return principal


async def list_test_suites(request: Request) -> JSONResponse:
    session = request.state.db_session
    principal = _principal_from_request(request)
    suites = (
        session.query(TestSuite)
        .order_by(TestSuite.created_at.desc())
        .filter(
            or_(
                TestSuite.visibility == "public",
                TestSuite.owner == principal["user_id"],
            )
        )
        .all()
    )
    payload = [
        TestSuiteSummary(
            id=s.id,
            name=s.name,
            description=s.description,
        )
        for s in suites
    ]
    return JSONResponse({"testSuites": [suite.model_dump() for suite in payload]})


async def get_test_suite(request: Request) -> JSONResponse:
    suite_id = request.path_params["suite_id"]
    session = request.state.db_session
    suite = session.query(TestSuite).filter(TestSuite.id == suite_id).one_or_none()
    if suite is None:
        return JSONResponse(
            APIError(detail="test suite not found").model_dump(),
            status_code=status.HTTP_404_NOT_FOUND,
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
        tests=[
            TestSummary(id=t.id, name=t.name, prompt=t.prompt, type=t.type)
            for t in tests
        ],  # Possibly add the expected state in response later for local diff runner
    )
    return JSONResponse(payload.model_dump())


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
    test = session.query(Test).filter(Test.id == body.testId).one_or_none()
    if test is None:
        return JSONResponse(
            APIError(detail="test not found").model_dump(),
            status_code=status.HTTP_404_NOT_FOUND,
        )
    core: CoreIsolationEngine = request.app.state.coreIsolationEngine
    schema = body.templateSchema or test.template_schema

    result = core.create_environment(
        template_schema=schema,
        ttl_seconds=body.ttlSeconds or 1800,
        impersonate_user_id=body.impersonateUserId,
        impersonate_email=body.impersonateEmail,
    )

    env_url = f"/api/env/{result['environment_id']}"
    expires_at = result.get("expires_at")
    response = InitEnvResponse(
        environmentId=str(result["environment_id"]),
        environmentUrl=env_url,
        expiresAt=expires_at if isinstance(expires_at, datetime) else None,
        schemaName=str(result["schema"]),
    )
    return JSONResponse(response.model_dump(), status_code=status.HTTP_201_CREATED)


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
    test = session.query(Test).filter(Test.id == body.testId).one_or_none()
    if test is None:
        return JSONResponse(
            APIError(detail="test not found").model_dump(),
            status_code=status.HTTP_404_NOT_FOUND,
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
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    session.add(run)
    session.flush()

    response = StartRunResponse(
        runId=str(run.id),
        status=run.status,
        beforeSnapshot=before_result.suffix,
    )
    return JSONResponse(response.model_dump(), status_code=status.HTTP_201_CREATED)


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
    run = session.query(TestRun).filter(TestRun.id == body.runId).one_or_none()
    if run is None:
        return JSONResponse(
            APIError(detail="run not found").model_dump(),
            status_code=status.HTTP_404_NOT_FOUND,
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
    diff_payload: dict[str, Any] | None = None
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
    except Exception as exc:  # snapshot/diff/eval failure
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
    return JSONResponse(response.model_dump())


async def get_run_result(request: Request) -> JSONResponse:
    run_id = request.path_params["run_id"]
    session = request.state.db_session
    run = session.query(TestRun).filter(TestRun.id == run_id).one_or_none()
    if run is None:
        return JSONResponse(
            APIError(detail="run not found").model_dump(),
            status_code=status.HTTP_404_NOT_FOUND,
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
    return JSONResponse(payload.model_dump())


async def delete_environment(request: Request) -> JSONResponse:
    env_id = request.path_params["env_id"]
    session = request.state.db_session
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

    core: CoreIsolationEngine = request.app.state.coreIsolationEngine
    core.environment_handler.drop_schema(env.schema)
    core.environment_handler.mark_environment_status(env_id, "deleted")

    response = DeleteEnvResponse(environmentId=str(env_id), status="deleted")
    return JSONResponse(response.model_dump())


async def health_check(request: Request) -> JSONResponse:
    return JSONResponse({"status": "healthy", "service": "diff-the-universe"})


routes = [
    Route("/health", health_check, methods=["GET"]),
    Route("/testSuites", list_test_suites, methods=["GET"]),
    Route("/testSuites/{suite_id}", get_test_suite, methods=["GET"]),
    Route("/initEnv", init_environment, methods=["POST"]),
    Route("/startRun", start_run, methods=["POST"]),
    Route("/endRun", end_run, methods=["POST"]),
    Route("/results/{run_id}", get_run_result, methods=["GET"]),
    Route("/env/{env_id}", delete_environment, methods=["DELETE"]),
]
