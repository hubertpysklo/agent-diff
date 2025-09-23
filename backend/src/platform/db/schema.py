from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Enum, UniqueConstraint, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ForeignKey
from datetime import datetime
from uuid import uuid4


class PlatformBase(DeclarativeBase):
    pass


class Organization(PlatformBase):
    __tablename__ = "organizations"
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
    userId: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    organizationId: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), primary_key=True
    )
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class TemplateEnvironment(PlatformBase):
    __tablename__ = "environments"
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
        {"schema": "meta"},  # keep control-plane out of state routing
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
        {"schema": "meta"},
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
