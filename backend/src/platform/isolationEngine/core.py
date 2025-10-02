from .auth import TokenHandler
from .session import SessionManager
from contextlib import contextmanager
from .environment import EnvironmentHandler
from uuid import uuid4
from .types import InitEnvRequest, InitEnvResult
from datetime import datetime, timedelta


class CoreIsolationEngine:
    def __init__(
        self,
        token: TokenHandler,
        sessions: SessionManager,
        environment_handler: EnvironmentHandler,
    ):
        self.token = token
        self.sessions = sessions
        self.environment_handler = environment_handler

    def get_session_for_token(self, token: str):
        claims = self.token.decode_token(token)
        schema, _ = self.sessions.lookup_environment(claims["environment_id"])
        return self.sessions.get_session_for_schema(schema)

    @contextmanager
    def with_session(self, token: str):
        claims = self.token.decode_token(token)
        schema, _ = self.sessions.lookup_environment(claims["environment_id"])
        with self.sessions.get_session_for_schema(schema) as s:
            yield s

    def init_env_and_issue_token(self, request: InitEnvRequest) -> InitEnvResult:
        evn_uuid = uuid4()
        environment_id = evn_uuid.hex
        environment_schema = f"state_{environment_id}"
        self.environment_handler.create_schema(environment_schema)
        self.environment_handler.migrate_schema(
            request.environment_schema, environment_schema
        )
        self.environment_handler.seed_data_from_template(
            request.environment_schema, environment_schema
        )
        self.environment_handler.set_runtime_environment(
            environment_id=environment_id,
            schema=environment_schema,
            expires_at=datetime.now() + timedelta(seconds=request.ttl_seconds),
            last_used_at=datetime.now(),
        )
        token = self.token.issue_token(
            environment_id=environment_id,
            user_id=request.user_id,
            impersonate_user_id=request.impersonate_user_id,
            token_ttl_seconds=request.ttl_seconds,
        )
        return InitEnvResult(
            environment_id=environment_id,
            impersonate_user_id=request.impersonate_user_id,
            user_id=request.user_id,
            expires_at=datetime.now() + timedelta(seconds=request.ttl_seconds),
            token=token,
        )
