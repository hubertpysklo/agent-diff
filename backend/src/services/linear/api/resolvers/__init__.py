# Linear GraphQL resolvers - TODO: implement

import secrets

from ariadne import ObjectType, QueryType
from graphql import GraphQLError
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from db_schema import (
    SessionLocal,
    Organization,
    OrganizationDomain,
    Team,
    TeamMembership,
    User,
    Project,
    Issue,
    Attachment,
    Label,
    IssueRelation,
)


# Query reoslvers
Query = QueryType()
ProjectStatusObject = ObjectType("ProjectStatus")
AttachmentObject = ObjectType("Attachment")
IssueObject = ObjectType("Issue")


SUPPORTED_PROJECT_FIELDS: set[str] = {
    "archivedAt",
    "canceledAt",
    "completedAt",
    "content",
    "convertedFromIssueId",
    "createdAt",
    "description",
    "id",
    "leadId",
    "name",
    "organizationId",
    "priority",
    "slugId",
    "startDate",
    "startedAt",
    "statusId",
    "statusType",
    "targetDate",
    "trashed",
    "updatedAt",
    "url",
}


class ProjectDTO:
    __slots__ = ("_project",)

    def __init__(self, project: Project):
        self._project = project

    def __getattr__(self, item: str):
        if item in SUPPORTED_PROJECT_FIELDS:
            return getattr(self._project, item)
        if item.startswith("__"):
            raise AttributeError(item)
        raise GraphQLError(f"Project field '{item}' is not available")

    @property
    def id(self) -> str:
        return self._project.id


SUPPORTED_ATTACHMENT_FIELDS: set[str] = {
    "archivedAt",
    "bodyData",
    "createdAt",
    "creator",
    "groupBySource",
    "id",
    "issue",
    "metadata",
    "originalIssue",
    "source",
    "sourceType",
    "subtitle",
    "title",
    "updatedAt",
    "url",
}


class AttachmentDTO:
    __slots__ = ("_attachment",)

    def __init__(self, attachment: Attachment):
        self._attachment = attachment

    def __getattr__(self, item: str):
        if item in SUPPORTED_ATTACHMENT_FIELDS:
            return getattr(self._attachment, item)
        if item.startswith("__"):
            raise AttributeError(item)
        raise GraphQLError(f"Attachment field '{item}' is not available")

    @property
    def id(self) -> str:
        return self._attachment.id


SUPPORTED_LABEL_FIELDS: set[str] = {
    "archivedAt",
    "createdAt",
    "description",
    "id",
    "name",
    "organizationId",
    "parentId",
    "teamId",
    "updatedAt",
}


class LabelDTO:
    __slots__ = ("_label",)

    def __init__(self, label: Label):
        self._label = label

    def __getattr__(self, item: str):
        if item in SUPPORTED_LABEL_FIELDS:
            return getattr(self._label, item)
        if item.startswith("__"):
            raise AttributeError(item)
        raise GraphQLError(f"IssueLabel field '{item}' is not available")

    @property
    def id(self) -> str:
        return self._label.id


ISSUE_PRIORITY_MAP = (
    {"priority": 0, "label": "No priority"},
    {"priority": 1, "label": "Urgent"},
    {"priority": 2, "label": "High"},
    {"priority": 3, "label": "Normal"},
    {"priority": 4, "label": "Low"},
)


def _issue_relation_connection(session, stmt, first: int | None):
    if first is not None and first <= 0:
        raise GraphQLError("first must be greater than 0")

    limit = first if first is not None else 50
    fetch_limit = limit + 1

    ordered_stmt = stmt.order_by(IssueRelation.createdAt, IssueRelation.id).limit(fetch_limit)
    relations = session.execute(ordered_stmt).scalars().all()

    has_next_page = len(relations) > limit
    if has_next_page:
        relations = relations[:limit]

    edges = [{"cursor": relation.id, "node": relation} for relation in relations]
    start_cursor = edges[0]["cursor"] if edges else None
    end_cursor = edges[-1]["cursor"] if edges else None

    return {
        "edges": edges,
        "nodes": relations,
        "pageInfo": {
            "startCursor": start_cursor,
            "endCursor": end_cursor,
            "hasNextPage": has_next_page,
            "hasPreviousPage": False,
        },
    }

