from typing import Any, List

from pydantic import BaseModel


class DiffResult(BaseModel):
    inserts: List[dict[str, Any]]
    updates: List[dict[str, Any]]
    deletes: List[dict[str, Any]]
