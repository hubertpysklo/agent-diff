from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel


class Principal(BaseModel):
    user_id: str
    org_ids: List[str]
    is_platform_admin: bool
    is_organization_admin: bool


class ApiKeyResponse(BaseModel):
    token: str
    key_id: str
    expires_at: datetime
    user_id: str
    is_platform_admin: bool
    is_organization_admin: bool


class APIError(BaseModel):
    detail: str


class TestSummary(BaseModel):
    id: UUID
    name: str
    prompt: str
    type: str


class TestSuiteSummary(BaseModel):
    id: UUID
    name: str
    description: str


class TestSuiteDetail(TestSuiteSummary):
    tests: List[TestSummary]


class InitEnvRequestBody(BaseModel):
    testId: Optional[UUID] = None
    templateSchema: Optional[str] = None
    ttlSeconds: Optional[int] = None
    impersonateUserId: Optional[str] = None
    impersonateEmail: Optional[str] = None


class InitEnvResponse(BaseModel):
    environmentId: str
    schemaName: str
    service: str
    environmentUrl: str
    expiresAt: Optional[datetime]

    class Config:
        allow_population_by_field_name = True


class StartRunRequest(BaseModel):
    envId: str
    testId: UUID
    testSuiteId: Optional[UUID]


class StartRunResponse(BaseModel):
    runId: str
    status: str
    beforeSnapshot: str


class EndRunRequest(BaseModel):
    runId: str


class EndRunResponse(BaseModel):
    runId: str
    status: str
    passed: bool
    score: Any


class TestResultResponse(BaseModel):
    runId: str
    status: str
    passed: bool
    score: Any
    failures: List[str]
    diff: Any
    createdAt: datetime


class DeleteEnvResponse(BaseModel):
    environmentId: str
    status: str