# Skipped Querry:
# - organizationDomainClaimRequest
# - externalUsers


# Probably need to include?
# - organizationInvite (Need to create an ORM)
# - organizationInviteDetails?
# - organizationInvites
# - projectStatusProjectCount (am not sure whether in organizations)

# @Query.field("organization")
# def resolve_organization(_, info):
#     user_email = select(User.email)


# platform/graphql.py
from ariadne.asgi import GraphQL

class GraphQLWithSession(GraphQL):
    async def handle_request(self, request):
        token = (request.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        session = None
        try:
            session = session_provider.create_session_for_token(token)
            request.state.db_session = session
            result = await super().handle_request(request)
            session.commit()
            return result
        except Exception:
            if session:
                session.rollback()
            raise
        finally:
            if session:
                session.close()

    
@Query.field("organizationExists")
def resolve_organizationExists(_parent, info, urlKey: str):
    session = info.context.state.db_session
    created_session = False
    if session is None:
        session = SessionLocal()
        created_session = True

    try:
        stmt = (
            select(Organization.id)
            .where(func.lower(Organization.urlKey) == urlKey.lower())
            .limit(1)
        )
        exists_ = session.execute(stmt).scalar_one_or_none() is not None
        return {"exists": exists_, "success": True}
    except Exception:
        if created_session:
            session.rollback()
        return {"exists": False, "success": False}
    finally:
        if created_session:
            session.close()
            
@Query.field("organizationDomainClaimRequest")
def resolve_organizationDomainClaimRequest(_parent, info, id: str):
    session = info.context.state.db_session
    stmt = select(OrganizationDomain).where(OrganizationDomain.id == id).limit(1)
    domain = session.execute(stmt).scalars().first()

    if domain is None:
        raise GraphQLError("Organization domain not found")

    org_id = getattr(info.context.state, "org_id", None)
    if org_id is not None and domain.organizationId != org_id:
        raise GraphQLError("Access denied")

    if domain.claimed or domain.verified:
        raise GraphQLError("Domain already claimed")

    if not domain.verificationString:
        domain.verificationString = secrets.token_urlsafe(16)
        session.add(domain)
        session.flush()

    return {"verificationString": domain.verificationString}


@Query.field("organizationMeta")
def resolve_organizationMeta(_parent, info, urlKey: str):
    raw_key = (urlKey or "").strip()
    if not raw_key:
        raise GraphQLError("Invalid organization key")

    session = info.context.state.db_session
    created_session = False
    if session is None:
        session = SessionLocal()
        created_session = True

    try:
        lowered_key = raw_key.lower()
        stmt = (
            select(Organization)
            .where(
                or_(
                    func.lower(Organization.urlKey) == lowered_key,
                    Organization.id == raw_key,
                )
            )
            .limit(1)
        )
        organization = session.execute(stmt).scalars().first()

        if organization is None:
            raise GraphQLError("Organization not found")

        allowed_services = organization.allowedAuthServices or []
        if not isinstance(allowed_services, list):
            allowed_services = []

        region = organization.region or "us"

        return {
            "allowedAuthServices": allowed_services,
            "region": region,
        }
    except Exception:
        if created_session:
            session.rollback()
        raise
    finally:
        if created_session:
            session.close()


@Query.field("archivedTeams")
def resolve_archivedTeams(_parent, info):
    session = info.context.state.db_session
    org_id = getattr(info.context.state, "org_id", None) # Will have to handle this later
    if org_id is None:
        return []

    stmt = select(Team).where(Team.organizationId == org_id, Team.archivedAt.isnot(None))

    try:
        return session.scalars(stmt).all()
    except Exception:
        return []
    
# Querries Teams


# Querries Users:
# Need to implmenet:
#   - administableTeams
#   - teams    

@Query.field("team")
def resolve_team(_parent, info, id: str):
    session = info.context.state.db_session
    stmt = select(Team).where(Team.id == id).limit(1)
    team = session.execute(stmt).scalars().first()

    if team is None:
        raise GraphQLError("Team not found")  # Team! must not be null

    return team
    
@Query.field("teamMembership")
def resolve_teamMembership(_parent, info, id: str):
    session = info.context.state.db_session
    stmt = select(TeamMembership).where(TeamMembership.id == id).limit(1)
    membership = session.execute(stmt).scalars().first()

    if membership is None:
        raise GraphQLError("TeamMembership not found")

    return membership


@Query.field("issue")
def resolve_issue(_parent, info, id: str):
    session = info.context.state.db_session

    stmt = select(Issue).join(Team, Issue.teamId == Team.id).where(Issue.id == id)

    org_id = getattr(info.context.state, "org_id", None)
    if org_id is not None:
        stmt = stmt.where(Team.organizationId == org_id)

    issue = session.execute(stmt.limit(1)).scalars().first()

    if issue is None:
        raise GraphQLError("Issue not found")

    return issue


@Query.field("issueLabel")
def resolve_issueLabel(_parent, info, id: str):
    session = info.context.state.db_session

    stmt = select(Label).where(Label.id == id)

    org_id = getattr(info.context.state, "org_id", None)
    if org_id is not None:
        stmt = stmt.where(Label.organizationId == org_id)

    label = session.execute(stmt.limit(1)).scalars().first()

    if label is None:
        raise GraphQLError("IssueLabel not found")

    return LabelDTO(label)


@Query.field("issueLabels")
def resolve_issueLabels(
    _parent,
    info,
    after: str | None = None,
    before: str | None = None,
    filter: dict | None = None,
    first: int | None = None,
    includeArchived: bool | None = False,
    last: int | None = None,
    orderBy: str | None = None,
):
    unsupported_args = {
        "after": after,
        "before": before,
        "filter": filter,
        "last": last,
        "orderBy": orderBy,
    }
    if any(value is not None for value in unsupported_args.values()):
        raise GraphQLError("Pagination or filtering arguments are not supported")

    session = info.context.state.db_session

    org_id = getattr(info.context.state, "org_id", None)
    if org_id is None:
        raise GraphQLError("Organization context is missing")

    if first is not None and first <= 0:
        raise GraphQLError("first must be greater than 0")

    limit = first if first is not None else 50
    fetch_limit = limit + 1

    stmt = select(Label).where(Label.organizationId == org_id)

    if not includeArchived:
        stmt = stmt.where(Label.archivedAt.is_(None))

    stmt = stmt.order_by(Label.createdAt, Label.id).limit(fetch_limit)

    labels = session.execute(stmt).scalars().all()

    has_next_page = len(labels) > limit
    if has_next_page:
        labels = labels[:limit]

    nodes = [LabelDTO(label) for label in labels]
    edges = [
        {
            "cursor": label.id,
            "node": dto,
        }
        for label, dto in zip(labels, nodes)
    ]

    start_cursor = edges[0]["cursor"] if edges else None
    end_cursor = edges[-1]["cursor"] if edges else None

    return {
        "edges": edges,
        "nodes": nodes,
        "pageInfo": {
            "startCursor": start_cursor,
            "endCursor": end_cursor,
            "hasNextPage": has_next_page,
            "hasPreviousPage": False,
        },
    }


@Query.field("issuePriorityValues")
def resolve_issuePriorityValues(_parent, info):
    return ISSUE_PRIORITY_MAP


@Query.field("issueRelation")
def resolve_issueRelation(_parent, info, id: str):
    session = info.context.state.db_session

    stmt = (
        select(IssueRelation)
        .join(Issue, IssueRelation.issue)
        .join(Team, Issue.team)
        .where(IssueRelation.id == id)
    )

    org_id = getattr(info.context.state, "org_id", None)
    if org_id is not None:
        stmt = stmt.where(Team.organizationId == org_id)

    relation = session.execute(stmt.limit(1)).scalars().first()

    if relation is None:
        raise GraphQLError("IssueRelation not found")

    return relation


@Query.field("issueRelations")
def resolve_issueRelations(
    _parent,
    info,
    after: str | None = None,
    before: str | None = None,
    first: int | None = None,
    includeArchived: bool | None = False,
    last: int | None = None,
    orderBy: str | None = None,
):
    unsupported_args = {"after": after, "before": before, "last": last, "orderBy": orderBy}
    if any(value is not None for value in unsupported_args.values()):
        raise GraphQLError("Pagination parameters are not supported")

    session = info.context.state.db_session

    org_id = getattr(info.context.state, "org_id", None)
    if org_id is None:
        raise GraphQLError("Organization context is missing")

    stmt = (
        select(IssueRelation)
        .join(Issue, IssueRelation.issue)
        .join(Team, Issue.team)
        .where(Team.organizationId == org_id)
    )

    if not includeArchived:
        stmt = stmt.where(IssueRelation.archivedAt.is_(None))

    return _issue_relation_connection(session, stmt, first)


@IssueObject.field("relations")
def resolve_issue_relations_field(
    issue,
    info,
    after: str | None = None,
    before: str | None = None,
    first: int | None = None,
    includeArchived: bool | None = False,
    last: int | None = None,
    orderBy: str | None = None,
):
    unsupported_args = {"after": after, "before": before, "last": last, "orderBy": orderBy}
    if any(value is not None for value in unsupported_args.values()):
        raise GraphQLError("Pagination parameters are not supported")

    session = info.context.state.db_session

    stmt = select(IssueRelation).where(IssueRelation.issueId == issue.id)

    org_id = getattr(info.context.state, "org_id", None)
    if org_id is not None:
        stmt = stmt.join(Issue, IssueRelation.issue).join(Team, Issue.team).where(Team.organizationId == org_id)

    if not includeArchived:
        stmt = stmt.where(IssueRelation.archivedAt.is_(None))

    return _issue_relation_connection(session, stmt, first)


@IssueObject.field("inverseRelations")
def resolve_issue_inverse_relations_field(
    issue,
    info,
    after: str | None = None,
    before: str | None = None,
    first: int | None = None,
    includeArchived: bool | None = False,
    last: int | None = None,
    orderBy: str | None = None,
):
    unsupported_args = {"after": after, "before": before, "last": last, "orderBy": orderBy}
    if any(value is not None for value in unsupported_args.values()):
        raise GraphQLError("Pagination parameters are not supported")

    session = info.context.state.db_session

    stmt = select(IssueRelation).where(IssueRelation.relatedIssueId == issue.id)

    org_id = getattr(info.context.state, "org_id", None)
    if org_id is not None:
        stmt = stmt.join(Issue, IssueRelation.relatedIssue).join(Team, Issue.team).where(Team.organizationId == org_id)

    if not includeArchived:
        stmt = stmt.where(IssueRelation.archivedAt.is_(None))

    return _issue_relation_connection(session, stmt, first)


@Query.field("organization")
def resolve_organization(_parent, info):
    session = info.context.state.db_session

    user_id = getattr(info.context.state, "user_id", None)
    if user_id is None:
        raise GraphQLError("Not authenticated")

    user = session.get(User, user_id)
    if user is None or user.organization is None:
        raise GraphQLError("Organization not found")

    return user.organization


@Query.field("users")
def resolve_users(
    _parent,
    info,
    after: str | None = None,
    before: str | None = None,
    filter: dict | None = None,
    first: int | None = None,
    includeArchived: bool | None = False,
    includeDisabled: bool | None = False,
    last: int | None = None,
    orderBy: str | None = None,
    sort: list | None = None,
):
    unsupported_args = {
        "after": after,
        "before": before,
        "filter": filter,
        "last": last,
        "orderBy": orderBy,
        "sort": sort,
    }
    if any(value is not None for value in unsupported_args.values()):
        raise GraphQLError("Pagination or filtering arguments are not supported")

    session = info.context.state.db_session

    org_id = getattr(info.context.state, "org_id", None)
    if org_id is None:
        raise GraphQLError("Organization context is missing")

    if first is not None and first <= 0:
        raise GraphQLError("first must be greater than 0")

    limit = first if first is not None else 50
    fetch_limit = limit + 1

    stmt = select(User).where(User.organizationId == org_id)

    if not includeArchived:
        stmt = stmt.where(User.archivedAt.is_(None))

    if not includeDisabled:
        stmt = stmt.where(User.active.is_(True))

    stmt = stmt.order_by(User.createdAt, User.id).limit(fetch_limit)

    users = session.execute(stmt).scalars().all()

    has_next_page = len(users) > limit
    if has_next_page:
        users = users[:limit]

    edges = [{"cursor": user.id, "node": user} for user in users]
    start_cursor = edges[0]["cursor"] if edges else None
    end_cursor = edges[-1]["cursor"] if edges else None

    return {
        "edges": edges,
        "nodes": users,
        "pageInfo": {
            "startCursor": start_cursor,
            "endCursor": end_cursor,
            "hasNextPage": has_next_page,
            "hasPreviousPage": False,
        },
    }


@Query.field("projectStatusProjectCount")
def resolve_projectStatusProjectCount(_parent, info, id: str):
    if not id:
        raise GraphQLError("Status id is required")

    session = info.context.state.db_session

    org_id = getattr(info.context.state, "org_id", None)
    if org_id is None:
        raise GraphQLError("Organization context is missing")

    stmt = (
        select(func.count())
        .select_from(Project)
        .where(
            Project.organizationId == org_id,
            Project.statusId == id,
        )
    )

    count = session.execute(stmt).scalar_one()

    return {
        "archivedTeamCount": 0.0,
        "count": float(count),
        "privateCount": 0.0,
    }


@Query.field("projectStatuses")
def resolve_projectStatuses(
    _parent,
    info,
    after: str | None = None,
    before: str | None = None,
    first: int | None = None,
    includeArchived: bool | None = False,
    last: int | None = None,
    orderBy: str | None = None,
):
    unsupported_args = {
        "after": after,
        "before": before,
        "last": last,
        "orderBy": orderBy,
    }
    if any(value is not None for value in unsupported_args.values()):
        raise GraphQLError("Pagination arguments are not supported")

    session = info.context.state.db_session

    org_id = getattr(info.context.state, "org_id", None)
    if org_id is None:
        raise GraphQLError("Organization context is missing")

    if first is not None and first <= 0:
        raise GraphQLError("first must be greater than 0")

    limit = first if first is not None else 50

    stmt = select(Project.statusId, Project.statusType).where(
        Project.organizationId == org_id
    )

    if not includeArchived:
        stmt = stmt.where(Project.archivedAt.is_(None))

    rows = session.execute(stmt).all()

    status_map: dict[str, dict[str, str | None]] = {}
    for status_id, status_type in rows:
        if not status_id:
            continue
        status_map.setdefault(
            status_id,
            {
                "id": status_id,
                "type": status_type,
            },
        )

    statuses = sorted(status_map.values(), key=lambda item: item["id"])

    has_next_page = len(statuses) > limit
    if has_next_page:
        statuses = statuses[:limit]

    edges = [{"cursor": status["id"], "node": status} for status in statuses]
    start_cursor = edges[0]["cursor"] if edges else None
    end_cursor = edges[-1]["cursor"] if edges else None

    return {
        "edges": edges,
        "nodes": statuses,
        "pageInfo": {
            "startCursor": start_cursor,
            "endCursor": end_cursor,
            "hasNextPage": has_next_page,
            "hasPreviousPage": False,
        },
    }


@Query.field("projects")
def resolve_projects(
    _parent,
    info,
    after: str | None = None,
    before: str | None = None,
    first: int | None = None,
    includeArchived: bool | None = False,
    last: int | None = None,
    orderBy: str | None = None,
):
    unsupported_args = {
        "after": after,
        "before": before,
        "last": last,
        "orderBy": orderBy,
    }
    if any(value is not None for value in unsupported_args.values()):
        raise GraphQLError("Pagination arguments are not supported")

    session = info.context.state.db_session

    org_id = getattr(info.context.state, "org_id", None)
    if org_id is None:
        raise GraphQLError("Organization context is missing")

    if first is not None and first <= 0:
        raise GraphQLError("first must be greater than 0")

    limit = first if first is not None else 50
    fetch_limit = limit + 1

    stmt = select(Project).where(Project.organizationId == org_id)

    if not includeArchived:
        stmt = stmt.where(Project.archivedAt.is_(None))

    stmt = stmt.order_by(Project.createdAt, Project.id).limit(fetch_limit)

    projects = session.execute(stmt).scalars().all()

    has_next_page = len(projects) > limit
    if has_next_page:
        projects = projects[:limit]

    nodes = [ProjectDTO(project) for project in projects]
    edges = [
        {
            "cursor": project.id,
            "node": dto,
        }
        for project, dto in zip(projects, nodes)
    ]

    start_cursor = edges[0]["cursor"] if edges else None
    end_cursor = edges[-1]["cursor"] if edges else None

    return {
        "edges": edges,
        "nodes": nodes,
        "pageInfo": {
            "startCursor": start_cursor,
            "endCursor": end_cursor,
            "hasNextPage": has_next_page,
            "hasPreviousPage": False,
        },
    }


@ProjectStatusObject.field("id")
def resolve_project_status_id(status, _info):
    return status["id"]


@ProjectStatusObject.field("type")
def resolve_project_status_type(status, _info):
    status_type = status.get("type")
    if status_type is None:
        raise GraphQLError("Project status type is not available")
    return status_type


def _unsupported_project_status_field(field_name: str):
    def _resolver(_parent, _info):
        raise GraphQLError(f"Project status field '{field_name}' is not available")

    return _resolver


for _field in (
    "archivedAt",
    "color",
    "createdAt",
    "description",
    "indefinite",
    "name",
    "position",
    "updatedAt",
):
    ProjectStatusObject.set_field(_field, _unsupported_project_status_field(_field))


@Query.field("attachments")
def resolve_attachments(
    _parent,
    info,
    after: str | None = None,
    before: str | None = None,
    filter: dict | None = None,
    first: int | None = None,
    includeArchived: bool | None = False,
    last: int | None = None,
    orderBy: str | None = None,
):
    unsupported_args = {
        "after": after,
        "before": before,
        "filter": filter,
        "last": last,
        "orderBy": orderBy,
    }
    if any(value is not None for value in unsupported_args.values()):
        raise GraphQLError("Pagination or filtering arguments are not supported")

    session = info.context.state.db_session

    org_id = getattr(info.context.state, "org_id", None)
    if org_id is None:
        raise GraphQLError("Organization context is missing")

    if first is not None and first <= 0:
        raise GraphQLError("first must be greater than 0")

    limit = first if first is not None else 50
    fetch_limit = limit + 1

    stmt = (
        select(Attachment)
        .join(Issue, Attachment.issue)
        .join(Team, Issue.team)
        .where(Team.organizationId == org_id)
    )

    if not includeArchived:
        stmt = stmt.where(Attachment.archivedAt.is_(None))

    stmt = stmt.order_by(Attachment.createdAt, Attachment.id).limit(fetch_limit)

    attachments = session.execute(stmt).scalars().all()

    has_next_page = len(attachments) > limit
    if has_next_page:
        attachments = attachments[:limit]

    nodes = [AttachmentDTO(attachment) for attachment in attachments]
    edges = [
        {
            "cursor": attachment.id,
            "node": dto,
        }
        for attachment, dto in zip(attachments, nodes)
    ]

    start_cursor = edges[0]["cursor"] if edges else None
    end_cursor = edges[-1]["cursor"] if edges else None

    return {
        "edges": edges,
        "nodes": nodes,
        "pageInfo": {
            "startCursor": start_cursor,
            "endCursor": end_cursor,
            "hasNextPage": has_next_page,
            "hasPreviousPage": False,
        },
    }


@AttachmentObject.field("id")
def resolve_attachment_id(attachment, _info):
    return attachment.id


def _unsupported_attachment_field(field_name: str):
    def _resolver(_parent, _info):
        raise GraphQLError(f"Attachment field '{field_name}' is not available")

    return _resolver


for _field in ("externalUserCreator",):
    AttachmentObject.set_field(_field, _unsupported_attachment_field(_field))





# Still need to add teamMemberships

# Not included:
#   - apiKeys
#   - applicationWithAuthorization
#   - availableUsers
#   - customViewHasSubscribers
#   - customViews
#   - externalUser
#   - externalUsers
#   - notificationSubscriptions
def resolve 







        
        
    
