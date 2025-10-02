from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import (
    Integer,
    String,
    DateTime,
    ForeignKey,
    Boolean,
    Text,
    Float,
    Date,
    UniqueConstraint,
)
from datetime import datetime
from datetime import timezone
from datetime import date
from sqlalchemy.dialects.postgresql import JSONB


class LinearBase(DeclarativeBase):
    pass

class Organization(LinearBase):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    urlKey: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    allowedAuthServices: Mapped[list[str]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    region: Mapped[str] = mapped_column(String(32), default="us", nullable=False)
    allowMembersToInvite: Mapped[bool] = mapped_column(Boolean, default=True)
    restrictLabelManagementToAdmins: Mapped[bool] = mapped_column(
        Boolean, default=False
    )
    restrictTeamCreationToAdmins: Mapped[bool] = mapped_column(Boolean, default=False)
    archivedAt: Mapped[datetime | None] = mapped_column(DateTime)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    teams: Mapped[list["Team"]] = relationship(
        "Team",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    projects: Mapped[list["Project"]] = relationship(
        "Project",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    domains: Mapped[list["OrganizationDomain"]] = relationship(
        "OrganizationDomain",
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class OrganizationDomain(LinearBase):
    __tablename__ = "organization_domains"
    __table_args__ = (
        UniqueConstraint("organizationId", "name", name="uq_org_domain_org_name"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organizationId: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id"), nullable=False
    )
    creatorId: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    authType: Mapped[str] = mapped_column(String(32), default="general", nullable=False)
    claimed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    disableOrganizationCreation: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    verificationEmail: Mapped[str | None] = mapped_column(String(255))
    verificationString: Mapped[str | None] = mapped_column(String(255))
    archivedAt: Mapped[datetime | None] = mapped_column(DateTime)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="domains"
    )
    creator: Mapped["User" | None] = relationship("User")


class OrganizationMembership(LinearBase):
    __tablename__ = "organization_memberships"
    userId: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id"), primary_key=True
    )
    organizationId: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id"), primary_key=True
    )
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Team(LinearBase):
    __tablename__ = "teams"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organizationId: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id")
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    displayName: Mapped[str] = mapped_column(String(100), nullable=False)
    defaultIssueStateId: Mapped[str] = mapped_column(
        String(64), ForeignKey("workflow_states.id")
    )
    inviteHash: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    key: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # e.g., "ENG" The team's unique key. The key is used in URLs.

    joinByDefault: Mapped[bool] = mapped_column(Boolean, default=True)
    private: Mapped[bool] = mapped_column(Boolean, default=False)
    archivedAt: Mapped[datetime | None] = mapped_column(DateTime)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="teams",
    )
    issues: Mapped[list["Issue"]] = relationship(
        "Issue",
        back_populates="team",
        cascade="all, delete-orphan",
    )


class TeamMembership(LinearBase):
    __tablename__ = "team_memberships"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    teamId: Mapped[str] = mapped_column(String(64), ForeignKey("teams.id"))
    userId: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"))
    owner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sortOrder: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    archivedAt: Mapped[datetime | None] = mapped_column(DateTime)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class User(LinearBase):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organizationId: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id")
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    displayName: Mapped[str] = mapped_column(String(100), nullable=False)
    admin: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    canAccessAnyPublicTeam: Mapped[bool] = mapped_column(Boolean, default=False)
    isAssignable: Mapped[bool] = mapped_column(Boolean, default=True)
    isMentionable: Mapped[bool] = mapped_column(Boolean, default=True)
    url: Mapped[str] = mapped_column(String(255), nullable=False)  # User's profile URL.
    archivedAt: Mapped[datetime | None] = mapped_column(DateTime)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="users",
    )
    assignedIssues: Mapped[list["Issue"]] = relationship(
        "Issue",
        foreign_keys="Issue.assigneeId",
        back_populates="assignee",
    )


class Issue(LinearBase):
    __tablename__ = "issues"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    teamId: Mapped[str] = mapped_column(
        String(64), ForeignKey("teams.id")
    )
    creatorId: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"))
    assigneeId: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"))
    projectId: Mapped[str | None] = mapped_column(String(64), ForeignKey("projects.id"))
    projectMilestoneId: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("project_milestones.id")
    )
    stateId: Mapped[str] = mapped_column(String(64), ForeignKey("workflow_states.id"))
    identifier: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False
    )  # e.g., "ENG-123" The issue's unique identifier.
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(
        Integer, default=0
    )  # 0=None, 1=Urgent, 2=High, 3=Normal, 4=Low
    parentId: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("issues.id")
    )  # ID of the parent issue if the issue is a sub-issue
    number: Mapped[float] = mapped_column(Float, nullable=False)
    labelIds: Mapped[list[str]] = mapped_column(
        JSONB
    )  # This is a list of label IDs. If we want to check lebels for the issue, we need to use the ids and get the labels from the labels table.
    dueDate: Mapped[date | None] = mapped_column(Date)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    completedAt: Mapped[datetime | None] = mapped_column(DateTime)
    canceledAt: Mapped[datetime | None] = mapped_column(DateTime)
    team: Mapped["Team"] = relationship(
        "Team",
        back_populates="issues",
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment",
        foreign_keys="Attachment.issueId",
        back_populates="issue",
        cascade="all, delete-orphan",
    )
    originalAttachments: Mapped[list["Attachment"]] = relationship(
        "Attachment",
        foreign_keys="Attachment.originalIssueId",
        back_populates="originalIssue",
    )
    assignee: Mapped["User" | None] = relationship(
        "User",
        foreign_keys=[assigneeId],
        back_populates="assignedIssues",
    )
    blocks: Mapped[list["IssueRelation"]] = relationship(
        "IssueRelation",
        foreign_keys="IssueRelation.issueId",
        back_populates="issue",
        cascade="all, delete-orphan",
    )
    blocked_by: Mapped[list["IssueRelation"]] = relationship(
        "IssueRelation",
        foreign_keys="IssueRelation.relatedIssueId",
        back_populates="relatedIssue",
        cascade="all, delete-orphan",
    )


