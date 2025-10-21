from __future__ import annotations
from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID
from pydantic import BaseModel


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


class TemplateEnvironmentSummary(BaseModel):
    id: UUID
    service: str
    description: str | None = None
    name: str


class TemplateEnvironmentDetail(TemplateEnvironmentSummary):
    version: str
    schemaName: str  # Location of the template environment in the database (schema_name) or S3 (s3://...)


class TemplateEnvironmentListResponse(BaseModel):
    templates: List[TemplateEnvironmentSummary]


class InitEnvRequestBody(BaseModel):
    testId: Optional[UUID] = None
    templateSchema: Optional[str] = None
    ttlSeconds: Optional[int] = None
    impersonateUserId: Optional[str] = None
    impersonateEmail: Optional[str] = None


class InitEnvResponse(BaseModel):
    environmentId: str
    templateSchema: str
    schemaName: str
    service: str
    environmentUrl: str
    expiresAt: Optional[datetime]


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
