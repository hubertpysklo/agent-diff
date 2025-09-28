from sqlalchemy import text
from backend.src.platform.isolationEngine.session import SessionManager
from sqlalchemy import inspect
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from backend.src.platform.db.schema import Diff
from typing import Any


class Differ:
    def __init__(
        self, schema: str, environment_id: str, session_manager: SessionManager
    ):
        self.session_manager = session_manager
        self.schema = schema
        self.environment_id = environment_id
        self.engine = session_manager.base_engine
        self.inspector = inspect(self.engine)
        self.tables = self.inspector.get_table_names(schema=self.schema)
        self.q = self.engine.dialect.identifier_preparer.quote

    def create_snapshot(self, suffix: str) -> None:
        with self.engine.begin() as conn:
            for t in self.tables:
                snapshot_table = f"{t}_snapshot_{suffix}"
                sql = f""" 
                    CREATE TABLE IF NOT EXISTS {self.q(self.schema)}.{self.q(snapshot_table)} AS 
                    SELECT * FROM {self.q(self.schema)}.{self.q(t)}
                """
                conn.execute(text(sql))

    def get_inserts(self, before_suffix: str, after_suffix: str) -> list[dict]:
        inserts = []
        with self.engine.begin() as conn:
            for t in self.tables:
                before_table = f"{t}_snapshot_{before_suffix}"
                after_table = f"{t}_snapshot_{after_suffix}"
                q_inserts = f"""
                    SELECT a.*
                    FROM {self.q(self.schema)}.{self.q(after_table)} AS a
                    LEFT JOIN {self.q(self.schema)}.{self.q(before_table)} AS b
                    ON a.id = b.id
                    WHERE b.id IS NULL
                """
                rows = conn.execute(text(q_inserts)).mappings().all()
                inserts.extend(rows)
        return inserts

    def get_updates(
        self,
        before_suffix: str,
        after_suffix: str,
        exclude_cols: list[str] | list[str] = ["id"],
    ) -> list[dict]:
        updates = []
        with self.engine.begin() as conn:
            for t in self.tables:
                before = f"{t}_snapshot_{before_suffix}"
                after = f"{t}_snapshot_{after_suffix}"

                cols = [
                    c["name"] for c in self.inspector.get_columns(t, schema=self.schema)
                ]
                compare_cols = [c for c in cols if c not in exclude_cols]
                if not compare_cols:
                    continue

                cmp_expr = " OR ".join(
                    f"a.{self.q(c)} IS DISTINCT FROM b.{self.q(c)}"
                    for c in compare_cols
                )

                sql = f"""
                    SELECT a.*
                    FROM {self.q(self.schema)}.{self.q(after)} AS a
                    JOIN {self.q(self.schema)}.{self.q(before)} AS b
                      ON a.id = b.id
                    WHERE {cmp_expr}
                """
                updates.extend(conn.exec_driver_sql(sql).mappings().all())
        return updates

    def get_deletes(self, before_suffix: str, after_suffix: str) -> list[dict]:
        deletes = []
        with self.engine.begin() as conn:
            for t in self.tables:
                before_table = f"{t}_snapshot_{before_suffix}"
                after_table = f"{t}_snapshot_{after_suffix}"
                q_deletes = f"""
                    SELECT b.*
                    FROM {self.q(self.schema)}.{self.q(before_table)} AS b
                    LEFT JOIN {self.q(self.schema)}.{self.q(after_table)} AS a
                    ON b.id = a.id
                    WHERE a.id IS NULL
                """
                rows = conn.execute(text(q_deletes)).mappings().all()
                deletes.extend(rows)
        return deletes

    def get_diff(
        self, before_suffix: str, after_suffix: str
    ) -> dict[str, list[dict[str, Any]]]:
        inserts = self.get_inserts(before_suffix, after_suffix)
        updates = self.get_updates(before_suffix, after_suffix)
        deletes = self.get_deletes(before_suffix, after_suffix)
        return {"inserts": inserts, "updates": updates, "deletes": deletes}

    def archive_snapshots(self, suffix: str) -> None:
        with self.engine.begin() as conn:
            for t in self.tables:
                snapshot_table = f"{t}_snapshot_{suffix}"
                sql = f"""
                    DROP TABLE IF EXISTS {self.q(self.schema)}.{self.q(snapshot_table)}
                """
                conn.execute(text(sql))

    def store_diff(
        self,
        diff: dict[str, list[dict[str, Any]]],
        before_suffix: str,
        after_suffix: str,
    ) -> None:
        session = self.session_manager.get_meta_session()
        try:
            diff_object = Diff(
                environmentId=self.environment_id,
                beforeSuffix=before_suffix,
                afterSuffix=after_suffix,
                diff=diff,
                createdAt=datetime.now(),
                updatedAt=datetime.now(),
            )
            session.add(diff_object)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
