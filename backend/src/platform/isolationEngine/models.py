from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class InitEnvRequest(BaseModel):
    environment_schema: str
    user_id: str
    impersonate_user_id: Optional[str] = None
    impersonate_email: Optional[str] = None
    ttl_seconds: int = 1800
    permanent: bool = False
    max_idle_seconds: int = 1800


class InitEnvResult(BaseModel):
    environment_id: str
    user_id: str
    impersonate_user_id: Optional[str]
    expires_at: Optional[datetime]


class EnvironmentResponse(BaseModel):
    environment_id: str
    schema_name: str
    expires_at: datetime
    impersonate_user_id: Optional[str] = None
    impersonate_email: Optional[str] = None
