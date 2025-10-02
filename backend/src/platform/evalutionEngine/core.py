from dataclasses import dataclass
from typing import Any, Mapping

from platform.evalutionEngine.compiler import DSLCompiler
from platform.evalutionEngine.assertion import AssertionEngine
from platform.evalutionEngine.differ import Differ
from platform.isolationEngine.session import SessionManager


class TestManager:
    def __init__(
        self,
        compiler: DSLCompiler,
        assertion_engine: AssertionEngine,
        differ: Differ,
        session_manager: SessionManager,
    ):
        self.compiler = compiler
        self.assertion_engine = assertion_engine
        self.differ = differ
        self.session_manager = session_manager

    def get_test(self, test_id: str) -> Test:
        return self.test_manager.get_test(test_id)

    def add_test(self, test: Test) -> None:
        self.test_manager.add_test(test)


class TestRunner:
    def __init__(self, test_manager: TestManager, session_manager: SessionManager):
        self.test_manager = test_manager
        self.session_manager = session_manager

    def take_before_snapshot(self, test_id: str) -> dict:
        return self.test_manager.take_snapshot(test_id)

    def take_after_snapshot(self, test_id: str) -> dict:
        return self.test_manager.take_after_snapshot(test_id)

    def get_diff(self, test_id: str) -> dict:
        return self.test_manager.get_diff(test_id)

    def add_run(self, run: Run) -> None:
        self.test_manager.add_run(run)

    def get_result(self, test_id: str) -> dict:
        return self.test_manager.get_result(test_id)
