"""State containers for MCP sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class SessionState:
    env_id: str
    last_notification_id: int = 0
    cache: Dict[str, Any] = field(default_factory=dict)
