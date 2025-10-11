from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.src.platform.db.schema import RunTimeEnvironment


class SessionManager:
    def __init__(
        self,
        base_engine: Engine,
    ):
        self.base_engine = base_engine

    def get_meta_session(self):
        """
        Returns a raw session for platform database.
        Caller MUST manually commit/rollback and close the session.
        Use with_meta_session() instead for automatic cleanup.
        """
        return sessionmaker(bind=self.base_engine)(expire_on_commit=False)

    @contextmanager
    def with_meta_session(self):
        session = self.get_meta_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def lookup_environment(self, env_id: str):
        env_uuid = self._to_uuid(env_id)
        with Session(bind=self.base_engine) as s:
            env = (
                s.query(RunTimeEnvironment)
                .filter(RunTimeEnvironment.id == env_uuid)
                .one_or_none()
            )
            if env is None or env.status != "ready":
                raise PermissionError("environment not available")
            env.lastUsedAt = datetime.now()
            s.commit()
            return env.schema, env.lastUsedAt

    def get_session_for_schema(self, schema: str):
        """
        Returns a raw session bound to a specific schema.
        Caller MUST manually commit/rollback and close the session.
        Use with_session_for_schema() instead for automatic cleanup.
        """
        translated_engine = self.base_engine.execution_options(
            schema_translate_map={None: schema}
        )
        return sessionmaker(bind=translated_engine)()

    @contextmanager
    def with_session_for_schema(self, schema: str):
        session = self.get_session_for_schema(schema)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session_for_environment(self, environment_id: str):
        """
        Returns a raw session bound to an environment's schema.
        Caller MUST manually commit/rollback and close the session.
        Use with_session_for_environment() instead for automatic cleanup.
        """
        schema, _ = self.lookup_environment(environment_id)
        translated = self.base_engine.execution_options(
            schema_translate_map={None: schema}
        )
        return Session(bind=translated, expire_on_commit=False)

    @contextmanager
    def with_session_for_environment(self, environment_id: str):
        session = self.get_session_for_environment(environment_id)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _to_uuid(value: str) -> UUID:
        try:
            return UUID(value)
        except ValueError:
            return UUID(hex=value)
