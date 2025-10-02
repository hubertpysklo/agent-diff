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

    def get_meta_session(self) -> Session:
        return sessionmaker(bind=self.base_engine)(expire_on_commit=False)

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

    def get_session_for_schema(self, schema: str) -> Session:
        translated_engine = self.base_engine.execution_options(
            schema_translate_map={
                None: schema,
            }
        )
        return sessionmaker(bind=translated_engine)()

    def get_session_for_token(self, token: str) -> Session:
        claims = self.token_handler.decode_token(token)
        schema, _ = self.lookup_environment(claims["environment_id"])
        translated = self.base_engine.execution_options(
            schema_translate_map={None: schema}
        )
        return Session(bind=translated, expire_on_commit=False)

    def get_session_for_environment(self, environment_id: str) -> Session:
        schema, _ = self.lookup_environment(environment_id)
        translated = self.base_engine.execution_options(
            schema_translate_map={None: schema}
        )
        return Session(bind=translated, expire_on_commit=False)

    @contextmanager
    def with_session(self, token: str):
        sess = self.get_session_for_token(token)
        try:
            yield sess
            sess.commit()
        except:
            sess.rollback()
            raise
        finally:
            sess.close()
