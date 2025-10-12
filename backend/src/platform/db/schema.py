from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Enum, UniqueConstraint, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID as PgUUID, JSONB
from sqlalchemy import ForeignKey, Text
from datetime import datetime
from uuid import uuid4, UUID as PyUUID


class PlatformBase(DeclarativeBase):
    pass


class Organization(PlatformBase):
    __tablename__ = "organizations"
    __table_args__ = ({"schema": "public"},)
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )


class User(PlatformBase):
    __tablename__ = "users"
    __table_args__ = ({"schema": "public"},)
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_organization_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )


class OrganizationMembership(PlatformBase):
    __tablename__ = "organization_memberships"
    __table_args__ = ({"schema": "public"},)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TemplateEnvironment(PlatformBase):
    __tablename__ = "environments"
    __table_args__ = ({"schema": "public"},)
    __table_args__ = (
        UniqueConstraint(
            "service",
            "owner_scope",
            "owner_org_id",
            "owner_user_id",
            "name",
            "version",
            name="uq_environments_identity",
        ),
        {"schema": "public"},
    )

    id: Mapped[PyUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    service: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # 'linear', 'slack', …
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    owner_scope: Mapped[str] = mapped_column(
        Enum("global", "org", "user", name="owner_scope"),
        nullable=False,
        default="global",
    )
    owner_org_id: Mapped[str | None] = mapped_column(nullable=True)
    owner_user_id: Mapped[str | None] = mapped_column(nullable=True)
    kind: Mapped[str] = mapped_column(
        Enum("schema", "artifact", "jsonb", name="template_kind"),
        nullable=False,
        default="schema",
    )
    location: Mapped[str] = mapped_column(
        String(512), nullable=False
    )  # schema_name or s3://… URI
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )


class RunTimeEnvironment(PlatformBase):
    __tablename__ = "run_time_environments"
    __table_args__ = (
        UniqueConstraint("schema", name="uq_run_time_environments_schema"),
        {"schema": "public"},
    )

    id: Mapped[PyUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    environment_id: Mapped[PyUUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )
    template_id: Mapped[PyUUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )
    schema: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("initializing", "ready", "expired", "deleted", name="test_state_status"),
        nullable=False,
        default="initializing",
    )
    permanent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    max_idle_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    impersonate_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    impersonate_email: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ApiKey(PlatformBase):
    __tablename__ = "api_keys"
    __table_args__ = ({"schema": "public"},)
    id: Mapped[PyUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    key_salt: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Diff(PlatformBase):
    __tablename__ = "diffs"
    __table_args__ = ({"schema": "public"},)
    id: Mapped[PyUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    environment_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("run_time_environments.id"), nullable=False
    )
    before_suffix: Mapped[str] = mapped_column(String(255), nullable=False)
    after_suffix: Mapped[str] = mapped_column(String(255), nullable=False)
    diff: Mapped[JSONB] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Test(PlatformBase):
    __tablename__ = "tests"
    __table_args__ = ({"schema": "public"},)
    id: Mapped[PyUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(
        Enum("actionEval", "retriEval", "compositeEval", name="test_type"),
        nullable=False,
    )
    expected_output: Mapped[JSONB] = mapped_column(JSONB, nullable=False)
    template_schema: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TestSuite(PlatformBase):
    __tablename__ = "test_suites"
    __table_args__ = ({"schema": "public"},)
    id: Mapped[PyUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    visibility: Mapped[str] = mapped_column(
        Enum("public", "private", name="test_suite_visibility"),
        nullable=False,
        default="private",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TestMembership(PlatformBase):
    __tablename__ = "test_memberships"
    __table_args__ = ({"schema": "public"},)
    id: Mapped[PyUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    test_id: Mapped[PyUUID] = mapped_column(ForeignKey("tests.id"), nullable=False)
    test_suite_id: Mapped[PyUUID] = mapped_column(
        ForeignKey("test_suites.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TestRun(PlatformBase):
    __tablename__ = "test_runs"
    __table_args__ = ({"schema": "public"},)
    id: Mapped[PyUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    test_id: Mapped[PyUUID] = mapped_column(ForeignKey("tests.id"), nullable=False)
    test_suite_id: Mapped[PyUUID | None] = mapped_column(
        ForeignKey("test_suites.id"), nullable=True
    )
    environment_id: Mapped[PyUUID] = mapped_column(
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
    before_snapshot_suffix: Mapped[str | None] = mapped_column(String(255), nullable=True)
    after_snapshot_suffix: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
