from datetime import datetime
from typing import Iterable
from uuid import UUID

from sqlalchemy import MetaData, text

from backend.src.platform.db.schema import RunTimeEnvironment

from .session import SessionManager


class EnvironmentHandler:
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    def create_schema(self, schema: str) -> None:
        with self.session_manager.base_engine.begin() as conn:
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

    def set_runtime_environment(
        self,
        environment_id: str,
        schema: str,
        expires_at: datetime | None,
        last_used_at: datetime,
        *,
        template_id: str | None = None,
    ) -> None:
        env_uuid = self._to_uuid(environment_id)
        template_uuid = self._to_uuid(template_id) if template_id else None
        with self.session_manager.with_meta_session() as s:
            rte = RunTimeEnvironment(
                id=env_uuid,
                schema=schema,
                status="ready",
                expiresAt=expires_at,
                lastUsedAt=last_used_at,
            )
            if template_uuid:
                rte.templateId = template_uuid  # type: ignore[attr-defined,assignment]
            s.add(rte)

    def drop_schema(self, schema: str) -> None:
        with self.session_manager.base_engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))

    def mark_environment_status(self, environment_id: str, status: str) -> None:
        env_uuid = self._to_uuid(environment_id)
        with self.session_manager.with_meta_session() as s:
            env = (
                s.query(RunTimeEnvironment)
                .filter(RunTimeEnvironment.id == env_uuid)
                .one_or_none()
            )
            if env is None:
                raise ValueError("environment not found")
            env.status = status
            env.updatedAt = datetime.now()

    @staticmethod
    def _to_uuid(value: str | None) -> UUID:
        if value is None:
            raise ValueError("UUID value cannot be None")
        try:
            return UUID(value)
        except ValueError:
            return UUID(hex=value)
