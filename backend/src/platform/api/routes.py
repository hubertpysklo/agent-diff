from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import or_
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from backend.src.platform.api.models import (
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
from backend.src.platform.db.schema import (
    TestSuite,
    Test,
    TestMembership,
    TestRun,
    RunTimeEnvironment,
)
from backend.src.platform.evaluationEngine.core import CoreEvaluationEngine
from backend.src.platform.evaluationEngine.differ import Differ
from backend.src.platform.isolationEngine.core import CoreIsolationEngine


def _principal_from_request(request: Request) -> dict[str, Any]:
    principal = getattr(request.state, "principal", None)
    if principal:
        return principal
    raise PermissionError("missing principal context")


async def list_test_suites(request: Request) -> JSONResponse:
    session = request.state.db_session
    suites = (
        session.query(TestSuite)
        .order_by(TestSuite.createdAt.desc())
        .filter(
            or_(
                TestSuite.visibility == "public",
                TestSuite.owner == request.state.principal.user_id,
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
        .join(TestMembership, TestMembership.testId == Test.id)
        .filter(TestMembership.testSuiteId == suite_id)
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
    data = await request.json()
    body = InitEnvRequestBody(**data)
    session = request.state.db_session
    test = session.query(Test).filter(Test.id == body.testId).one_or_none()
    if test is None:
        return JSONResponse(
            APIError(detail="test not found").model_dump(),
            status_code=status.HTTP_404_NOT_FOUND,
        )
    core: CoreIsolationEngine = request.app.state.coreIsolationEngine
    schema = body.templateSchema or test.templateSchema

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
    data = await request.json()
    body = StartRunRequest(**data)
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
        testId=body.testId,
        testSuiteId=body.testSuiteId,
        environmentId=body.envId,
        status="running",
        result=None,
        beforeSnapshotSuffix=before_result.suffix,
        createdAt=datetime.now(),
        updatedAt=datetime.now(),
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
    data = await request.json()
    body = EndRunRequest(**data)
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
        .filter(RunTimeEnvironment.id == run.environmentId)
        .one()
    )

    after = core_eval.take_after(
        schema=rte.schema, environment_id=str(run.environmentId)
    )
    evaluation: dict[str, Any]
    diff_payload: dict[str, Any] | None = None
    try:
        diff_payload = core_eval.compute_diff(
            schema=rte.schema,
            environment_id=str(run.environmentId),
            before_suffix=run.beforeSnapshotSuffix,
            after_suffix=after.suffix,
        )
        differ = Differ(
            schema=rte.schema,
            environment_id=str(run.environmentId),
            session_manager=request.app.state.sessions,
        )
        differ.store_diff(
            diff_payload,
            before_suffix=run.beforeSnapshotSuffix,
            after_suffix=after.suffix,
        )
        spec = session.query(Test).filter(Test.id == run.testId).one()
        evaluation = core_eval.evaluate(
            compiled_spec=spec.expectedOutput,
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
    run.afterSnapshotSuffix = after.suffix
    run.updatedAt = datetime.now()

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
        createdAt=run.createdAt,
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


routes = [
    Route("/testSuites", list_test_suites, methods=["GET"]),
    Route("/testSuites/{suite_id}", get_test_suite, methods=["GET"]),
    Route("/initEnv", init_environment, methods=["POST"]),
    Route("/startRun", start_run, methods=["POST"]),
    Route("/endRun", end_run, methods=["POST"]),
    Route("/results/{run_id}", get_run_result, methods=["GET"]),
    Route("/env/{env_id}", delete_environment, methods=["DELETE"]),
]
