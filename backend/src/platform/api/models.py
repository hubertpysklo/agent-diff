from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


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
    testId: UUID = Field(..., alias="testId")
    templateSchema: Optional[str] = Field(None, alias="templateSchema")
    ttlSeconds: Optional[int] = Field(1800, alias="ttlSeconds")
    impersonateUserId: Optional[str] = Field(None, alias="impersonateUserId")
    impersonateEmail: Optional[str] = Field(None, alias="impersonateEmail")

    class Config:
        allow_population_by_field_name = True


class InitEnvResponse(BaseModel):
    environmentId: str = Field(..., alias="environmentId")
    schemaName: str = Field(
        ..., alias="schemaName"
    )  # Changed alias from "schema" to "schemaName"
    environmentUrl: str = Field(..., alias="environmentUrl")
    expiresAt: Optional[datetime] = Field(None, alias="expiresAt")

    class Config:
        allow_population_by_field_name = True


class StartRunRequest(BaseModel):
    envId: str = Field(..., alias="envId")
    testId: UUID = Field(..., alias="testId")
    testSuiteId: Optional[UUID] = Field(None, alias="testSuiteId")


class StartRunResponse(BaseModel):
    runId: str = Field(..., alias="runId")
    status: str
    beforeSnapshot: str = Field(..., alias="beforeSnapshot")


class EndRunRequest(BaseModel):
    runId: str = Field(..., alias="runId")


class EndRunResponse(BaseModel):
    runId: str = Field(..., alias="runId")
    status: str
    passed: bool
    score: Any


class TestResultResponse(BaseModel):
    runId: str = Field(..., alias="runId")
    status: str
    passed: bool
    score: Any
    failures: List[str]
    diff: Any
    createdAt: datetime = Field(..., alias="createdAt")


class DeleteEnvResponse(BaseModel):
    environmentId: str = Field(..., alias="environmentId")
    status: str


class Principal(BaseModel):
    user_id: int
    org_ids: List[int]
    is_platform_admin: bool
    is_organization_admin: bool
