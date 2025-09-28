from sqlalchemy import text
from backend.src.platform.isolationEngine.session import SessionManager
import json
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import MetaData
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy.sql import table, column
from sqlalchemy.sql.elements import quoted_name
from datetime import datetime


class Differ:
    def __init__(self, schema: str, session_manager: SessionManager):
        self.session_manager = session_manager
        self.schema = schema
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

    def get_updates(self, before_suffix: str, after_suffix: str) -> list[dict]:
        updates = []
        with self.engine.begin() as conn:
            for t in self.tables:
                before_table = f"{t}_snapshot_{before_suffix}"
                after_table = f"{t}_snapshot_{after_suffix}"
                q_updates = f"""
                    SELECT a.*
                    FROM {self.q(self.schema)}.{self.q(after_table)} AS a
                    LEFT JOIN {self.q(self.schema)}.{self.q(before_table)} AS b
                    ON a.id = b.id
                    WHERE b.id IS NOT NULL
                """
                rows = conn.execute(text(q_updates)).mappings().all()
                updates.extend(rows)
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

    def get_diff(self, before_suffix: str, after_suffix: str) -> list[dict]:
        inserts = self.get_inserts(before_suffix, after_suffix)
        updates = self.get_updates(before_suffix, after_suffix)
        deletes = self.get_deletes(before_suffix, after_suffix)
        return inserts + updates + deletes

    def normalize(self, data: list[dict]) -> list[dict]:
        for d in data:
            for k, v in d.items():
                if isinstance(v, datetime):
                    d[k] = v.isoformat()
                elif isinstance(v, list):
                    d[v] = self.normalize(v)
                elif isinstance(v, dict):
                    d[k] = self.normalize(v)
        return data
