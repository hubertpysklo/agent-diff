import logging
from typing import Any, List, Tuple, Optional
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import or_
from src.platform.api.models import Visibility
from src.platform.api.auth import require_resource_access
from src.platform.db.schema import TestSuite, Test, TestMembership
from src.platform.evaluationEngine.compiler import DSLCompiler


logger = logging.getLogger(__name__)


class CoreTestManager:
    def __init__(self) -> None:
        self.compiler = DSLCompiler()

    def list_test_suites(
        self, session: Session, principal_id: str
    ) -> List[TestSuite]:
        suites = (
            session.query(TestSuite)
            .order_by(TestSuite.created_at.desc())
            .filter(
                or_(
                    TestSuite.visibility == "public",
                    TestSuite.owner == principal_id,
                )
            )
            .all()
        )
        return suites

    def get_test_suite(
        self, session: Session, principal_id: str, suite_id: str
    ) -> Tuple[TestSuite | None, List[Test]]:
        suite = session.query(TestSuite).filter(TestSuite.id == suite_id).one_or_none()
        if suite is None:
            return None, []

        if suite.visibility == "private":
            require_resource_access(principal_id, suite.owner)

        tests = (
            session.query(Test)
            .join(TestMembership, TestMembership.test_id == Test.id)
            .filter(TestMembership.test_suite_id == suite_id)
            .all()
        )
        return suite, tests

    def create_test_suite(
        self,
        session: Session,
        principal_id: str,
        *,
        name: str,
        description: str,
        visibility: Visibility = Visibility.private,
    ) -> TestSuite:
        suite = TestSuite(
            id=uuid4(),
            name=name,
            description=description,
            owner=principal_id,
            visibility=visibility.value,
        )
        session.add(suite)
        return suite

    def validate_dsl(self, spec: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.compiler.compile(spec)
        except Exception as e:
            raise ValueError(f"invalid DSL: {e}") from e

    def create_test(
        self,
        session: Session,
        principal_id: str,
        *,
        test_suite_id: str,
        name: str,
        prompt: str,
        type: str,
        expected_output: dict[str, Any],
        template_schema: str,
        impersonate_user_id: Optional[str] = None,
    ) -> Test:
        suite = (
            session.query(TestSuite).filter(TestSuite.id == test_suite_id).one_or_none()
        )
        if suite is None:
            raise ValueError("test suite not found")
        require_resource_access(principal_id, suite.owner)

        self.validate_dsl(expected_output)

        test = Test(
            id=uuid4(),
            name=name,
            prompt=prompt,
            type=type,
            expected_output=expected_output,
            template_schema=template_schema,
            impersonate_user_id=impersonate_user_id,
        )
        session.add(test)
        session.add(TestMembership(test_id=test.id, test_suite_id=suite.id))
        return test

    def create_tests_bulk(
        self,
        session: Session,
        principal_id: str,
        *,
        test_suite_id: str,
        items: list[dict],
        resolved_schemas: list[str],
    ) -> List[Test]:
        suite = (
            session.query(TestSuite).filter(TestSuite.id == test_suite_id).one_or_none()
        )
        if suite is None:
            raise ValueError("test suite not found")

        require_resource_access(principal_id, suite.owner)

        if len(items) != len(resolved_schemas):
            raise ValueError("items and resolved_schemas length mismatch")

        created: List[Test] = []
        for idx, item in enumerate(items):
            t = Test(
                id=uuid4(),
                name=item["name"],
                prompt=item["prompt"],
                type=item["type"],
                expected_output=item["expected_output"],
                template_schema=resolved_schemas[idx],
                impersonate_user_id=item.get("impersonateUserId"),
            )
            session.add(t)
            session.add(TestMembership(test_id=t.id, test_suite_id=suite.id))
            created.append(t)

        session.flush()
        return created

    def get_test_suite_for_test(
        self, session: Session, principal_id: str, test_id: str
    ) -> TestSuite | None:
        suite = (
            session.query(TestSuite)
            .join(TestMembership, TestMembership.test_suite_id == TestSuite.id)
            .filter(TestMembership.test_id == test_id)
            .first()
        )
        if suite is None:
            return None

        if suite.visibility == "private":
            require_resource_access(principal_id, suite.owner)
        return suite

    def get_test(self, session: Session, principal_id: str, test_id: str) -> Test:
        test = session.query(Test).filter(Test.id == test_id).one_or_none()
        if test is None:
            raise ValueError("test not found")

        self.get_test_suite_for_test(session, principal_id, test_id)
        return test
