import os
import requests
from models import InitEnvRequestBody, InitEnvResponse


class AgentDiff:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.getenv("DIFF_AGENT_API_KEY")
        self.base_url = base_url or os.getenv(
            "DIFF_AGENT_BASE_URL",
        )
        if not self.api_key:
            raise ValueError(
                "API key required. Set DIFF_AGENT_API_KEY env var or pass api_key parameter"
            )
        if not self.base_url:
            raise ValueError(
                "Base URL required. Set DIFF_AGENT_BASE_URL env var or pass base_url parameter"
            )
    def init_env(self, request: InitEnvRequestBody) -> InitEnvResponse:
        response = requests.post(
            f"{self.base_url}/api/platform/initEnv",
            json=request.model_dump(mode="json"),
            headers={"Authorization": f"ApiKey {self.api_key}"},
            timeout=30,
        )
        response.raise_for_status()
        return InitEnvResponse.model_validate(response.json())

    def list_templates(self) -> List[Template]:
        pass

    def add_template(self, template: Template) -> Template:
        pass

    def list_test_suites(self) -> List[TestSuiteSummary]:
        pass

    def get_test_suite(self, suite_id: UUID) -> TestSuiteDetail:
        pass

    def get_test(self, test_id: UUID) -> Test:
        pass

    def create_test(self, test: Test, testSuiteId: UUID) -> Test:
        pass

    def create_test_suite(self, test_suite: TestSuite) -> TestSuite:

    def take_before_snapshot(self, env_id: str) -> BeforeSnapshotResponse:
        pass

    def take_after_snapshot(self, env_id: str) -> AfterSnapshotResponse:
        pass

    def get_diff(self, before_suffix: str, after_suffix: str) -> Diff:
        pass  # This function should accept aither a runId or just pure test written in DSL

    def evaluate(self, before_suffix: str, after_suffix: str, expected_output: dict) -> Evaluation:
        pass  # This function should accept aither a runId or just pure test written in DSL

    def start_run(self, run: Run) -> Run:
        pass

    def end_run(self, run_id: str) -> Run:
        pass

    def get_results_for_run(self, run_id: str) -> TestResultResponse:
        pass

    def delete_env(self, env_id: str) -> DeleteEnvResponse:
        pass


