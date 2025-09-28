from sqlalchemy import text
from backend.src.platform.isolationEngine.session import SessionManager
import json
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import MetaData
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy.sql import table, column

from datetime import datetime


class Differ:
    def __init__(self, schema: str, session_manager: SessionManager):
        self.session_manager = session_manager
        self.schema = schema
        self.engine = session_manager.base_engine
        self.inspector = inspect(self.engine)
        self.tables = self.inspector.get_table_names(schema=self.schema)

    def create_snapshot(self, suffix: str) -> None:
        with self.engine.begin() as conn:
            for table in self.tables:
                snapshot_table = f"{table}_snapshot_{suffix}"
                sql = f""" 
                    CREATE TABLE {snapshot_table} AS 
                    SELECT * FROM {self.schema}.{table}
                """
                conn.execute(text(sql))

    def get_inserts(self, before_suffix: str, after_suffix: str) -> list[dict]:
        inserts = []
        with self.engine.begin() as conn:
            for table in self.tables:
                before_table = f"{table}_snapshot_{before_suffix}"
                after_table = f"{table}_snapshot_{after_suffix}"
                q_inserts = f"""
                    SELECT * FROM {before_table}
                    WHERE {before_table}.id NOT IN (SELECT id FROM {after_table})
                """
                rows = conn.execute(text(q_inserts)).fetchall()
                inserts.extend([dict(row) for row in rows])
        return inserts

    def get_updates(self, schema: str) -> list[dict]:
        pass

    def get_deletes(self, schema: str) -> list[dict]:
        pass

    def get_diff(self, schema: str) -> list[dict]:
        pass

    def convert_to_json(self, data: list[dict]) -> JSONB:
        return json.dumps(data)
