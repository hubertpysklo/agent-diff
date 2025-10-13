import logging
from .session import SessionManager
from .environment import EnvironmentHandler
from .models import EnvironmentResponse
from uuid import uuid4
from datetime import datetime, timedelta
from src.platform.db.schema import RunTimeEnvironment

logger = logging.getLogger(__name__)


class CoreIsolationEngine:
    def __init__(
        self,
        sessions: SessionManager,
        environment_handler: EnvironmentHandler,
    ):
        self.sessions = sessions
        self.environment_handler = environment_handler

    def create_environment(
        self,
        *,
        template_schema: str,
        ttl_seconds: int,
        created_by: str,
        impersonate_user_id: str | None = None,
        impersonate_email: str | None = None,
    ) -> EnvironmentResponse:
        if not self.environment_handler.schema_exists(template_schema):
            logger.error(f"Template schema '{template_schema}' does not exist")
            raise ValueError(f"template schema '{template_schema}' does not exist")

        evn_uuid = uuid4()
        environment_id = evn_uuid.hex
        environment_schema = f"state_{environment_id}"

        self.environment_handler.create_schema(environment_schema)
        self.environment_handler.migrate_schema(template_schema, environment_schema)
        self.environment_handler.seed_data_from_template(
            template_schema, environment_schema
        )

        expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
        self.environment_handler.set_runtime_environment(
            environment_id=environment_id,
            schema=environment_schema,
            expires_at=expires_at,
            last_used_at=datetime.now(),
            created_by=created_by,
            impersonate_user_id=impersonate_user_id,
            impersonate_email=impersonate_email,
        )

        logger.info(f"Created environment {environment_id} from template {template_schema} for user {created_by}")

        return EnvironmentResponse(
            environment_id=environment_id,
            schema_name=environment_schema,
            expires_at=expires_at,
            impersonate_user_id=impersonate_user_id,
            impersonate_email=impersonate_email,
        )

    def get_schema_for_environment(self, environment_id: str) -> str:
        with self.sessions.with_meta_session() as session:
            env = (
                session.query(RunTimeEnvironment)
                .filter(RunTimeEnvironment.id == environment_id)
                .one_or_none()
            )
            if env is None:
                raise ValueError("environment not found")
            return env.schema
