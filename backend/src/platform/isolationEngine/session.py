from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Session, sessionmaker
from .auth import TokenHandler
from sqlalchemy import Engine
from backend.src.platform.db.schema import RunTimeEnvironment
from contextlib import contextmanager


class SessionManager:
    def __init__(
        self,
        base_engine: Engine,
        token_handler: TokenHandler,
    ):
        self.base_engine = base_engine
        self.token_handler = token_handler

    def get_meta_session(self):
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
        with Session(bind=self.base_engine) as s:
            env = (
                s.query(RunTimeEnvironment)
                .filter(RunTimeEnvironment.id == env_id)
                .one_or_none()
            )
            if env is None or env.status != "ready":
                raise PermissionError("environment not available")
            env.lastUsedAt = datetime.now()
            s.commit()
            return env.schema, env.lastUsedAt

    def get_session_for_schema(self, schema: str):
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
