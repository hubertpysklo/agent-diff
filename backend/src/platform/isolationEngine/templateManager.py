import logging
from typing import List, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import or_

from src.platform.api.auth import check_template_access, require_resource_access
from src.platform.api.models import InitEnvRequestBody
from src.platform.db.schema import (
    TemplateEnvironment,
    Test,
    TestSuite,
    TestMembership,
)

logger = logging.getLogger(__name__)


class TemplateManager:
    @staticmethod
    def parse_uuid(value: str) -> UUID | None:
        try:
            return UUID(value)
        except Exception:
            return None

    def list_templates(
        self, session: Session, principal_id: str
    ) -> List[TemplateEnvironment]:
        query = session.query(TemplateEnvironment).filter(
            or_(
                TemplateEnvironment.visibility == "public",
                TemplateEnvironment.owner_id == principal_id,
            )
        )

        all_templates = query.order_by(TemplateEnvironment.created_at.desc()).all()

        # Deduplicate by (service, name)
        seen = set()
        deduplicated = []
        for t in all_templates:
            key = (t.service, t.name)
            if key not in seen:
                seen.add(key)
                deduplicated.append(t)

        return deduplicated

    def get_template_by_id(
        self, session: Session, principal_id: str, template_id: UUID
    ) -> TemplateEnvironment:
        template = (
            session.query(TemplateEnvironment)
            .filter(TemplateEnvironment.id == template_id)
            .one_or_none()
        )
        if template is None:
            raise ValueError("template not found")

        check_template_access(principal_id, template)
        return template

    def resolve_template_schema(
        self, session: Session, principal_id: str, template_ref: str
    ) -> str:
        # Try UUID first
        maybe_uuid = self.parse_uuid(template_ref)
        if maybe_uuid:
            template = self.get_template_by_id(session, principal_id, maybe_uuid)
            return template.location

        # Parse service:name format
        service: str | None = None
        name = template_ref
        if ":" in template_ref:
            service, name = template_ref.split(":", 1)

        # Query by name (and optionally service)
        query = session.query(TemplateEnvironment).filter(
            TemplateEnvironment.name == name
        )
        if service:
            query = query.filter(TemplateEnvironment.service == service)

        # Filter by visibility
        query = query.filter(
            or_(
                TemplateEnvironment.visibility == "public",
                TemplateEnvironment.owner_id == principal_id,
            )
        )

        matches = query.order_by(TemplateEnvironment.created_at.desc()).all()
        if not matches:
            raise ValueError("template not found")

        return matches[0].location

    def resolve_init_template(
        self, session: Session, principal_id: str, body: InitEnvRequestBody
    ) -> Tuple[str, str]:
        # Path 1: testId provided
        if body.testId:
            test = session.query(Test).filter(Test.id == body.testId).one_or_none()
            if test is None:
                raise ValueError("test not found")

            # Validate access to its suite if private
            suite = (
                session.query(TestSuite)
                .join(TestMembership, TestMembership.test_suite_id == TestSuite.id)
                .filter(TestMembership.test_id == body.testId)
                .first()
            )
            if suite and suite.visibility == "private":
                require_resource_access(principal_id, suite.owner)

            schema = body.templateSchema or test.template_schema
            query = (
                session.query(TemplateEnvironment)
                .filter(TemplateEnvironment.location == schema)
                .filter(
                    or_(
                        TemplateEnvironment.visibility == "public",
                        TemplateEnvironment.owner_id == principal_id,
                    )
                )
            )
            matches = query.order_by(TemplateEnvironment.created_at.desc()).all()
            if not matches:
                raise ValueError("template schema not registered")

            t = matches[0]
            check_template_access(principal_id, t)
            return t.location, t.service

        # Path 2: templateId
        if body.templateId is not None:
            t = self.get_template_by_id(session, principal_id, body.templateId)
            return t.location, t.service

        # Path 3: service + name
        if body.templateService and body.templateName:
            query = (
                session.query(TemplateEnvironment)
                .filter(
                    TemplateEnvironment.service == body.templateService,
                    TemplateEnvironment.name == body.templateName,
                )
                .filter(
                    or_(
                        TemplateEnvironment.visibility == "public",
                        TemplateEnvironment.owner_id == principal_id,
                    )
                )
            )
            matches = query.order_by(TemplateEnvironment.created_at.desc()).all()
            if len(matches) == 0:
                raise ValueError("template not found")

            t = matches[0]
            return t.location, t.service

        # Path 4: templateSchema
        if body.templateSchema:
            query = (
                session.query(TemplateEnvironment)
                .filter(TemplateEnvironment.location == body.templateSchema)
                .filter(
                    or_(
                        TemplateEnvironment.visibility == "public",
                        TemplateEnvironment.owner_id == principal_id,
                    )
                )
            )
            matches = query.order_by(TemplateEnvironment.created_at.desc()).all()
            if not matches:
                raise ValueError("template schema not registered")

            t = matches[0]
            check_template_access(principal_id, t)
            return t.location, t.service

        raise ValueError(
            "one of templateId, (templateService+templateName), templateSchema, or testId must be provided"
        )
