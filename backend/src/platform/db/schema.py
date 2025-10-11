from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Enum, UniqueConstraint, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import ForeignKey, Text
from datetime import datetime
from uuid import uuid4


class PlatformBase(DeclarativeBase):
    pass


class Organization(PlatformBase):
    __tablename__ = "organizations"
    __table_args__ = ({"schema": "public"},)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )


class User(PlatformBase):
    __tablename__ = "users"
    __table_args__ = ({"schema": "public"},)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    isPlatformAdmin: Mapped[bool] = mapped_column(Boolean, default=False)
    isOrganizationAdmin: Mapped[bool] = mapped_column(Boolean, default=False)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )


class OrganizationMembership(PlatformBase):
    __tablename__ = "organization_memberships"
    __table_args__ = ({"schema": "public"},)
    userId: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    organizationId: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), primary_key=True
    )
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TemplateEnvironment(PlatformBase):
    __tablename__ = "environments"
    __table_args__ = ({"schema": "public"},)
    __table_args__ = (
        UniqueConstraint(
            "service",
            "ownerScope",
            "ownerOrgId",
            "ownerUserId",
            "name",
            "version",
            name="uq_environments_identity",
        ),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    service: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # 'linear', 'slack', …
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    ownerScope: Mapped[str] = mapped_column(
        Enum("global", "org", "user", name="owner_scope"),
        nullable=False,
        default="global",
    )
    ownerOrgId: Mapped[int | None] = mapped_column(nullable=True)
    ownerUserId: Mapped[int | None] = mapped_column(nullable=True)
    kind: Mapped[str] = mapped_column(
        Enum("schema", "artifact", "jsonb", name="template_kind"),
        nullable=False,
        default="schema",
    )
    location: Mapped[str] = mapped_column(
        String(512), nullable=False
    )  # schema_name or s3://… URI
    createdAt: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )


class RunTimeEnvironment(PlatformBase):
    __tablename__ = "run_time_environments"
    __table_args__ = (
        UniqueConstraint("schema", name="uq_run_time_environments_schema"),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    environmentId: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    templateId: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    schema: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("initializing", "ready", "expired", "deleted", name="test_state_status"),
        nullable=False,
        default="initializing",
    )
    permanent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expiresAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    maxIdleSeconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lastUsedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updatedAt: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )


class ApiKey(PlatformBase):
    __tablename__ = "api_keys"
    __table_args__ = ({"schema": "public"},)
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    keyHash: Mapped[str] = mapped_column(String(255), nullable=False)
    keySalt: Mapped[str] = mapped_column(String(255), nullable=False)
    expiresAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revokedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    userId: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    lastUsedAt: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Diff(PlatformBase):
    __tablename__ = "diffs"
    __table_args__ = ({"schema": "public"},)
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    environmentId: Mapped[UUID] = mapped_column(
        ForeignKey("run_time_environments.id"), nullable=False
    )
    beforeSuffix: Mapped[str] = mapped_column(String(255), nullable=False)
    afterSuffix: Mapped[str] = mapped_column(String(255), nullable=False)
    diff: Mapped[JSONB] = mapped_column(JSONB, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Test(PlatformBase):
    __tablename__ = "tests"
    __table_args__ = ({"schema": "public"},)
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(
        Enum("actionEval", "retriEval", "compositeEval", name="test_type"),
        nullable=False,
    )
    expectedOutput: Mapped[JSONB] = mapped_column(JSONB, nullable=False)
    templateSchema: Mapped[str] = mapped_column(String(255), nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TestSuite(PlatformBase):
    __tablename__ = "test_suites"
    __table_args__ = ({"schema": "public"},)
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    visibility: Mapped[str] = mapped_column(
        Enum("public", "private", name="test_suite_visibility"),
        nullable=False,
        default="private",
    )
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TestMembership(PlatformBase):
    __tablename__ = "test_memberships"
    __table_args__ = ({"schema": "public"},)
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    testId: Mapped[UUID] = mapped_column(ForeignKey("tests.id"), nullable=False)
    testSuiteId: Mapped[UUID] = mapped_column(
        ForeignKey("test_suites.id"), nullable=False
    )
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TestRun(PlatformBase):
    __tablename__ = "test_runs"
    __table_args__ = ({"schema": "public"},)
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    testId: Mapped[UUID] = mapped_column(ForeignKey("tests.id"), nullable=False)
    testSuiteId: Mapped[UUID | None] = mapped_column(
        ForeignKey("test_suites.id"), nullable=True
    )
    environmentId: Mapped[UUID] = mapped_column(
        ForeignKey("run_time_environments.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum(
            "pending",
            "running",
            "passed",
            "failed",
            "error",
            name="test_run_status",
        ),
        nullable=False,
        default="pending",
    )
    result: Mapped[JSONB | None] = mapped_column(JSONB, nullable=True)
    beforeSnapshotSuffix: Mapped[str | None] = mapped_column(String(255), nullable=True)
    afterSnapshotSuffix: Mapped[str | None] = mapped_column(String(255), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