class Project(LinearBase):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organizationId: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id")
    )
    url: Mapped[str] = mapped_column(String(255), nullable=False)
    creatorId: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"))
    leadId: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    labelIds: Mapped[list[str]] = mapped_column(JSONB)
    slugId: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    convertedFromIssueId: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("issues.id")
    )
    statusId: Mapped[str] = mapped_column(String(64), ForeignKey("project_statuses.id"))
    statusType: Mapped[str | None] = mapped_column(String(32))
    completedAt: Mapped[datetime | None] = mapped_column(DateTime)
    startDate: Mapped[date | None] = mapped_column(Date)
    startedAt: Mapped[datetime | None] = mapped_column(DateTime)
    canceledAt: Mapped[datetime | None] = mapped_column(DateTime)
    trashed: Mapped[bool] = mapped_column(Boolean, default=False)
    targetDate: Mapped[date | None] = mapped_column(Date)
    archivedAt: Mapped[datetime | None] = mapped_column(DateTime)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="projects",
    )


class ProjectMember(LinearBase):
    __tablename__ = "project_members"
    userId: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id"), primary_key=True
    )
    projectId: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.id"), primary_key=True
    )
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Comment(LinearBase):
    __tablename__ = "comments"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    issueId: Mapped[str | None] = mapped_column(String(64), ForeignKey("issues.id"))
    url: Mapped[str] = mapped_column(String(255), nullable=False)
    userId: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"))
    parentId: Mapped[str | None] = mapped_column(String(64), ForeignKey("comments.id"))
    projectUpdateId: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("project_updates.id")
    )
    initiativeUpdateId: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("initiative_updates.id")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    archivedAt: Mapped[datetime | None] = mapped_column(DateTime)


class Label(LinearBase):
    __tablename__ = "labels"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organizationId: Mapped[str] = mapped_column(
        String(64), ForeignKey("organizations.id")
    )
    teamId: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("teams.id")
    )  # Null for workspace labels
    creatorId: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"))
    parentId: Mapped[str | None] = mapped_column(String(64), ForeignKey("labels.id"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    archivedAt: Mapped[datetime | None] = mapped_column(DateTime)


class WorkflowState(LinearBase):
    __tablename__ = "workflow_states"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    teamId: Mapped[str] = mapped_column(String(64), ForeignKey("teams.id"))
    inheritedFromId: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("workflow_states.id")
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # Backlog, Todo, In Progress, In Review, Done, Canceled, Duplicate
    position: Mapped[float] = mapped_column(Float, nullable=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    archivedAt: Mapped[datetime | None] = mapped_column(DateTime)


class IssueRelation(LinearBase):
    __tablename__ = "issue_relations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    issueId: Mapped[str] = mapped_column(String(64), ForeignKey("issues.id"), nullable=False)
    relatedIssueId: Mapped[str] = mapped_column(String(64), ForeignKey("issues.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    archivedAt: Mapped[datetime | None] = mapped_column(DateTime)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    issue: Mapped["Issue"] = relationship(
        "Issue",
        foreign_keys=[issueId],
        back_populates="blocks",
    )
    relatedIssue: Mapped["Issue"] = relationship(
        "Issue",
        foreign_keys=[relatedIssueId],
        back_populates="blocked_by",
    )

class Attachment(LinearBase):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    issueId: Mapped[str] = mapped_column(String(64), ForeignKey("issues.id"), nullable=False)
    originalIssueId: Mapped[str | None] = mapped_column(String(64), ForeignKey("issues.id"))
    creatorId: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    bodyData: Mapped[str | None] = mapped_column(Text)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    source: Mapped[dict | None] = mapped_column(JSONB)
    sourceType: Mapped[str | None] = mapped_column(String(64))
    groupBySource: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    archivedAt: Mapped[datetime | None] = mapped_column(DateTime)
    createdAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    issue: Mapped["Issue"] = relationship(
        "Issue",
        foreign_keys=[issueId],
        back_populates="attachments",
    )
    originalIssue: Mapped["Issue" | None] = relationship(
        "Issue",
        foreign_keys=[originalIssueId],
        back_populates="originalAttachments",
    )
    creator: Mapped["User" | None] = relationship("User")
