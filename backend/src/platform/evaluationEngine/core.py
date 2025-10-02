from typing import Any
from platform.evaluationEngine.compiler import DSLCompiler
from platform.evaluationEngine.differ import Differ
from platform.evaluationEngine.assertion import AssertionEngine
from platform.isolationEngine.session import SessionManager
from uuid import uuid4
from platform.evaluationEngine.testmanager import TestManager, TestSpec


"""
To do refractor TestManager from EvaluationEnvinge to services.
"""


class CoreEvaluationEngine:
    def __init__(self, sessions: SessionManager):
        self.sessions = sessions
        self.compiler = DSLCompiler()
        self.test_manager = TestManager(self.compiler, self.sessions)

    @staticmethod
    def generate_suffix(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex[:8]}"

    def compile(self, spec: dict[str, Any]) -> dict[str, Any]:
        return self.compiler.compile(spec)

    def add_test(self, test: TestSpec) -> None:
        return self.test_manager.add_test(test)

    def get_test(self, test_id: str):
        return self.test_manager.get_test(test_id)

    def take_before(
        self, *, schema: str, environment_id: str, suffix: str | None = None
    ) -> str:
        sfx = suffix or self.generate_suffix("before")
        differ = Differ(
            schema=schema, environment_id=environment_id, session_manager=self.sessions
        )
        differ.create_snapshot(sfx)
        return sfx

    def take_after(
        self, *, schema: str, environment_id: str, suffix: str | None = None
    ) -> str:
        sfx = suffix or self.generate_suffix("after")
        differ = Differ(
            schema=schema, environment_id=environment_id, session_manager=self.sessions
        )
        differ.create_snapshot(sfx)
        return sfx

    def compute_diff(
        self,
        *,
        schema: str,
        environment_id: str,
        before_suffix: str,
        after_suffix: str,
    ) -> dict[str, list[dict[str, Any]]]:
        differ = Differ(
            schema=schema, environment_id=environment_id, session_manager=self.sessions
        )
        return differ.get_diff(before_suffix, after_suffix)

    def archive(self, *, schema: str, environment_id: str, suffixes: list[str]) -> None:
        differ = Differ(
            schema=schema, environment_id=environment_id, session_manager=self.sessions
        )
        for sfx in suffixes:
            differ.archive_snapshots(sfx)

    def evaluate(
        self,
        *,
        compiled_spec: dict[str, Any],
        diff: dict[str, list[dict[str, Any]]],
    ) -> dict:
        return AssertionEngine(compiled_spec).evaluate(diff)
