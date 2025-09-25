from datetime import datetime, timedelta
from typing import Iterable
from sqlalchemy import text, MetaData
from sqlalchemy.orm import Session
from uuid import uuid4
from backend.src.platform.db.schema import RunTimeEnvironment
from .types import InitEnvRequest, InitEnvResult
from .auth import TokenHandler
from .session import SessionManager


class EnvironmentHandler:
    def __init__(self, token_handler: TokenHandler, session_manager: SessionManager):
        self.token_handler = token_handler
        self.session_manager = session_manager

    def create_schema(self, schema: str) -> None:
        with self.session_manager.get_meta_session() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))

    def migrate_schema(self, template_schema: str, target_schema: str) -> None:
        engine = self.session_manager.base_engine
        meta = MetaData()
        meta.reflect(bind=engine, schema=template_schema)
        translated = engine.execution_options(
            schema_translate_map={template_schema: target_schema}
        )
        meta.create_all(translated)

    def _list_tables(self, conn, schema: str) -> list[str]:
        rows = conn.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = :schema AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            ),
            {"schema": schema},
        ).fetchall()
        return [r[0] for r in rows]

    def _reset_sequences(self, conn, schema: str, tables: Iterable[str]) -> None:
        for tbl in tables:
            seq_name_row = conn.execute(
                text("SELECT pg_get_serial_sequence(:rel, 'id')"),
                {"rel": f"{schema}.{tbl}"},
            ).fetchone()
            if not seq_name_row or not seq_name_row[0]:
                continue
            conn.execute(
                text(
                    "SELECT setval(:seq, COALESCE((SELECT MAX(id) FROM "
                    f'"{schema}".{tbl}'
                    "), 0) + 1, false)"
                ),
                {"seq": seq_name_row[0]},
            )

    def seed_data_from_template(
        self,
        template_schema: str,
        target_schema: str,
        tables_order: list[str] | None = None,
    ) -> None:
        engine = self.session_manager.base_engine
        with engine.begin() as conn:
            meta = MetaData()
            meta.reflect(bind=engine, schema=template_schema)
            ordered = [t.name for t in meta.sorted_tables]
            for tbl in ordered:
                conn.execute(
                    text(
                        f'INSERT INTO "{target_schema}".{tbl} SELECT * FROM "{template_schema}".{tbl}'
                    )
                )
            self._reset_sequences(conn, target_schema, ordered)

    def init_env_and_issue_token(
        self,
        request: InitEnvRequest,
        *,
        secret: str,
        user_id: int,
        token_ttl_seconds: int = 1800,
    ) -> InitEnvResult:
        res = self.init_env(request)
        res.token = self.token_handler.issue_token(
            environment_id=res.environment_id,
            user_id=user_id,
            impersonate_user_id=request.impersonate_user_id,
            token_ttl_seconds=token_ttl_seconds,
        )
        return res

    def session_for_schema(self, schema: str) -> Session:
        return self.session_manager.get_session_for_schema(schema)
