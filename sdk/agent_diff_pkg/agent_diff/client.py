import os
from uuid import UUID
import requests
from .models import (
    InitEnvRequestBody,
    InitEnvResponse,
    TestSuiteListResponse,
    TemplateEnvironmentListResponse,
    TemplateEnvironmentDetail,
    CreateTestSuiteRequest,
    CreateTestSuiteResponse,
    TestSuiteDetail,
    Test,
    CreateTemplateFromEnvRequest,
    CreateTemplateFromEnvResponse,
    CreateTestsRequest,
    CreateTestsResponse,
    TestItem,
    StartRunRequest,
    StartRunResponse,
    EndRunRequest,
    EndRunResponse,
    TestResultResponse,
    DiffRunRequest,
    DiffRunResponse,
    DeleteEnvResponse,
)


class AgentDiff:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.getenv("AGENT_DIFF_API_KEY")
        self.base_url = base_url or os.getenv(
            "AGENT_DIFF_BASE_URL",
        )
        if not self.api_key:
            raise ValueError(
                "API key required. Set AGENT_DIFF_API_KEY env var or pass api_key parameter"
            )
        if not self.base_url:
            raise ValueError(
                "Base URL required. Set AGENT_DIFF_BASE_URL env var or pass base_url parameter"
            )

    def init_env(
        self, request: InitEnvRequestBody | None = None, **kwargs
    ) -> InitEnvResponse:
        """Initialize an isolated environment. Pass InitEnvRequestBody."""
        if request is None:
            request = InitEnvRequestBody(**kwargs)
        response = requests.post(
            f"{self.base_url}/api/platform/initEnv",
            json=request.model_dump(mode="json"),
            headers={"X-API-Key": self.api_key},
            timeout=30,
        )
        response.raise_for_status()
        return InitEnvResponse.model_validate(response.json())

    def create_template_from_environment(
        self, request: CreateTemplateFromEnvRequest | None = None, **kwargs
    ) -> CreateTemplateFromEnvResponse:
        """Create template from environment. Pass CreateTemplateFromEnvRequest."""
        if request is None:
            request = CreateTemplateFromEnvRequest(**kwargs)
        response = requests.post(
            f"{self.base_url}/api/platform/templates/from-environment",
            json=request.model_dump(mode="json"),
            headers={"X-API-Key": self.api_key},
            timeout=30,
        )
        response.raise_for_status()
        return CreateTemplateFromEnvResponse.model_validate(response.json())

    def list_templates(self) -> TemplateEnvironmentListResponse:
        response = requests.get(
            f"{self.base_url}/api/platform/templates",
            headers={"X-API-Key": self.api_key},
            timeout=5,
        )
        response.raise_for_status()
        return TemplateEnvironmentListResponse.model_validate(response.json())

    def get_template(self, template_id: UUID) -> TemplateEnvironmentDetail:
        response = requests.get(
            f"{self.base_url}/api/platform/templates/{template_id}",
            headers={"X-API-Key": self.api_key},
            timeout=5,
        )
        response.raise_for_status()
        return TemplateEnvironmentDetail.model_validate(response.json())

    def list_test_suites(self) -> TestSuiteListResponse:
        response = requests.get(
            f"{self.base_url}/api/platform/testSuites",
            headers={"X-API-Key": self.api_key},
            timeout=5,
        )
        response.raise_for_status()
        return TestSuiteListResponse.model_validate(response.json())

    def get_test_suite(
        self, suite_id: UUID, include_tests: bool = True
    ) -> TestSuiteDetail:
        query = "?expand=tests" if include_tests else ""
        response = requests.get(
            f"{self.base_url}/api/platform/testSuites/{suite_id}{query}",
            headers={"X-API-Key": self.api_key},
            timeout=5,
        )
        response.raise_for_status()
        return TestSuiteDetail.model_validate(response.json())

    def get_test(self, test_id: UUID) -> Test:
        response = requests.get(
            f"{self.base_url}/api/platform/tests/{test_id}",
            headers={"X-API-Key": self.api_key},
            timeout=5,
        )
        response.raise_for_status()
        return Test.model_validate(response.json())

    def create_tests(
        self, suite_id: UUID, request: CreateTestsRequest
    ) -> CreateTestsResponse:
        response = requests.post(
            f"{self.base_url}/api/platform/testSuites/{suite_id}/tests",
            json=request.model_dump(mode="json"),
            headers={"X-API-Key": self.api_key},
            timeout=10,
        )
        response.raise_for_status()
        return CreateTestsResponse.model_validate(response.json())

    def create_test(self, suite_id: UUID, test_item: dict) -> Test:
        req = CreateTestsRequest(tests=[TestItem(**test_item)])
        resp = self.create_tests(suite_id, req)
        return resp.tests[0]

    def create_test_suite(
        self, request: CreateTestSuiteRequest | None = None, **kwargs
    ) -> CreateTestSuiteResponse:
        """Create test suite. Pass CreateTestSuiteRequest."""
        if request is None:
            request = CreateTestSuiteRequest(**kwargs)
        response = requests.post(
            f"{self.base_url}/api/platform/testSuites",
            json=request.model_dump(mode="json"),
            headers={"X-API-Key": self.api_key},
            timeout=5,
        )
        response.raise_for_status()
        return CreateTestSuiteResponse.model_validate(response.json())

    def get_results_for_run(self, run_id: str):
        response = requests.get(
            f"{self.base_url}/api/platform/results/{run_id}",
            headers={"X-API-Key": self.api_key},
            timeout=10,
        )
        response.raise_for_status()
        return TestResultResponse.model_validate(response.json())

    def delete_env(self, env_id: str) -> DeleteEnvResponse:
        response = requests.delete(
            f"{self.base_url}/api/platform/env/{env_id}",
            headers={"X-API-Key": self.api_key},
            timeout=10,
        )
        response.raise_for_status()
        return DeleteEnvResponse.model_validate(response.json())

    def start_run(
        self, request: StartRunRequest | None = None, **kwargs
    ) -> StartRunResponse:
        """Start a test run (takes initial environment snapshot). Pass StartRunRequest."""
        if request is None:
            request = StartRunRequest(**kwargs)
        response = requests.post(
            f"{self.base_url}/api/platform/startRun",
            json=request.model_dump(mode="json"),
            headers={"X-API-Key": self.api_key},
            timeout=10,
        )
        response.raise_for_status()
        return StartRunResponse.model_validate(response.json())

    def evaluate_run(
        self, request: EndRunRequest | None = None, **kwargs
    ) -> EndRunResponse:
        """Evaluate a test run (computes diff and comperes to expected output in test suite). Pass EndRunRequest or runId."""
        if request is None:
            request = EndRunRequest(**kwargs)
        response = requests.post(
            f"{self.base_url}/api/platform/evaluateRun",
            json=request.model_dump(mode="json"),
            headers={"X-API-Key": self.api_key},
            timeout=10,
        )
        response.raise_for_status()
        return EndRunResponse.model_validate(response.json())

    def diff_run(
        self, request: DiffRunRequest | None = None, **kwargs
    ) -> DiffRunResponse:
        """Compute diff. Pass DiffRunRequest or kwargs (env_id, run_id, before_suffix)."""
        if request is None:
            request = DiffRunRequest(**kwargs)
        response = requests.post(
            f"{self.base_url}/api/platform/diffRun",
            json=request.model_dump(mode="json"),
            headers={"X-API-Key": self.api_key},
            timeout=10,
        )
        response.raise_for_status()
        return DiffRunResponse.model_validate(response.json())
