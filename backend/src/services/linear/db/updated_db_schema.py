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
from datetime import date
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects.postgresql import JSONB
from datetime import timezone
from functools import partial

class LinearBase(DeclarativeBase):
    pass


class Issue(LinearBase):
    __tablename__ = "issues"
    # activitySummary skipped
    # addedToCycleAt skipped
    addedToProjectAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))t
    addedToTeamAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=partial(datetime.now, timezone.utc), nullable=False)
    archivedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # asksExternalUserRequester skipped
    # asksRequester skipped
    assigneeId: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"))
    assignee: Mapped["User" | None] = relationship("User", back_populates="assignedIssues")
    attachments: Mapped[list["Attachment"]] = relationship("Attachment", back_populates="issue", cascade="all, delete-orphan")
    autoArchivedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    autoClosedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # boardOrder skipped
    # botActor skipped
    branchName: Mapped[str] = mapped_column(String(255), nullable=False)
    canceledAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # children are implemented below
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="issue", cascade="all, delete-orphan")
    completedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    createdAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=partial(datetime.now, timezone.utc), nullable=False)
    creatorId: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"))
    creator: Mapped["User" | None] = relationship("User", back_populates="createdIssues")
    # customerTicketCount skipped
    cycleId: Mapped[str | None] = mapped_column(String(64), ForeignKey("cycles.id"))
    cycle: Mapped["Cycle" | None] = relationship("Cycle", back_populates="issues")
    delegateId: Mapped[str | None] = mapped_column(String(64), ForeignKey("users.id"))
    delegate: Mapped["User" | None] = relationship("User", back_populates="delegatedIssues") # !!!!!!!!!
    description: Mapped[str | None] = mapped_column(String(1000))
    # descriptionState skipped
    # documentContent skipped
    dueDate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimate: Mapped[float | None] = mapped_column(Float)
    # externalUserCreator skipped
    # favorite skipped
    # formerAttachments skipped
    # formerNeeds skipped
    # history skipped
    id: Mapped[str] = mapped_column(String(64), primary_key=True, nullable=False)
    identifier: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    # incomingSuggestions skipped
    # integrationSourceType skipped
    # the next two lines deal with inverseRelations
    blocks: Mapped[list["IssueRelation"]] = relationship("IssueRelation", foreign_keys=[IssueRelation.issueId], back_populates="issue")
    blocked_by: Mapped[list["IssueRelation"]] = relationship("IssueRelation", foreign_keys=[IssueRelation.relatedIssueId], back_populates="relatedIssue")
    labels: Mapped[list["Label"]] = relationship("Label", secondary="issue_label_links", back_populates="issues") # !!!!!!!!!!!!
    # lastAppliedTemplate skipped
    # needs skipped
    number: Mapped[float] = mapped_column(Float, unique=True, nullable=False)
    parentId: Mapped[str | None] = mapped_column(String(64), ForeignKey("issues.id"))
    parent: Mapped["Issue" | None] = relationship("Issue", foreign_keys=[parentId], remote_side=[id], back_populates="children")
    children: Mapped[list["Issue"]] = relationship("Issue", foreign_keys=[parentId], back_populates="parent", cascade="all, delete-orphan") # !!!!! It deletes hicldren issues if a parent is deleted. We need to confirm if this is the way it works in Linear.
    # previousIdentifiers skipped
    priority: Mapped[float] = mapped_column(Float, unique=True, nullable=False)
    # previousIdentifiers skipped
    # priority label can be infered from priority
    # prioritySortOrder -- can be inferred during processing?
    projectId: Mapped[str | None] = mapped_column(String(64), ForeignKey("projects.id"))
    project: Mapped["Project" | None] = relationship("Project", back_populates="issues")
    # projectMilestone skipped
    # reactionData skipped
    # reactions skipped
    # recurringIssueTemplate skipped
    # slaBreachesAt skipped
    # slaHighRiskAt skipped
    # slaMediumRiskAt skipped
    # slaStartedAt skipped
    # slaType skipped
    # snoozedBy skipped
    # snoozedUntilAt skipped
    sortOrder: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # sourceComment skipped
    startedAt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # startedTriageAt skipped
    # state skipped !!!!!!!!!!!!!!!!! Maybe need to add? It is an essential attribute
    subIssueSortOrder: Mapped[float | None] = mapped_column(Float)
    # subscribers skipped
    # suggestions skipped
    # suggestionsGeneratedAt skipped
    # syncedWith skipped
    teamId: Mapped[str] = mapped_column(String(64), ForeignKey("teams.id"), nullable=False)
    team: Mapped["Team"] = relationship("Team", back_populates="issues")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    trashed: Mapped[bool] = mapped_column(Boolean, default=False) 
    # triagedAt skipped
    updatedAt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=partial(datetime.now, timezone.utc), onupdate=partial(datetime.now, timezone.utc), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)