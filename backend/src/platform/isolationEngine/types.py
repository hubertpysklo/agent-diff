from dataclasses import dataclass
from datetime import datetime


@dataclass
class InitEnvRequest:
    environment_schema: str
    user_id: str
    impersonate_user_id: str | None = None
    impersonate_email: str | None = None
    ttl_seconds: int = 1800
    permanent: bool = False
    max_idle_seconds: int = 1800


@dataclass
class InitEnvResult:
    environment_id: str
    user_id: str
    impersonate_user_id: str | None
    expires_at: datetime | None
