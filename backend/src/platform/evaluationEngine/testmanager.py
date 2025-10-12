from dataclasses import dataclass
from typing import Any
from typing_extensions import Literal
from platform.evaluationEngine.compiler import DSLCompiler
from platform.isolationEngine.session import SessionManager
import json
from backend.src.platform.db.schema import Test


@dataclass(frozen=True)
class TestSpec:
    id: str | None
    name: str
    prompt: str
    type: Literal["actionEval", "retriEval", "compositeEval"]
    expectedOutput: str | dict[str, Any]


class TestManager:
    def __init__(
        self,
        compiler: DSLCompiler,
        session_manager: SessionManager,
    ):
        self.compiler = compiler
        self.session_manager = session_manager

    @staticmethod
    def _as_dict(v: str | dict[str, Any]) -> dict[str, Any]:
        return v if isinstance(v, dict) else json.loads(v)

    def add_test(self, test: TestSpec) -> None:
        with self.session_manager.with_meta_session() as session:
            eo = self._as_dict(test.expectedOutput)
            compiled = self.compiler.compile(eo) if test.type == "actionEval" else eo
            compiledTest = Test(
                name=test.name,
                prompt=test.prompt,
                type=test.type,
                expected_output=compiled,
            )
            session.add(compiledTest)

    def get_test(self, test_id: str) -> Test:
        with self.session_manager.with_meta_session() as session:
            test = session.query(Test).filter(Test.id == test_id).first()
            if test is None:
                raise ValueError(f"Test with id {test_id} not found")
            return test
