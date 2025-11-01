from ariadne import QueryType, MutationType
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, select
from src.services.linear.database.schema import (
    Issue,
    Attachment,
    User,
    Team,
    Organization,
    OrganizationInvite,
    OrganizationDomain,
    ProjectStatus,
    Project,
    ProjectLabel,
    ProjectMilestone,
    ProjectMilestoneStatus,
    Notification,
    Initiative,
    Comment,
    Document,
    Cycle,
    TeamMembership,
    IssueRelation,
    InitiativeRelation,
    InitiativeToProject,
    ExternalUser,
    IssueLabel,
    IssueImport,
    UserFlag,
    UserSettings,
    ProjectRelation,
    WorkflowState,
    Template,
)
from typing import Optional
import base64
import json
import uuid
from datetime import datetime, timezone, timedelta

from ariadne import ObjectType

query = QueryType()
mutation = MutationType()
issue_type = ObjectType("Issue")

# Export query and mutation objects for use in schema binding
__all__ = ["query", "mutation", "issue_type"]


@issue_type.field("labels")
def resolve_issue_labels(
    issue,
    info,
    after=None,
    before=None,
    filter=None,
    first=50,
    includeArchived=False,
    last=None,
    orderBy="createdAt",
):
    """
    Resolve the labels field to return an IssueLabelConnection.

    Args:
        issue: The parent Issue object
        info: GraphQL resolve info
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        filter: IssueLabelFilter to filter results
        first: Number of items for forward pagination (default: 50)
        includeArchived: Include archived labels (default: False)
        last: Number of items for backward pagination
        orderBy: Order by field - "createdAt" or "updatedAt" (default: "createdAt")

    Returns:
        IssueLabelConnection with nodes field
    """
    # Get labels from the relationship
    labels = (
        issue.labels if hasattr(issue, "labels") and issue.labels is not None else []
    )

    # Filter archived labels unless includeArchived is True
    if not includeArchived:
        labels = [label for label in labels if not label.archivedAt]

    # Apply custom filter if provided
    if filter:
        # TODO: Implement IssueLabelFilter logic (name, team, etc.)
        pass

    # Sort by orderBy field
    if orderBy == "updatedAt":
        labels = sorted(labels, key=lambda l: l.updatedAt or l.createdAt)
    else:  # Default to createdAt
        labels = sorted(labels, key=lambda l: l.createdAt)

    # Apply pagination (simplified - full cursor-based pagination would be more complex)
    if first and first < len(labels):
        labels = labels[:first]
    elif last and last < len(labels):
        labels = labels[-last:]

    # Return in IssueLabelConnection format
    return {"nodes": labels}


# Helper functions for cursor-based pagination
def encode_cursor(item, order_field="createdAt"):
    """Encode a cursor for pagination"""
    field_value = getattr(item, order_field)

    # Handle None values - this shouldn't happen for createdAt/updatedAt but be defensive
    if field_value is None:
        raise Exception(
            f"Cannot create cursor: {order_field} is None for item {item.id}"
        )

    # Encode datetime fields using isoformat, others as string
    cursor_data = {
        "field": field_value.isoformat()
        if hasattr(field_value, "isoformat")
        else str(field_value),
        "id": item.id,
    }
    return base64.b64encode(json.dumps(cursor_data).encode()).decode()


def decode_cursor(cursor):
    """Decode a cursor from pagination"""
    try:
        cursor_data = json.loads(base64.b64decode(cursor.encode()).decode())
        return cursor_data
    except Exception:
        raise Exception(f"Invalid cursor: {cursor}")


def validate_pagination_params(after, before, first, last):
    """
    Validate pagination parameters according to Relay Cursor Connections Specification.

    Raises:
        Exception: If invalid pagination parameters are provided
    """
    if first is not None and first <= 0:
        raise Exception("Argument 'first' must be a positive integer")
    if last is not None and last <= 0:
        raise Exception("Argument 'last' must be a positive integer")

    if first is not None and last is not None:
        raise Exception("Cannot use both 'first' and 'last' together")

    if after and before:
        raise Exception("Cannot use both 'after' and 'before' cursors together")

    if after and last:
        raise Exception(
            "Cannot use 'after' cursor with 'last' (incompatible pagination directions)"
        )
    if before and first:
        raise Exception(
            "Cannot use 'before' cursor with 'first' (incompatible pagination directions)"
        )


def apply_pagination(items, after, before, first, last, order_field="createdAt"):
    """
    Apply pagination logic and build connection response.

    This function handles the complex logic of cursor-based pagination according
    to the Relay Cursor Connections Specification.

    Args:
        items: List of fetched items (should be limit + 1)
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        first: Number of items requested (forward pagination)
        last: Number of items requested (backward pagination)
        order_field: Field used for ordering

    Returns:
        dict: Connection object with edges, nodes, and pageInfo
    """
    # Determine the limit that was used
    limit = first if first else (last if last else 50)

    # Check if there are more pages
    has_more = len(items) > limit
    if has_more:
        items = items[:limit]

    if last or before:
        items = list(reversed(items))

    if last and before:
        has_next_page = True
        has_previous_page = has_more
    elif last:
        has_next_page = False
        has_previous_page = has_more
    elif before:
        has_next_page = True
        has_previous_page = has_more
    elif after:
        has_next_page = has_more
        has_previous_page = True
    elif first:
        has_next_page = has_more
        has_previous_page = False
    else:
        has_next_page = has_more
        has_previous_page = False

    # Build edges
    edges = [
        {"node": item, "cursor": encode_cursor(item, order_field)} for item in items
    ]

    # Build pageInfo
    page_info = {
        "hasNextPage": has_next_page,
        "hasPreviousPage": has_previous_page,
        "startCursor": edges[0]["cursor"] if edges else None,
        "endCursor": edges[-1]["cursor"] if edges else None,
    }

    # Return connection
    return {"edges": edges, "nodes": items, "pageInfo": page_info}


# Resolver functions will be added here as queries are implemented
@query.field("issue")
def resolve_issue(obj, info, id: str):
    """
    Query one specific issue by its id.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        id: The issue id to look up

    Returns:
        Issue: The issue with the specified id
    """
    session: Session = info.context["session"]

    # Query for the issue by id
    issue = session.query(Issue).filter(Issue.id == id).first()

    if not issue:
        raise Exception(f"Issue with id '{id}' not found")

    return issue


@query.field("issueRelation")
def resolve_issueRelation(obj, info, id: str):
    """
    One specific issue relation.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        id: The issue relation id to look up

    Returns:
        IssueRelation: The issue relation with the specified id
    """
    session: Session = info.context["session"]

    # Query for the issue relation by id
    issue_relation = session.query(IssueRelation).filter(IssueRelation.id == id).first()

    if not issue_relation:
        raise Exception(f"IssueRelation with id '{id}' not found")

    return issue_relation


@query.field("issueRelations")
def resolve_issueRelations(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
):
    """
    All issue relationships.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        first: Number of items for forward pagination
        includeArchived: Include archived issue relations (default: False)
        last: Number of items for backward pagination
        orderBy: Order by field (createdAt or updatedAt)

    Returns:
        dict: IssueRelationConnection with edges, nodes, and pageInfo
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine order field
    order_field = orderBy if orderBy else "createdAt"
    if order_field not in ["createdAt", "updatedAt"]:
        raise Exception(
            f"Invalid orderBy field: {order_field}. Must be 'createdAt' or 'updatedAt'"
        )

    # Build base query
    base_query = session.query(IssueRelation)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(IssueRelation.archivedAt.is_(None))

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(IssueRelation, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, IssueRelation.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(IssueRelation, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, IssueRelation.id < cursor_id),
            )
        )

    # Apply ordering
    order_column = getattr(IssueRelation, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), IssueRelation.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), IssueRelation.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


@query.field("attachmentSources")
def resolve_attachmentSources(obj, info, teamId: Optional[str] = None):
    """
    [Internal] Get a list of all unique attachment sources in the workspace.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        teamId: (optional) if provided will only return attachment sources for the given team

    Returns:
        dict: AttachmentSourcesPayload with 'sources' field containing unique source types
    """
    session: Session = info.context["session"]

    # Build base query for attachments
    base_query = session.query(Attachment.sourceType).distinct()

    # If teamId is provided, filter by team through the issue relationship
    if teamId:
        base_query = base_query.join(Issue, Attachment.issueId == Issue.id).filter(
            Issue.teamId == teamId
        )

    # Execute query and get all unique source types
    source_types = base_query.all()

    # Build the sources object - a dictionary of source types
    # The sourceType values are the unique identifiers for attachment sources
    sources = {}
    for (source_type,) in source_types:
        if source_type:  # Skip null source types
            sources[source_type] = True

    # Return the payload
    return {"sources": sources}


@query.field("attachment")
def resolve_attachment(obj, info, id: str):
    """
    One specific issue attachment.
    [Deprecated] 'url' can no longer be used as the 'id' parameter. Use 'attachmentsForUrl' instead

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        id: The attachment id to look up

    Returns:
        Attachment: The attachment with the specified id
    """
    session: Session = info.context["session"]

    # Query for the attachment by id
    attachment = session.query(Attachment).filter(Attachment.id == id).first()

    if not attachment:
        raise Exception(f"Attachment with id '{id}' not found")

    return attachment


@query.field("attachmentIssue")
def resolve_attachmentIssue(obj, info, id: str):
    """
    Query an issue by its associated attachment, and its id.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        id: The attachment id or URL to look up

    Returns:
        Issue: The issue associated with the attachment
    """
    session: Session = info.context["session"]

    # Query for the attachment by id or url (deprecated behavior)
    attachment = (
        session.query(Attachment)
        .filter(or_(Attachment.id == id, Attachment.url == id))
        .first()
    )

    if not attachment:
        raise Exception(f"Attachment with id or url '{id}' not found")

    # Return the associated issue
    # The ORM relationship will handle loading the issue
    return attachment.issue


@query.field("attachments")
def resolve_attachments(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filter: Optional[dict] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
):
    """
    All issue attachments.

    To get attachments for a given URL, use `attachmentsForURL` query.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        filter: AttachmentFilter to apply
        first: Number of items for forward pagination
        includeArchived: Include archived attachments (default: False)
        last: Number of items for backward pagination
        orderBy: Order by field (createdAt or updatedAt)

    Returns:
        dict: AttachmentConnection with edges, nodes, and pageInfo
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine order field
    order_field = orderBy if orderBy else "createdAt"
    if order_field not in ["createdAt", "updatedAt"]:
        raise Exception(
            f"Invalid orderBy field: {order_field}. Must be 'createdAt' or 'updatedAt'"
        )

    # Build base query
    base_query = session.query(Attachment)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(Attachment.archivedAt.is_(None))

    # Apply filters if provided
    if filter:
        base_query = apply_attachment_filter(base_query, filter)

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(Attachment, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, Attachment.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(Attachment, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, Attachment.id < cursor_id),
            )
        )

    # Apply ordering
    order_column = getattr(Attachment, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), Attachment.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), Attachment.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


@query.field("attachmentsForURL")
def resolve_attachmentsForURL(
    obj,
    info,
    url: str,
    after: Optional[str] = None,
    before: Optional[str] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
):
    """
    Returns issue attachments for a given URL.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        url: The attachment URL to search for (required)
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        first: Number of items for forward pagination
        includeArchived: Include archived attachments (default: False)
        last: Number of items for backward pagination
        orderBy: Order by field (createdAt or updatedAt)

    Returns:
        dict: AttachmentConnection with edges, nodes, and pageInfo
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine order field
    order_field = orderBy if orderBy else "createdAt"
    if order_field not in ["createdAt", "updatedAt"]:
        raise Exception(
            f"Invalid orderBy field: {order_field}. Must be 'createdAt' or 'updatedAt'"
        )

    # Build base query with URL filter
    base_query = session.query(Attachment).filter(Attachment.url == url)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(Attachment.archivedAt.is_(None))

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(Attachment, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, Attachment.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(Attachment, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, Attachment.id < cursor_id),
            )
        )

    # Apply ordering
    order_column = getattr(Attachment, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), Attachment.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), Attachment.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


@query.field("issueFigmaFileKeySearch")
def resolve_issueFigmaFileKeySearch(
    obj,
    info,
    fileKey: str,
    after: Optional[str] = None,
    before: Optional[str] = None,
    first: Optional[int] = None,
    last: Optional[int] = None,
    includeArchived: bool = False,
    orderBy: Optional[str] = None,
):
    """
    Find issues that are related to a given Figma file key.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        fileKey: The Figma file key to search for
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        first: Number of items to return (forward pagination)
        last: Number of items to return (backward pagination)
        includeArchived: Whether to include archived issues
        orderBy: Field to order by (createdAt or updatedAt)

    Returns:
        IssueConnection: Paginated list of issues with Figma attachments
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query: find issues that have attachments with Figma URLs containing the fileKey
    # Figma URLs typically look like: https://www.figma.com/file/{fileKey}/...
    base_query = (
        session.query(Issue)
        .join(Attachment, Issue.id == Attachment.issueId)
        .filter(Attachment.url.like(f"%figma.com/file/{fileKey}%"))
    )

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(Issue.archivedAt.is_(None))

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(Issue, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, Issue.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(Issue, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, Issue.id < cursor_id),
            )
        )

    # Apply ordering
    order_column = getattr(Issue, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), Issue.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), Issue.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


@query.field("searchIssues")
def resolve_searchIssues(
    obj,
    info,
    term: str,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filter: Optional[dict] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    includeComments: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
    snippetSize: Optional[float] = None,
    teamId: Optional[str] = None,
):
    """
    Search issues.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        term: Search string to look for
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        filter: IssueFilter to apply to results
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived issues (default: false)
        includeComments: Whether to search associated comments (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)
        snippetSize: [Deprecated] Size of search snippet to return (default: 100)
        teamId: UUID of a team to use as a boost

    Returns:
        IssueSearchPayload: Search results with edges, nodes, pageInfo, totalCount, and archivePayload
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query for issues
    base_query = session.query(Issue)

    # Apply search term filter (search in title and description)
    if term:
        search_pattern = f"%{term}%"
        search_conditions = [
            Issue.title.like(search_pattern),
            Issue.description.like(search_pattern),
        ]

        # If includeComments is true, search in comments too
        if includeComments:
            # Subquery to find issue IDs that have matching comments
            comment_subquery = (
                session.query(Comment.issueId)
                .filter(Comment.body.like(search_pattern))
                .distinct()
            )

            # Add condition to include issues with matching comments
            search_conditions.append(Issue.id.in_(comment_subquery))

        base_query = base_query.filter(or_(*search_conditions))

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(Issue.archivedAt.is_(None))

    # Apply team filter if provided (as a boost/filter)
    if teamId:
        base_query = base_query.filter(Issue.teamId == teamId)

    # Validate and apply additional filters if provided
    if filter:
        validate_issue_filter(filter)
        base_query = apply_issue_filter(base_query, filter)

    # Get total count before pagination
    total_count = base_query.count()

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(Issue, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, Issue.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(Issue, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, Issue.id < cursor_id),
            )
        )

    # Apply ordering
    order_column = getattr(Issue, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), Issue.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), Issue.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    pagination_result = apply_pagination(items, after, before, first, last, order_field)

    # IssueSearchResult nodes are just the Issue objects themselves
    # The GraphQL layer will handle serialization
    # No need to manually spread __dict__ attributes

    # Build archivePayload (empty for now as we don't have archived entities)
    archive_payload = {"success": True, "lastSyncId": 0.0}

    # Return IssueSearchPayload
    return {
        **pagination_result,
        "totalCount": float(total_count),
        "archivePayload": archive_payload,
    }


@query.field("issueSearch")
def resolve_issueSearch(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filter: Optional[dict] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
    query: Optional[str] = None,
):
    """
    [DEPRECATED] Search issues. This endpoint is deprecated and will be removed in the future.
    Use `searchIssues` instead.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        filter: IssueFilter to apply to results
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived issues (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)
        query: [Deprecated] Search string to look for

    Returns:
        IssueConnection: Paginated list of issues matching the search criteria
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query
    base_query = session.query(Issue)

    # Apply search query if provided (deprecated parameter)
    # Search in title and description fields
    if query:
        search_pattern = f"%{query}%"
        base_query = base_query.filter(
            or_(
                Issue.title.like(search_pattern), Issue.description.like(search_pattern)
            )
        )

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(Issue.archivedAt.is_(None))

    # Validate and apply additional filters if provided
    if filter:
        validate_issue_filter(filter)
        base_query = apply_issue_filter(base_query, filter)

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(Issue, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, Issue.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(Issue, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, Issue.id < cursor_id),
            )
        )

    # Apply ordering
    order_column = getattr(Issue, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), Issue.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), Issue.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


def validate_issue_filter(filter_dict, path="filter"):
    """
    Validate that the filter dictionary only contains supported operations.

    This function checks for unsupported filter features and raises clear errors.

    Args:
        filter_dict: Dictionary containing filter criteria
        path: Current path in the filter tree (for error messages)

    Raises:
        Exception: If unsupported filter operations are detected
    """
    if not filter_dict:
        return

    # Check for OR filters (not implemented)
    if "or" in filter_dict:
        raise Exception(
            f"OR filters are not currently supported. "
            f"Found at: {path}.or. "
            f"Please use only AND filters or separate queries."
        )

    # Check for AND filters recursively
    if "and" in filter_dict:
        for i, sub_filter in enumerate(filter_dict["and"]):
            validate_issue_filter(sub_filter, f"{path}.and[{i}]")

    # Check for nested relation filters (not fully implemented)
    unsupported_relation_keys = {
        "assignee": [
            "email",
            "name",
            "displayName",
            "active",
            "admin",
            "createdAt",
            "updatedAt",
        ],
        "team": ["name", "key", "description", "createdAt", "updatedAt"],
        "state": ["name", "color", "type", "description", "createdAt", "updatedAt"],
        "project": ["name", "description", "slugId", "state", "createdAt", "updatedAt"],
        "cycle": ["name", "number", "startsAt", "endsAt", "createdAt", "updatedAt"],
    }

    for relation_name, unsupported_keys in unsupported_relation_keys.items():
        if relation_name in filter_dict:
            relation_filter = filter_dict[relation_name]

            # Validate that relation filter is a dictionary
            if not isinstance(relation_filter, dict):
                raise Exception(
                    f"Invalid filter value for relation '{relation_name}'. "
                    f"Expected a dictionary with 'null' or 'id' keys, got {type(relation_filter).__name__}."
                )

            # Check if any unsupported nested keys are present
            for key in relation_filter.keys():
                if key in unsupported_keys:
                    raise Exception(
                        f"Nested relation filters are not currently supported. "
                        f"Found at: {path}.{relation_name}.{key}. "
                        f"Only 'null' and 'id' filters are supported for relation fields."
                    )


def apply_issue_filter(query, filter_dict):
    """
    Apply IssueFilter criteria to a SQLAlchemy query.

    This is a helper function that processes the filter dictionary and applies
    the appropriate WHERE clauses to the query.

    Args:
        query: SQLAlchemy query object
        filter_dict: Dictionary containing filter criteria

    Returns:
        Modified query with filters applied
    """
    if not filter_dict:
        return query

    # Handle compound filters
    if "and" in filter_dict:
        for sub_filter in filter_dict["and"]:
            query = apply_issue_filter(query, sub_filter)

    # Note: OR filters are validated and rejected in validate_issue_filter()
    # They are not implemented due to complexity of building condition expressions

    # String comparators
    if "title" in filter_dict:
        query = apply_string_comparator(query, Issue.title, filter_dict["title"])

    if "description" in filter_dict:
        query = apply_string_comparator(
            query, Issue.description, filter_dict["description"]
        )

    if "identifier" in filter_dict:
        query = apply_string_comparator(
            query, Issue.identifier, filter_dict["identifier"]
        )

    # Number comparators
    if "number" in filter_dict:
        query = apply_number_comparator(query, Issue.number, filter_dict["number"])

    if "priority" in filter_dict:
        query = apply_number_comparator(query, Issue.priority, filter_dict["priority"])

    if "estimate" in filter_dict:
        query = apply_number_comparator(query, Issue.estimate, filter_dict["estimate"])

    # Date comparators
    if "createdAt" in filter_dict:
        query = apply_date_comparator(query, Issue.createdAt, filter_dict["createdAt"])

    if "updatedAt" in filter_dict:
        query = apply_date_comparator(query, Issue.updatedAt, filter_dict["updatedAt"])

    if "completedAt" in filter_dict:
        query = apply_date_comparator(
            query, Issue.completedAt, filter_dict["completedAt"]
        )

    if "startedAt" in filter_dict:
        query = apply_date_comparator(query, Issue.startedAt, filter_dict["startedAt"])

    if "canceledAt" in filter_dict:
        query = apply_date_comparator(
            query, Issue.canceledAt, filter_dict["canceledAt"]
        )

    if "archivedAt" in filter_dict:
        query = apply_date_comparator(
            query, Issue.archivedAt, filter_dict["archivedAt"]
        )

    if "dueDate" in filter_dict:
        query = apply_date_comparator(query, Issue.dueDate, filter_dict["dueDate"])

    # ID comparator
    if "id" in filter_dict:
        query = apply_id_comparator(query, Issue.id, filter_dict["id"])

    # Relation filters (simplified - full implementation would need joins)
    if "assignee" in filter_dict:
        assignee_filter = filter_dict["assignee"]
        if assignee_filter.get("null") is True:
            query = query.filter(Issue.assigneeId.is_(None))
        elif assignee_filter.get("null") is False:
            query = query.filter(Issue.assigneeId.isnot(None))
        # Additional user filter criteria would be applied with joins

    if "team" in filter_dict:
        team_filter = filter_dict["team"]
        if team_filter.get("null") is True:
            query = query.filter(Issue.teamId.is_(None))
        elif team_filter.get("null") is False:
            query = query.filter(Issue.teamId.isnot(None))
        if "id" in team_filter:
            query = apply_id_comparator(query, Issue.teamId, team_filter["id"])

    if "state" in filter_dict:
        state_filter = filter_dict["state"]
        if state_filter.get("null") is True:
            query = query.filter(Issue.stateId.is_(None))
        elif state_filter.get("null") is False:
            query = query.filter(Issue.stateId.isnot(None))
        if "id" in state_filter:
            query = apply_id_comparator(query, Issue.stateId, state_filter["id"])

    if "project" in filter_dict:
        project_filter = filter_dict["project"]
        if project_filter.get("null") is True:
            query = query.filter(Issue.projectId.is_(None))
        elif project_filter.get("null") is False:
            query = query.filter(Issue.projectId.isnot(None))
        if "id" in project_filter:
            query = apply_id_comparator(query, Issue.projectId, project_filter["id"])

    if "cycle" in filter_dict:
        cycle_filter = filter_dict["cycle"]
        if cycle_filter.get("null") is True:
            query = query.filter(Issue.cycleId.is_(None))
        elif cycle_filter.get("null") is False:
            query = query.filter(Issue.cycleId.isnot(None))
        if "id" in cycle_filter:
            query = apply_id_comparator(query, Issue.cycleId, cycle_filter["id"])

    return query


def apply_attachment_filter(query, filter_dict):
    """
    Apply AttachmentFilter criteria to a SQLAlchemy query.

    This is a helper function that processes the filter dictionary and applies
    the appropriate WHERE clauses to the query.

    Args:
        query: SQLAlchemy query object
        filter_dict: Dictionary containing filter criteria

    Returns:
        Modified query with filters applied
    """
    if not filter_dict:
        return query

    # Handle compound filters
    if "and" in filter_dict:
        for sub_filter in filter_dict["and"]:
            query = apply_attachment_filter(query, sub_filter)

    if "or" in filter_dict:
        # Build OR conditions
        conditions = []
        for sub_filter in filter_dict["or"]:
            # We need to apply each filter to a fresh query and extract the whereclause
            # For simplicity, we'll raise an exception for now
            raise Exception("OR filters are not currently supported for attachments")

    # String comparators
    if "title" in filter_dict:
        query = apply_string_comparator(query, Attachment.title, filter_dict["title"])

    if "subtitle" in filter_dict:
        query = apply_nullable_string_comparator(
            query, Attachment.subtitle, filter_dict["subtitle"]
        )

    if "url" in filter_dict:
        query = apply_string_comparator(query, Attachment.url, filter_dict["url"])

    if "sourceType" in filter_dict:
        # SourceType is a string comparator
        query = apply_string_comparator(
            query, Attachment.sourceType, filter_dict["sourceType"]
        )

    # Date comparators
    if "createdAt" in filter_dict:
        query = apply_date_comparator(
            query, Attachment.createdAt, filter_dict["createdAt"]
        )

    if "updatedAt" in filter_dict:
        query = apply_date_comparator(
            query, Attachment.updatedAt, filter_dict["updatedAt"]
        )

    # ID comparator
    if "id" in filter_dict:
        query = apply_id_comparator(query, Attachment.id, filter_dict["id"])

    # Relation filters
    if "creator" in filter_dict:
        creator_filter = filter_dict["creator"]
        if creator_filter.get("null") is True:
            query = query.filter(Attachment.creatorId.is_(None))
        elif creator_filter.get("null") is False:
            query = query.filter(Attachment.creatorId.isnot(None))
        if "id" in creator_filter:
            query = apply_id_comparator(
                query, Attachment.creatorId, creator_filter["id"]
            )

    return query


def apply_string_comparator(query, column, comparator):
    """Apply string comparison filters."""
    if not isinstance(comparator, dict):
        raise Exception(
            f"Invalid comparator for string field. Expected dictionary with comparison operators, got {type(comparator).__name__}."
        )

    if "eq" in comparator:
        query = query.filter(column == comparator["eq"])
    if "neq" in comparator:
        query = query.filter(column != comparator["neq"])
    if "contains" in comparator:
        query = query.filter(column.like(f"%{comparator['contains']}%"))
    if "notContains" in comparator:
        query = query.filter(~column.like(f"%{comparator['notContains']}%"))
    if "startsWith" in comparator:
        query = query.filter(column.like(f"{comparator['startsWith']}%"))
    if "endsWith" in comparator:
        query = query.filter(column.like(f"%{comparator['endsWith']}"))
    if "in" in comparator:
        query = query.filter(column.in_(comparator["in"]))
    if "notIn" in comparator:
        query = query.filter(~column.in_(comparator["notIn"]))
    if "containsIgnoreCase" in comparator:
        query = query.filter(column.ilike(f"%{comparator['containsIgnoreCase']}%"))
    if "notContainsIgnoreCase" in comparator:
        query = query.filter(~column.ilike(f"%{comparator['notContainsIgnoreCase']}%"))
    if "startsWithIgnoreCase" in comparator:
        query = query.filter(column.ilike(f"{comparator['startsWithIgnoreCase']}%"))
    if "endsWithIgnoreCase" in comparator:
        query = query.filter(column.ilike(f"%{comparator['endsWithIgnoreCase']}"))
    return query


def apply_number_comparator(query, column, comparator):
    """Apply number comparison filters."""
    if not isinstance(comparator, dict):
        raise Exception(
            f"Invalid comparator for number field. Expected dictionary with comparison operators, got {type(comparator).__name__}."
        )

    if "eq" in comparator:
        query = query.filter(column == comparator["eq"])
    if "neq" in comparator:
        query = query.filter(column != comparator["neq"])
    if "gt" in comparator:
        query = query.filter(column > comparator["gt"])
    if "gte" in comparator:
        query = query.filter(column >= comparator["gte"])
    if "lt" in comparator:
        query = query.filter(column < comparator["lt"])
    if "lte" in comparator:
        query = query.filter(column <= comparator["lte"])
    if "in" in comparator:
        query = query.filter(column.in_(comparator["in"]))
    if "notIn" in comparator:
        query = query.filter(~column.in_(comparator["notIn"]))
    return query


def apply_date_comparator(query, column, comparator):
    """Apply date comparison filters."""

    if not isinstance(comparator, dict):
        raise Exception(
            f"Invalid comparator for date field. Expected dictionary with comparison operators, got {type(comparator).__name__}."
        )

    if "eq" in comparator:
        date_val = (
            datetime.fromisoformat(comparator["eq"])
            if isinstance(comparator["eq"], str)
            else comparator["eq"]
        )
        query = query.filter(column == date_val)
    if "neq" in comparator:
        date_val = (
            datetime.fromisoformat(comparator["neq"])
            if isinstance(comparator["neq"], str)
            else comparator["neq"]
        )
        query = query.filter(column != date_val)
    if "gt" in comparator:
        date_val = (
            datetime.fromisoformat(comparator["gt"])
            if isinstance(comparator["gt"], str)
            else comparator["gt"]
        )
        query = query.filter(column > date_val)
    if "gte" in comparator:
        date_val = (
            datetime.fromisoformat(comparator["gte"])
            if isinstance(comparator["gte"], str)
            else comparator["gte"]
        )
        query = query.filter(column >= date_val)
    if "lt" in comparator:
        date_val = (
            datetime.fromisoformat(comparator["lt"])
            if isinstance(comparator["lt"], str)
            else comparator["lt"]
        )
        query = query.filter(column < date_val)
    if "lte" in comparator:
        date_val = (
            datetime.fromisoformat(comparator["lte"])
            if isinstance(comparator["lte"], str)
            else comparator["lte"]
        )
        query = query.filter(column <= date_val)
    return query


def apply_id_comparator(query, column, comparator):
    """Apply ID comparison filters."""
    if not isinstance(comparator, dict):
        raise Exception(
            f"Invalid comparator for ID field. Expected dictionary with comparison operators, got {type(comparator).__name__}."
        )

    if "eq" in comparator:
        query = query.filter(column == comparator["eq"])
    if "neq" in comparator:
        query = query.filter(column != comparator["neq"])
    if "in" in comparator:
        query = query.filter(column.in_(comparator["in"]))
    if "notIn" in comparator:
        query = query.filter(~column.in_(comparator["notIn"]))
    return query


@query.field("user")
def resolve_user(obj, info, id: str):
    """
    Query one specific user by their id.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        id: The user id to look up

    Returns:
        User: The user with the specified id

    Raises:
        Exception: If the user is not found
    """
    session: Session = info.context["session"]

    # Query for the user by id
    user = session.query(User).filter(User.id == id).first()

    if not user:
        raise Exception(f"User with id '{id}' not found")

    return user


@query.field("issueVcsBranchSearch")
def resolve_issueVcsBranchSearch(obj, info, branchName: str):
    """
    Find issue based on the VCS branch name.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        branchName: The VCS branch name to search for

    Returns:
        Issue: The issue with the matching branch name, or None if not found
    """
    session: Session = info.context["session"]

    # Query for the issue by branch name
    issue = session.query(Issue).filter(Issue.branchName == branchName).first()

    # Return the issue (can be None if not found)
    return issue


@query.field("issues")
def resolve_issues(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filter: Optional[dict] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    includeSubTeams: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
    sort: Optional[list] = None,
):
    """
    Query all issues with filtering, sorting, and pagination.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        filter: IssueFilter to apply to results
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived issues (default: false)
        includeSubTeams: Include issues from sub-teams when filtering by team (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)
        sort: [INTERNAL] Sort options for issues

    Returns:
        IssueConnection: Paginated list of issues
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query
    base_query = session.query(Issue)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(Issue.archivedAt.is_(None))

    # Validate and apply additional filters if provided
    if filter:
        validate_issue_filter(filter)
        base_query = apply_issue_filter(base_query, filter)

    # Validate that sort parameter is not used with cursors
    # The [INTERNAL] sort parameter uses complex multi-field sorting that is
    # incompatible with cursor-based pagination
    if sort and (after or before):
        raise Exception(
            "Cannot use cursor pagination (after/before) with the [INTERNAL] sort parameter. Use orderBy instead."
        )

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(Issue, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, Issue.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(Issue, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, Issue.id < cursor_id),
            )
        )

    # Apply sorting if provided (INTERNAL parameter)
    # Note: The sort parameter is marked as [INTERNAL] in the GraphQL schema
    # and provides more granular control over sorting than orderBy
    if sort:
        base_query = apply_issue_sort(base_query, sort)
    else:
        # Apply default ordering based on orderBy parameter
        order_column = getattr(Issue, order_field)
        if last or before:
            # For backward pagination, reverse the order
            base_query = base_query.order_by(order_column.desc(), Issue.id.desc())
        else:
            base_query = base_query.order_by(order_column.asc(), Issue.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


def apply_issue_sort(query, sort_list):
    """
    Apply IssueSortInput criteria to a SQLAlchemy query.

    This handles the [INTERNAL] sort parameter which provides more granular
    control over sorting than the standard orderBy parameter.

    Args:
        query: SQLAlchemy query object
        sort_list: List of sort input dictionaries

    Returns:
        Modified query with sorting applied
    """
    from sqlalchemy import asc, desc

    if not sort_list:
        return query

    # Build a list of order_by clauses
    order_clauses = []

    for sort_input in sort_list:
        # Each sort_input is a dictionary with one or more sort fields
        # Each field value is a dictionary with direction (e.g., {"direction": "ASC"})

        if "assignee" in sort_input:
            # Sort by assignee name - would require join with User table
            # For now, we'll sort by assigneeId as a simplified implementation
            direction = sort_input["assignee"].get("direction", "ASC")
            order_clauses.append(
                asc(Issue.assigneeId) if direction == "ASC" else desc(Issue.assigneeId)
            )

        if "completedAt" in sort_input:
            direction = sort_input["completedAt"].get("direction", "ASC")
            order_clauses.append(
                asc(Issue.completedAt)
                if direction == "ASC"
                else desc(Issue.completedAt)
            )

        if "createdAt" in sort_input:
            direction = sort_input["createdAt"].get("direction", "ASC")
            order_clauses.append(
                asc(Issue.createdAt) if direction == "ASC" else desc(Issue.createdAt)
            )

        if "customerCount" in sort_input:
            # This would require aggregating customer needs
            # For now, skip or use a placeholder
            pass

        if "dueDate" in sort_input:
            direction = sort_input["dueDate"].get("direction", "ASC")
            order_clauses.append(
                asc(Issue.dueDate) if direction == "ASC" else desc(Issue.dueDate)
            )

        if "estimate" in sort_input:
            direction = sort_input["estimate"].get("direction", "ASC")
            order_clauses.append(
                asc(Issue.estimate) if direction == "ASC" else desc(Issue.estimate)
            )

        if "priority" in sort_input:
            direction = sort_input["priority"].get("direction", "ASC")
            order_clauses.append(
                asc(Issue.priority) if direction == "ASC" else desc(Issue.priority)
            )

        if "title" in sort_input:
            direction = sort_input["title"].get("direction", "ASC")
            order_clauses.append(
                asc(Issue.title) if direction == "ASC" else desc(Issue.title)
            )

        if "updatedAt" in sort_input:
            direction = sort_input["updatedAt"].get("direction", "ASC")
            order_clauses.append(
                asc(Issue.updatedAt) if direction == "ASC" else desc(Issue.updatedAt)
            )

        if "manual" in sort_input:
            # Manual sorting uses sortOrder field
            direction = sort_input["manual"].get("direction", "ASC")
            order_clauses.append(
                asc(Issue.sortOrder) if direction == "ASC" else desc(Issue.sortOrder)
            )

    # Apply all order clauses to the query
    if order_clauses:
        query = query.order_by(*order_clauses)

    return query


def validate_user_filter(filter_dict, path="filter"):
    """
    Validate that the filter dictionary only contains supported operations.

    Args:
        filter_dict: Dictionary containing filter criteria
        path: Current path in the filter tree (for error messages)

    Raises:
        Exception: If unsupported filter operations are detected
    """
    if not filter_dict:
        return

    # Check for OR filters (not implemented)
    if "or" in filter_dict:
        raise Exception(
            f"OR filters are not currently supported. "
            f"Found at: {path}.or. "
            f"Please use only AND filters or separate queries."
        )

    # Check for AND filters recursively
    if "and" in filter_dict:
        for i, sub_filter in enumerate(filter_dict["and"]):
            validate_user_filter(sub_filter, f"{path}.and[{i}]")

    # Check for nested relation filters (not fully implemented)
    if "assignedIssues" in filter_dict:
        # This would require complex join logic
        raise Exception(
            f"Nested collection filters are not currently supported. "
            f"Found at: {path}.assignedIssues. "
            f"Please filter users separately from issues."
        )

    # Check for isMe filter (not implemented - requires auth context)
    if "isMe" in filter_dict:
        raise Exception(
            f"The 'isMe' filter is not currently supported. "
            f"Use the 'viewer' query to get the current user, or filter by specific user IDs."
        )


def apply_user_filter(query, filter_dict):
    """
    Apply UserFilter criteria to a SQLAlchemy query.

    Args:
        query: SQLAlchemy query object
        filter_dict: Dictionary containing filter criteria

    Returns:
        Modified query with filters applied
    """
    if not filter_dict:
        return query

    # Handle compound filters
    if "and" in filter_dict:
        for sub_filter in filter_dict["and"]:
            query = apply_user_filter(query, sub_filter)

    # Boolean comparators
    if "active" in filter_dict:
        query = apply_boolean_comparator(query, User.active, filter_dict["active"])

    if "admin" in filter_dict:
        query = apply_boolean_comparator(query, User.admin, filter_dict["admin"])

    if "app" in filter_dict:
        query = apply_boolean_comparator(query, User.app, filter_dict["app"])

    if "invited" in filter_dict or "isInvited" in filter_dict:
        # Both 'invited' and 'isInvited' refer to the same thing
        # In Linear's API, a user is "invited" if they haven't accepted yet
        # For simplicity, we'll check if the user has a valid inviteHash
        invited_filter = filter_dict.get("invited", filter_dict.get("isInvited"))
        if isinstance(invited_filter, dict):
            if invited_filter.get("eq") is True:
                query = query.filter(User.inviteHash.isnot(None))
            elif invited_filter.get("eq") is False:
                query = query.filter(User.inviteHash.is_(None))
            elif invited_filter.get("neq") is True:
                query = query.filter(User.inviteHash.is_(None))
            elif invited_filter.get("neq") is False:
                query = query.filter(User.inviteHash.isnot(None))

    # Note: 'isMe' filter is validated and rejected in validate_user_filter()

    # String comparators
    if "displayName" in filter_dict:
        query = apply_string_comparator(
            query, User.displayName, filter_dict["displayName"]
        )

    if "email" in filter_dict:
        query = apply_string_comparator(query, User.email, filter_dict["email"])

    if "name" in filter_dict:
        query = apply_string_comparator(query, User.name, filter_dict["name"])

    # Date comparators
    if "createdAt" in filter_dict:
        query = apply_date_comparator(query, User.createdAt, filter_dict["createdAt"])

    if "updatedAt" in filter_dict:
        query = apply_date_comparator(query, User.updatedAt, filter_dict["updatedAt"])

    # ID comparator
    if "id" in filter_dict:
        query = apply_id_comparator(query, User.id, filter_dict["id"])

    return query


def apply_boolean_comparator(query, column, comparator):
    """Apply boolean comparison filters."""
    if not isinstance(comparator, dict):
        raise Exception(
            f"Invalid comparator for boolean field. Expected dictionary with comparison operators, got {type(comparator).__name__}."
        )

    if "eq" in comparator:
        query = query.filter(column == comparator["eq"])
    if "neq" in comparator:
        query = query.filter(column != comparator["neq"])

    return query


def apply_user_sort(query, sort_list):
    """
    Apply UserSortInput criteria to a SQLAlchemy query.

    Args:
        query: SQLAlchemy query object
        sort_list: List of sort input dictionaries

    Returns:
        Modified query with sorting applied
    """
    from sqlalchemy import asc, desc

    if not sort_list:
        return query

    order_clauses = []

    for sort_input in sort_list:
        if "displayName" in sort_input:
            direction = sort_input["displayName"].get("direction", "ASC")
            order_clauses.append(
                asc(User.displayName) if direction == "ASC" else desc(User.displayName)
            )

        if "name" in sort_input:
            direction = sort_input["name"].get("direction", "ASC")
            order_clauses.append(
                asc(User.name) if direction == "ASC" else desc(User.name)
            )

    if order_clauses:
        query = query.order_by(*order_clauses)

    return query


@query.field("users")
def resolve_users(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filter: Optional[dict] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    includeDisabled: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
    sort: Optional[list] = None,
):
    """
    Query all users for the organization.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        filter: UserFilter to apply to results
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived users (default: false)
        includeDisabled: Whether to include disabled/suspended users (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)
        sort: [INTERNAL] Sort options for users

    Returns:
        UserConnection: Paginated list of users
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query
    base_query = session.query(User)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(User.archivedAt.is_(None))

    # Apply disabled filter
    if not includeDisabled:
        base_query = base_query.filter(User.active == True)

    # Validate and apply additional filters if provided
    if filter:
        validate_user_filter(filter)
        base_query = apply_user_filter(base_query, filter)

    # Validate that sort parameter is not used with cursors
    if sort and (after or before):
        raise Exception(
            "Cannot use cursor pagination (after/before) with the [INTERNAL] sort parameter. Use orderBy instead."
        )

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(User, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, User.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(User, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, User.id < cursor_id),
            )
        )

    # Apply sorting if provided (INTERNAL parameter)
    if sort:
        base_query = apply_user_sort(base_query, sort)
    else:
        # Apply default ordering based on orderBy parameter
        order_column = getattr(User, order_field)
        if last or before:
            # For backward pagination, reverse the order
            base_query = base_query.order_by(order_column.desc(), User.id.desc())
        else:
            base_query = base_query.order_by(order_column.asc(), User.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


@query.field("viewer")
def resolve_viewer(obj, info):
    """
    Query the currently authenticated user.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context

    Returns:
        User: The currently authenticated user

    Raises:
        Exception: If no authenticated user is found in context or user doesn't exist
    """
    session: Session = info.context["session"]

    # Get the current user ID from the authentication context
    # In a real implementation, this would come from a JWT token, session, etc.
    # The context should be set up by the authentication middleware
    current_user_id = info.context.get("user_id")

    if not current_user_id:
        raise Exception(
            "No authenticated user found. Please provide authentication credentials."
        )

    # Query for the authenticated user
    viewer = session.query(User).filter(User.id == current_user_id).first()

    if not viewer:
        raise Exception(
            f"Authenticated user with id '{current_user_id}' not found in database"
        )

    return viewer


def validate_team_filter(filter_dict, path="filter"):
    """
    Validate that the filter dictionary only contains supported operations.

    Args:
        filter_dict: Dictionary containing filter criteria
        path: Current path in the filter tree (for error messages)

    Raises:
        Exception: If unsupported filter operations are detected
    """
    if not filter_dict:
        return

    # Check for OR filters (not implemented)
    if "or" in filter_dict:
        raise Exception(
            f"OR filters are not currently supported. "
            f"Found at: {path}.or. "
            f"Please use only AND filters or separate queries."
        )

    # Check for AND filters recursively
    if "and" in filter_dict:
        for i, sub_filter in enumerate(filter_dict["and"]):
            validate_team_filter(sub_filter, f"{path}.and[{i}]")

    # Check for nested relation filters (not fully implemented)
    if "parent" in filter_dict:
        # Nested parent filters would require complex join logic
        parent_filter = filter_dict["parent"]

        # Validate that parent filter is a dictionary
        if parent_filter and not isinstance(parent_filter, dict):
            raise Exception(
                f"Invalid filter value for relation 'parent'. "
                f"Expected a dictionary with 'null' key, got {type(parent_filter).__name__}."
            )

        if parent_filter and isinstance(parent_filter, dict):
            # Only 'null' filter is supported for parent
            unsupported_keys = [k for k in parent_filter.keys() if k not in ["null"]]
            if unsupported_keys:
                raise Exception(
                    f"Nested parent filters are not currently supported. "
                    f"Found at: {path}.parent.{unsupported_keys[0]}. "
                    f"Only 'null' filter is supported for parent field."
                )

    # Check for nested issue collection filters (not implemented)
    if "issues" in filter_dict:
        raise Exception(
            f"Nested collection filters are not currently supported. "
            f"Found at: {path}.issues. "
            f"Please filter teams and issues separately."
        )


def apply_team_filter(query, filter_dict):
    """
    Apply TeamFilter criteria to a SQLAlchemy query.

    Args:
        query: SQLAlchemy query object
        filter_dict: Dictionary containing filter criteria

    Returns:
        Modified query with filters applied
    """
    if not filter_dict:
        return query

    # Handle compound filters
    if "and" in filter_dict:
        for sub_filter in filter_dict["and"]:
            query = apply_team_filter(query, sub_filter)

    # String comparators
    if "name" in filter_dict:
        query = apply_string_comparator(query, Team.name, filter_dict["name"])

    if "key" in filter_dict:
        query = apply_string_comparator(query, Team.key, filter_dict["key"])

    if "description" in filter_dict:
        query = apply_nullable_string_comparator(
            query, Team.description, filter_dict["description"]
        )

    # Date comparators
    if "createdAt" in filter_dict:
        query = apply_date_comparator(query, Team.createdAt, filter_dict["createdAt"])

    if "updatedAt" in filter_dict:
        query = apply_date_comparator(query, Team.updatedAt, filter_dict["updatedAt"])

    # ID comparator
    if "id" in filter_dict:
        query = apply_id_comparator(query, Team.id, filter_dict["id"])

    # Boolean comparator
    if "private" in filter_dict:
        query = apply_boolean_comparator(query, Team.private, filter_dict["private"])

    # Parent filter (simplified - only null check supported)
    if "parent" in filter_dict:
        parent_filter = filter_dict["parent"]
        if parent_filter and isinstance(parent_filter, dict):
            if parent_filter.get("null") is True:
                query = query.filter(Team.parentId.is_(None))
            elif parent_filter.get("null") is False:
                query = query.filter(Team.parentId.isnot(None))

    return query


def apply_nullable_string_comparator(query, column, comparator):
    """Apply nullable string comparison filters."""
    if not isinstance(comparator, dict):
        raise Exception(
            f"Invalid comparator for nullable string field. Expected dictionary with comparison operators, got {type(comparator).__name__}."
        )

    # Handle null checks first
    if "null" in comparator:
        if comparator["null"] is True:
            query = query.filter(column.is_(None))
        elif comparator["null"] is False:
            query = query.filter(column.isnot(None))

    # Apply string comparisons (only when not null)
    if "eq" in comparator:
        query = query.filter(column == comparator["eq"])
    if "neq" in comparator:
        query = query.filter(column != comparator["neq"])
    if "contains" in comparator:
        query = query.filter(column.like(f"%{comparator['contains']}%"))
    if "notContains" in comparator:
        query = query.filter(~column.like(f"%{comparator['notContains']}%"))
    if "startsWith" in comparator:
        query = query.filter(column.like(f"{comparator['startsWith']}%"))
    if "endsWith" in comparator:
        query = query.filter(column.like(f"%{comparator['endsWith']}"))
    if "in" in comparator:
        query = query.filter(column.in_(comparator["in"]))
    if "notIn" in comparator:
        query = query.filter(~column.in_(comparator["notIn"]))
    if "containsIgnoreCase" in comparator:
        query = query.filter(column.ilike(f"%{comparator['containsIgnoreCase']}%"))
    if "notContainsIgnoreCase" in comparator:
        query = query.filter(~column.ilike(f"%{comparator['notContainsIgnoreCase']}%"))
    if "startsWithIgnoreCase" in comparator:
        query = query.filter(column.ilike(f"{comparator['startsWithIgnoreCase']}%"))
    if "endsWithIgnoreCase" in comparator:
        query = query.filter(column.ilike(f"%{comparator['endsWithIgnoreCase']}"))

    return query


@query.field("administrableTeams")
def resolve_administrableTeams(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filter: Optional[dict] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
):
    """
    Query all teams the user can administrate.

    Administrable teams are teams whose settings the user can change,
    but to whose issues the user doesn't necessarily have access to.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        filter: TeamFilter to apply to results
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived teams (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)

    Returns:
        TeamConnection: Paginated list of teams
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query
    # TODO: In a real implementation, this would filter by user's admin permissions
    # For now, we return all teams (the database would have proper ACL enforcement)
    base_query = session.query(Team)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(Team.archivedAt.is_(None))

    # Validate and apply additional filters if provided
    if filter:
        validate_team_filter(filter)
        base_query = apply_team_filter(base_query, filter)

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(Team, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, Team.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(Team, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, Team.id < cursor_id),
            )
        )

    # Apply ordering
    order_column = getattr(Team, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), Team.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), Team.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


@query.field("archivedTeams")
def resolve_archivedTeams(obj, info):
    """
    [Internal] All archived teams of the organization.

    This query returns only teams that have been archived (archivedAt is not null).

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context

    Returns:
        list[Team]: List of all archived teams
    """
    session: Session = info.context["session"]

    # Query for all teams that have been archived
    # A team is archived if archivedAt is not null
    archived_teams = session.query(Team).filter(Team.archivedAt.isnot(None)).all()

    return archived_teams


@query.field("team")
def resolve_team(obj, info, id: str):
    """
    Query one specific team by its id.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        id: The team id to look up

    Returns:
        Team: The team with the specified id

    Raises:
        Exception: If the team is not found
    """
    session: Session = info.context["session"]

    # Query for the team by id
    team = session.query(Team).filter(Team.id == id).first()

    if not team:
        raise Exception(f"Team with id '{id}' not found")

    return team


@query.field("teams")
def resolve_teams(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filter: Optional[dict] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
):
    """
    Query all teams whose issues can be accessed by the user.

    This might be different from `administrableTeams`, which also includes teams
    whose settings can be changed by the user.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        filter: TeamFilter to apply to results
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived teams (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)

    Returns:
        TeamConnection: Paginated list of teams
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query
    # All teams whose issues can be accessed by the user
    # In a real implementation, this would filter by user's issue access permissions
    # For now, we return all teams (the database would have proper ACL enforcement)
    base_query = session.query(Team)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(Team.archivedAt.is_(None))

    # Validate and apply additional filters if provided
    if filter:
        validate_team_filter(filter)
        base_query = apply_team_filter(base_query, filter)

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(Team, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, Team.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(Team, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, Team.id < cursor_id),
            )
        )

    # Apply ordering
    order_column = getattr(Team, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), Team.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), Team.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


@query.field("organization")
def resolve_organization(obj, info):
    """
    Query the user's organization.

    This query returns the organization that the currently authenticated user belongs to.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context

    Returns:
        Organization: The user's organization

    Raises:
        Exception: If no authenticated user is found or the user's organization doesn't exist
    """
    session: Session = info.context["session"]

    # Get the current user ID from the authentication context
    # The context should be set up by the authentication middleware
    current_user_id = info.context.get("user_id")

    if not current_user_id:
        raise Exception(
            "No authenticated user found. Please provide authentication credentials."
        )

    # First, get the current user to find their organization ID
    user = session.query(User).filter(User.id == current_user_id).first()

    if not user:
        raise Exception(
            f"Authenticated user with id '{current_user_id}' not found in database"
        )

    # Query for the user's organization
    organization = (
        session.query(Organization)
        .filter(Organization.id == user.organizationId)
        .first()
    )

    if not organization:
        raise Exception(f"Organization with id '{user.organizationId}' not found")

    return organization


@query.field("organizationExists")
def resolve_organizationExists(obj, info, urlKey: str):
    """
    Check if an organization exists by its URL key.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        urlKey: The organization's URL key to check

    Returns:
        dict: OrganizationExistsPayload with 'exists' and 'success' fields
    """
    session: Session = info.context["session"]

    # Query for an organization with the given urlKey
    # The organization could be active or archived, so we check both
    organization = (
        session.query(Organization).filter(Organization.urlKey == urlKey).first()
    )

    # Return the payload
    return {"exists": organization is not None, "success": True}


@query.field("organizationInvite")
def resolve_organizationInvite(obj, info, id: str):
    """
    Query one specific organization invite by its id.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        id: The organization invite id to look up

    Returns:
        OrganizationInvite: The organization invite with the specified id

    Raises:
        Exception: If the organization invite is not found
    """
    session: Session = info.context["session"]

    # Query for the organization invite by id
    organization_invite = (
        session.query(OrganizationInvite).filter(OrganizationInvite.id == id).first()
    )

    if not organization_invite:
        raise Exception(f"OrganizationInvite with id '{id}' not found")

    return organization_invite


@query.field("organizationInvites")
def resolve_organizationInvites(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
):
    """
    Query all invites for the organization.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived invites (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)

    Returns:
        OrganizationInviteConnection: Paginated list of organization invites
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query
    base_query = session.query(OrganizationInvite)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(OrganizationInvite.archivedAt.is_(None))

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(OrganizationInvite, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(
                    order_column == cursor_field_value,
                    OrganizationInvite.id > cursor_id,
                ),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(OrganizationInvite, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(
                    order_column == cursor_field_value,
                    OrganizationInvite.id < cursor_id,
                ),
            )
        )

    # Apply ordering
    order_column = getattr(OrganizationInvite, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(
            order_column.desc(), OrganizationInvite.id.desc()
        )
    else:
        base_query = base_query.order_by(
            order_column.asc(), OrganizationInvite.id.asc()
        )

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


# ============================================================================
# OrganizationInvite Mutations
# ============================================================================


@mutation.field("organizationInviteCreate")
def resolve_organizationInviteCreate(obj, info, **kwargs):
    """
    Creates a new organization invite.

    Args:
        obj: The parent object (unused for mutations)
        info: GraphQL resolve info containing context
        **kwargs: Mutation arguments including 'input'

    Returns:
        The created OrganizationInvite entity
    """
    session: Session = info.context["session"]

    try:
        # Extract input data
        input_data = kwargs.get("input", {})

        # Validate required fields
        if not input_data.get("email"):
            raise Exception("Field 'email' is required")

        # Generate ID if not provided
        invite_id = input_data.get("id", str(uuid.uuid4()))

        # Get current timestamp
        now = datetime.now(timezone.utc)

        # Build organization invite data
        invite_data = {
            "id": invite_id,
            "email": input_data["email"],
            "role": input_data.get(
                "role", "user"
            ),  # Default to 'user' as specified in input
            "metadata_": input_data.get("metadata"),  # Optional metadata
            "external": False,  # Will be determined by system logic
            "createdAt": now,
            "updatedAt": now,
        }

        # Handle organizationId - this should typically come from context
        # For now, we'll allow it to be set via input if needed
        # In a real implementation, this might come from the authenticated user's org
        if "organizationId" in input_data:
            invite_data["organizationId"] = input_data["organizationId"]

        # Handle inviterId - this should typically come from the authenticated user
        # For now, we'll allow it to be set via input if needed
        if "inviterId" in input_data:
            invite_data["inviterId"] = input_data["inviterId"]

        # Create the organization invite entity
        organization_invite = OrganizationInvite(**invite_data)

        # Handle team associations if teamIds are provided
        team_ids = input_data.get("teamIds", [])
        if team_ids:
            # Query for the teams
            teams = session.query(Team).filter(Team.id.in_(team_ids)).all()

            # Validate that all teams exist
            found_team_ids = {team.id for team in teams}
            missing_team_ids = set(team_ids) - found_team_ids
            if missing_team_ids:
                raise Exception(f"Teams not found: {', '.join(missing_team_ids)}")

            # Associate teams with the invite
            organization_invite.teams = teams

        session.add(organization_invite)

        return organization_invite

    except Exception as e:
        raise Exception(f"Failed to create organization invite: {str(e)}")


@mutation.field("organizationInviteUpdate")
def resolve_organizationInviteUpdate(obj, info, **kwargs):
    """
    Updates an organization invite.

    Args:
        obj: The parent object (unused for mutations)
        info: GraphQL resolve info containing context
        **kwargs: Mutation arguments including 'id' and 'input'

    Returns:
        The updated OrganizationInvite entity
    """
    session: Session = info.context["session"]

    try:
        # Extract arguments
        invite_id = kwargs.get("id")
        input_data = kwargs.get("input", {})

        # Validate required fields
        if not invite_id:
            raise Exception("Field 'id' is required")

        # Fetch the organization invite to update
        org_invite = session.query(OrganizationInvite).filter_by(id=invite_id).first()

        if not org_invite:
            raise Exception(f"OrganizationInvite with id {invite_id} not found")

        # Handle team associations update
        team_ids = input_data.get("teamIds", [])
        if team_ids is not None:  # Allow empty list to clear teams
            # Query for the teams
            teams = session.query(Team).filter(Team.id.in_(team_ids)).all()

            # Validate that all teams exist
            found_team_ids = {team.id for team in teams}
            missing_team_ids = set(team_ids) - found_team_ids
            if missing_team_ids:
                raise Exception(f"Teams not found: {', '.join(missing_team_ids)}")

            # Update team associations
            org_invite.teams = teams

        # Update the timestamp
        org_invite.updatedAt = datetime.now(timezone.utc)

        return org_invite

    except Exception as e:
        raise Exception(f"Failed to update organization invite: {str(e)}")


@mutation.field("organizationInviteDelete")
def resolve_organizationInviteDelete(obj, info, **kwargs):
    """
    Deletes an organization invite.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (organization invite ID to delete)

    Returns:
        Dict containing DeletePayload with entityId, success, and lastSyncId
    """
    session: Session = info.context["session"]
    invite_id = kwargs.get("id")

    try:
        # Fetch the organization invite to delete
        org_invite = session.query(OrganizationInvite).filter_by(id=invite_id).first()

        if not org_invite:
            raise Exception(f"OrganizationInvite with id {invite_id} not found")

        # Soft delete by setting archivedAt timestamp
        org_invite.archivedAt = datetime.now(timezone.utc)
        org_invite.updatedAt = datetime.now(timezone.utc)

        # Return DeletePayload structure
        return {
            "entityId": invite_id,
            "success": True,
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
        }

    except Exception as e:
        raise Exception(f"Failed to delete organization invite: {str(e)}")


@query.field("projectStatus")
def resolve_projectStatus(obj, info, id: str):
    """
    Query one specific project status by its id.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        id: The project status id to look up

    Returns:
        ProjectStatus: The project status with the specified id

    Raises:
        Exception: If the project status is not found
    """
    session: Session = info.context["session"]

    # Query for the project status by id
    project_status = session.query(ProjectStatus).filter(ProjectStatus.id == id).first()

    if not project_status:
        raise Exception(f"ProjectStatus with id '{id}' not found")

    return project_status


@query.field("projectStatuses")
def resolve_projectStatuses(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
):
    """
    Query all project statuses.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived project statuses (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)

    Returns:
        ProjectStatusConnection: Paginated list of project statuses
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query
    base_query = session.query(ProjectStatus)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(ProjectStatus.archivedAt.is_(None))

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(ProjectStatus, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, ProjectStatus.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(ProjectStatus, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, ProjectStatus.id < cursor_id),
            )
        )

    # Apply ordering
    order_column = getattr(ProjectStatus, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), ProjectStatus.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), ProjectStatus.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


@query.field("projectStatusProjectCount")
def resolve_projectStatusProjectCount(obj, info, id: str):
    """
    [INTERNAL] Count of projects using this project status across the organization.

    This query counts:
    - Total number of projects using the specified project status
    - Projects in archived teams (not visible to users)
    - Projects in private teams (not visible to users who aren't members)

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        id: The identifier of the project status to find the project count for

    Returns:
        dict: ProjectStatusCountPayload with count, archivedTeamCount, and privateCount fields
    """
    session: Session = info.context["session"]

    # Verify the project status exists
    project_status = session.query(ProjectStatus).filter(ProjectStatus.id == id).first()
    if not project_status:
        raise Exception(f"ProjectStatus with id '{id}' not found")

    # Count total projects using this project status
    # This includes all projects regardless of team status
    total_count = session.query(Project).filter(Project.statusId == id).count()

    # Count projects in archived teams
    # Join with teams and filter for archived teams
    archived_team_count = (
        session.query(Project)
        .join(Team, Project.teams)
        .filter(Project.statusId == id, Team.archivedAt.isnot(None))
        .distinct()
        .count()
    )

    # Count projects in private teams
    # Join with teams and filter for private teams
    private_count = (
        session.query(Project)
        .join(Team, Project.teams)
        .filter(Project.statusId == id, Team.private == True)
        .distinct()
        .count()
    )

    # Return the payload
    return {
        "count": float(total_count),
        "archivedTeamCount": float(archived_team_count),
        "privateCount": float(private_count),
    }


def validate_project_label_filter(filter_dict, path="filter"):
    """
    Validate that the filter dictionary only contains supported operations.

    Args:
        filter_dict: Dictionary containing filter criteria
        path: Current path in the filter tree (for error messages)

    Raises:
        Exception: If unsupported filter operations are detected
    """
    if not filter_dict:
        return

    # Check for OR filters (not implemented)
    if "or" in filter_dict:
        raise Exception(
            f"OR filters are not currently supported. "
            f"Found at: {path}.or. "
            f"Please use only AND filters or separate queries."
        )

    # Check for AND filters recursively
    if "and" in filter_dict:
        for i, sub_filter in enumerate(filter_dict["and"]):
            validate_project_label_filter(sub_filter, f"{path}.and[{i}]")

    # Check for nested relation filters
    if "creator" in filter_dict:
        creator_filter = filter_dict["creator"]
        if creator_filter and not isinstance(creator_filter, dict):
            raise Exception(
                f"Invalid filter value for relation 'creator'. "
                f"Expected a dictionary with 'null' key, got {type(creator_filter).__name__}."
            )

    if "parent" in filter_dict:
        parent_filter = filter_dict["parent"]
        if parent_filter and not isinstance(parent_filter, dict):
            raise Exception(
                f"Invalid filter value for relation 'parent'. "
                f"Expected a dictionary, got {type(parent_filter).__name__}."
            )
        # Recursively validate nested parent filters
        if parent_filter and isinstance(parent_filter, dict):
            validate_project_label_filter(parent_filter, f"{path}.parent")


def apply_project_label_filter(query, filter_dict):
    """
    Apply ProjectLabelFilter criteria to a SQLAlchemy query.

    Args:
        query: SQLAlchemy query object
        filter_dict: Dictionary containing filter criteria

    Returns:
        Modified query with filters applied
    """
    if not filter_dict:
        return query

    # Handle compound filters
    if "and" in filter_dict:
        for sub_filter in filter_dict["and"]:
            query = apply_project_label_filter(query, sub_filter)

    # String comparators
    if "name" in filter_dict:
        query = apply_string_comparator(query, ProjectLabel.name, filter_dict["name"])

    # Date comparators
    if "createdAt" in filter_dict:
        query = apply_date_comparator(
            query, ProjectLabel.createdAt, filter_dict["createdAt"]
        )

    if "updatedAt" in filter_dict:
        query = apply_date_comparator(
            query, ProjectLabel.updatedAt, filter_dict["updatedAt"]
        )

    # ID comparator
    if "id" in filter_dict:
        query = apply_id_comparator(query, ProjectLabel.id, filter_dict["id"])

    # Boolean comparator
    if "isGroup" in filter_dict:
        query = apply_boolean_comparator(
            query, ProjectLabel.isGroup, filter_dict["isGroup"]
        )

    # Creator filter (nullable user filter)
    if "creator" in filter_dict:
        creator_filter = filter_dict["creator"]
        if creator_filter and isinstance(creator_filter, dict):
            if creator_filter.get("null") is True:
                query = query.filter(ProjectLabel.creatorId.is_(None))
            elif creator_filter.get("null") is False:
                query = query.filter(ProjectLabel.creatorId.isnot(None))

    # Parent filter (recursive project label filter)
    if "parent" in filter_dict:
        parent_filter = filter_dict["parent"]
        if parent_filter and isinstance(parent_filter, dict):
            # For nested parent filters, we need to recursively apply filters
            # This is a simplified implementation that only supports basic operations
            if "id" in parent_filter:
                query = apply_id_comparator(
                    query, ProjectLabel.parentId, parent_filter["id"]
                )
            if "name" in parent_filter:
                # This requires a join with the parent label
                query = query.join(ProjectLabel.parent).filter(
                    apply_string_comparator(
                        query, ProjectLabel.name, parent_filter["name"]
                    )
                )

    return query


@query.field("projectLabel")
def resolve_projectLabel(obj, info, id: str):
    """
    Query one specific project label by its id.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        id: The project label id to look up

    Returns:
        ProjectLabel: The project label with the specified id

    Raises:
        Exception: If the project label is not found
    """
    session: Session = info.context["session"]

    # Query for the project label by id
    project_label = session.query(ProjectLabel).filter(ProjectLabel.id == id).first()

    if not project_label:
        raise Exception(f"ProjectLabel with id '{id}' not found")

    return project_label


@query.field("projectLabels")
def resolve_projectLabels(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filter: Optional[dict] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
):
    """
    Query all project labels.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        filter: ProjectLabelFilter to apply to results
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived project labels (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)

    Returns:
        ProjectLabelConnection: Paginated list of project labels
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query
    base_query = session.query(ProjectLabel)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(ProjectLabel.archivedAt.is_(None))

    # Validate and apply additional filters if provided
    if filter:
        validate_project_label_filter(filter)
        base_query = apply_project_label_filter(base_query, filter)

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(ProjectLabel, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, ProjectLabel.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(ProjectLabel, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, ProjectLabel.id < cursor_id),
            )
        )

    # Apply ordering
    order_column = getattr(ProjectLabel, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), ProjectLabel.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), ProjectLabel.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


def validate_project_milestone_filter(filter_dict, path="filter"):
    """
    Validate that the filter dictionary only contains supported operations.

    Args:
        filter_dict: Dictionary containing filter criteria
        path: Current path in the filter tree (for error messages)

    Raises:
        Exception: If unsupported filter operations are detected
    """
    if not filter_dict:
        return

    # Check for OR filters (not implemented)
    if "or" in filter_dict:
        raise Exception(
            f"OR filters are not currently supported. "
            f"Found at: {path}.or. "
            f"Please use only AND filters or separate queries."
        )

    # Check for AND filters recursively
    if "and" in filter_dict:
        for i, sub_filter in enumerate(filter_dict["and"]):
            validate_project_milestone_filter(sub_filter, f"{path}.and[{i}]")


def apply_project_milestone_filter(query, filter_dict):
    """
    Apply ProjectMilestoneFilter criteria to a SQLAlchemy query.

    Args:
        query: SQLAlchemy query object
        filter_dict: Dictionary containing filter criteria

    Returns:
        Modified query with filters applied
    """
    if not filter_dict:
        return query

    # Handle compound filters
    if "and" in filter_dict:
        for sub_filter in filter_dict["and"]:
            query = apply_project_milestone_filter(query, sub_filter)

    # String comparators
    if "name" in filter_dict:
        query = apply_nullable_string_comparator(
            query, ProjectMilestone.name, filter_dict["name"]
        )

    # Date comparators
    if "createdAt" in filter_dict:
        query = apply_date_comparator(
            query, ProjectMilestone.createdAt, filter_dict["createdAt"]
        )

    if "updatedAt" in filter_dict:
        query = apply_date_comparator(
            query, ProjectMilestone.updatedAt, filter_dict["updatedAt"]
        )

    if "targetDate" in filter_dict:
        query = apply_nullable_date_comparator(
            query, ProjectMilestone.targetDate, filter_dict["targetDate"]
        )

    # ID comparator
    if "id" in filter_dict:
        query = apply_id_comparator(query, ProjectMilestone.id, filter_dict["id"])

    return query


def apply_nullable_date_comparator(query, column, comparator):
    """Apply nullable date comparison filters."""

    if not isinstance(comparator, dict):
        raise Exception(
            f"Invalid comparator for nullable date field. Expected dictionary with comparison operators, got {type(comparator).__name__}."
        )

    # Handle null checks first
    if "null" in comparator:
        if comparator["null"] is True:
            query = query.filter(column.is_(None))
        elif comparator["null"] is False:
            query = query.filter(column.isnot(None))

    # Apply date comparisons (only when not null)
    if "eq" in comparator:
        date_val = (
            datetime.fromisoformat(comparator["eq"])
            if isinstance(comparator["eq"], str)
            else comparator["eq"]
        )
        query = query.filter(column == date_val)
    if "neq" in comparator:
        date_val = (
            datetime.fromisoformat(comparator["neq"])
            if isinstance(comparator["neq"], str)
            else comparator["neq"]
        )
        query = query.filter(column != date_val)
    if "gt" in comparator:
        date_val = (
            datetime.fromisoformat(comparator["gt"])
            if isinstance(comparator["gt"], str)
            else comparator["gt"]
        )
        query = query.filter(column > date_val)
    if "gte" in comparator:
        date_val = (
            datetime.fromisoformat(comparator["gte"])
            if isinstance(comparator["gte"], str)
            else comparator["gte"]
        )
        query = query.filter(column >= date_val)
    if "lt" in comparator:
        date_val = (
            datetime.fromisoformat(comparator["lt"])
            if isinstance(comparator["lt"], str)
            else comparator["lt"]
        )
        query = query.filter(column < date_val)
    if "lte" in comparator:
        date_val = (
            datetime.fromisoformat(comparator["lte"])
            if isinstance(comparator["lte"], str)
            else comparator["lte"]
        )
        query = query.filter(column <= date_val)

    return query


@query.field("projectMilestone")
def resolve_projectMilestone(obj, info, id: str):
    """
    Query one specific project milestone.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        id: The project milestone id to look up

    Returns:
        ProjectMilestone: The project milestone with the specified id

    Raises:
        Exception: If the project milestone is not found
    """
    session: Session = info.context["session"]

    # Query for the project milestone by id
    project_milestone = (
        session.query(ProjectMilestone).filter(ProjectMilestone.id == id).first()
    )

    if not project_milestone:
        raise Exception(f"ProjectMilestone with id '{id}' not found")

    return project_milestone


@query.field("projectMilestones")
def resolve_projectMilestones(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filter: Optional[dict] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
):
    """
    Query all milestones for the project.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        filter: ProjectMilestoneFilter to apply to results
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived project milestones (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)

    Returns:
        ProjectMilestoneConnection: Paginated list of project milestones
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query
    base_query = session.query(ProjectMilestone)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(ProjectMilestone.archivedAt.is_(None))

    # Validate and apply additional filters if provided
    if filter:
        validate_project_milestone_filter(filter)
        base_query = apply_project_milestone_filter(base_query, filter)

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(ProjectMilestone, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(
                    order_column == cursor_field_value, ProjectMilestone.id > cursor_id
                ),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(ProjectMilestone, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(
                    order_column == cursor_field_value, ProjectMilestone.id < cursor_id
                ),
            )
        )

    # Apply ordering
    order_column = getattr(ProjectMilestone, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(
            order_column.desc(), ProjectMilestone.id.desc()
        )
    else:
        base_query = base_query.order_by(order_column.asc(), ProjectMilestone.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


@query.field("projectRelation")
def resolve_projectRelation(obj, info, id: str):
    """
    One specific project relation.

    Args:
        obj: The parent object (unused)
        info: GraphQL resolve info containing context
        id: The unique identifier of the project relation

    Returns:
        ProjectRelation: The project relation object

    Raises:
        Exception: If the project relation is not found
    """
    session: Session = info.context["session"]

    # Query the project relation by ID
    project_relation = (
        session.query(ProjectRelation).filter(ProjectRelation.id == id).first()
    )

    # Raise an error if not found
    if not project_relation:
        raise Exception(f"ProjectRelation with id '{id}' not found")

    return project_relation


@query.field("projectRelations")
def resolve_projectRelations(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
):
    """
    All project relationships.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        first: Number of items for forward pagination
        includeArchived: Include archived project relations (default: False)
        last: Number of items for backward pagination
        orderBy: Order by field (createdAt or updatedAt)

    Returns:
        dict: ProjectRelationConnection with edges, nodes, and pageInfo
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine order field
    order_field = orderBy if orderBy else "createdAt"
    if order_field not in ["createdAt", "updatedAt"]:
        raise Exception(
            f"Invalid orderBy field: {order_field}. Must be 'createdAt' or 'updatedAt'"
        )

    # Build base query
    base_query = session.query(ProjectRelation)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(ProjectRelation.archivedAt.is_(None))

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(ProjectRelation, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(
                    order_column == cursor_field_value, ProjectRelation.id > cursor_id
                ),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(ProjectRelation, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(
                    order_column == cursor_field_value, ProjectRelation.id < cursor_id
                ),
            )
        )

    # Apply ordering
    order_column = getattr(ProjectRelation, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), ProjectRelation.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), ProjectRelation.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


@query.field("searchProjects")
def resolve_searchProjects(
    obj,
    info,
    term: str,
    after: Optional[str] = None,
    before: Optional[str] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    includeComments: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
    snippetSize: Optional[float] = None,
    teamId: Optional[str] = None,
):
    """
    Search projects.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        term: Search string to look for
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived projects (default: false)
        includeComments: Whether to search associated comments (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)
        snippetSize: [Deprecated] Size of search snippet to return (default: 100)
        teamId: UUID of a team to use as a boost

    Returns:
        ProjectSearchPayload: Search results with edges, nodes, pageInfo, totalCount, and archivePayload
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query for projects
    base_query = session.query(Project)

    # Apply search term filter (search in name, description, slugId)
    if term:
        search_pattern = f"%{term}%"
        base_query = base_query.filter(
            or_(
                Project.name.like(search_pattern),
                Project.description.like(search_pattern),
                Project.slugId.like(search_pattern),
            )
        )

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(Project.archivedAt.is_(None))

    # Apply team filter if provided
    # Note: This requires a proper join with team_projects association table
    # For now, we'll skip this optimization as it requires understanding the schema better
    # if teamId:
    #     base_query = base_query.filter(Project.team_id == teamId)

    # Get total count before pagination
    total_count = base_query.count()

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(Project, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, Project.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(Project, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, Project.id < cursor_id),
            )
        )

    # Apply ordering
    order_column = getattr(Project, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), Project.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), Project.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Check if there are more pages
    has_more = len(items) > limit
    if has_more:
        items = items[:limit]

    # If using backward pagination, reverse the results
    if last or before:
        items = list(reversed(items))

    # Determine pagination info according to Relay spec
    if last and before:
        has_next_page = True
        has_previous_page = has_more
    elif last:
        has_next_page = False
        has_previous_page = has_more
    elif before:
        has_next_page = True
        has_previous_page = has_more
    elif after:
        has_next_page = has_more
        has_previous_page = True
    elif first:
        has_next_page = has_more
        has_previous_page = False
    else:
        has_next_page = has_more
        has_previous_page = False

    # Build edges - each edge contains a ProjectSearchResult node
    # ProjectSearchResult is essentially the Project with search metadata
    edges = [
        {
            "node": {
                # Include all project fields
                **{k: v for k, v in project.__dict__.items() if not k.startswith("_")},
                # Add search-specific metadata
                "metadata": {},  # Empty metadata for now
            },
            "cursor": encode_cursor(project, order_field),
        }
        for project in items
    ]

    # Build nodes - same as edge nodes
    nodes = [edge["node"] for edge in edges]

    # Build pageInfo
    page_info = {
        "hasNextPage": has_next_page,
        "hasPreviousPage": has_previous_page,
        "startCursor": edges[0]["cursor"] if edges else None,
        "endCursor": edges[-1]["cursor"] if edges else None,
    }

    # Build archivePayload (empty for now as we don't have archived entities)
    archive_payload = {"success": True, "lastSyncId": 0.0}

    # Return ProjectSearchPayload
    return {
        "edges": edges,
        "nodes": nodes,
        "pageInfo": page_info,
        "totalCount": float(total_count),
        "archivePayload": archive_payload,
    }


@query.field("notification")
def resolve_notification(obj, info, id: str):
    """
    Query one specific notification by its id.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        id: The notification id to look up

    Returns:
        Notification: The notification with the specified id

    Raises:
        Exception: If notification with the given id is not found
    """
    session: Session = info.context["session"]

    # Query for the notification by id
    notification = session.query(Notification).filter(Notification.id == id).first()

    if not notification:
        raise Exception(f"Notification with id '{id}' not found")

    return notification


@query.field("notifications")
def resolve_notifications(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filter: Optional[dict] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
):
    """
    Query all notifications with filtering, sorting, and pagination.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        filter: NotificationFilter to apply to results
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived notifications (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)

    Returns:
        NotificationConnection: Paginated list of notifications
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query
    base_query = session.query(Notification)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(Notification.archivedAt.is_(None))

    # Validate and apply additional filters if provided
    if filter:
        validate_notification_filter(filter)
        base_query = apply_notification_filter(base_query, filter)

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(Notification, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, Notification.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(Notification, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, Notification.id < cursor_id),
            )
        )

    # Apply default ordering based on orderBy parameter
    order_column = getattr(Notification, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), Notification.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), Notification.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


def validate_notification_filter(filter_dict, path="filter"):
    """
    Validate that the filter dictionary only contains supported operations.

    Args:
        filter_dict: Dictionary containing filter criteria
        path: Current path in the filter tree (for error messages)

    Raises:
        Exception: If unsupported filter operations are detected
    """
    if not filter_dict:
        return

    # Check for OR filters (supported recursively)
    if "or" in filter_dict:
        for i, sub_filter in enumerate(filter_dict["or"]):
            validate_notification_filter(sub_filter, f"{path}.or[{i}]")

    # Check for AND filters recursively
    if "and" in filter_dict:
        for i, sub_filter in enumerate(filter_dict["and"]):
            validate_notification_filter(sub_filter, f"{path}.and[{i}]")


def apply_notification_filter(query, filter_dict):
    """
    Apply NotificationFilter criteria to a SQLAlchemy query.

    Args:
        query: SQLAlchemy query object
        filter_dict: Dictionary containing filter criteria

    Returns:
        Modified query with filters applied
    """
    if not filter_dict:
        return query

    # Handle compound filters
    if "and" in filter_dict:
        for sub_filter in filter_dict["and"]:
            query = apply_notification_filter(query, sub_filter)

    if "or" in filter_dict:
        # Build a list of conditions for OR
        # Each sub_filter is a branch, and conditions within a branch are ANDed together
        or_conditions = []
        for sub_filter in filter_dict["or"]:
            # Collect conditions for this specific OR branch
            branch_conditions = []

            # Build conditions for each field using helper functions
            if "archivedAt" in sub_filter:
                cond = build_date_condition(
                    Notification.archivedAt, sub_filter["archivedAt"]
                )
                if cond is not None:
                    branch_conditions.append(cond)

            if "createdAt" in sub_filter:
                cond = build_date_condition(
                    Notification.createdAt, sub_filter["createdAt"]
                )
                if cond is not None:
                    branch_conditions.append(cond)

            if "id" in sub_filter:
                cond = build_id_condition(Notification.id, sub_filter["id"])
                if cond is not None:
                    branch_conditions.append(cond)

            if "type" in sub_filter:
                cond = build_string_condition(Notification.type, sub_filter["type"])
                if cond is not None:
                    branch_conditions.append(cond)

            if "updatedAt" in sub_filter:
                cond = build_date_condition(
                    Notification.updatedAt, sub_filter["updatedAt"]
                )
                if cond is not None:
                    branch_conditions.append(cond)

            # Nested compound filters within OR
            if "and" in sub_filter or "or" in sub_filter:
                raise Exception(
                    "Nested compound filters (AND/OR) within OR filters are not currently supported for notifications. "
                    "Please restructure your query to avoid nesting."
                )

            # Combine conditions within this branch with AND
            if branch_conditions:
                if len(branch_conditions) == 1:
                    or_conditions.append(branch_conditions[0])
                else:
                    or_conditions.append(and_(*branch_conditions))

        if or_conditions:
            query = query.filter(or_(*or_conditions))

    # Date comparators
    if "archivedAt" in filter_dict:
        query = apply_date_comparator(
            query, Notification.archivedAt, filter_dict["archivedAt"]
        )

    if "createdAt" in filter_dict:
        query = apply_date_comparator(
            query, Notification.createdAt, filter_dict["createdAt"]
        )

    if "updatedAt" in filter_dict:
        query = apply_date_comparator(
            query, Notification.updatedAt, filter_dict["updatedAt"]
        )

    # ID comparator
    if "id" in filter_dict:
        query = apply_id_comparator(query, Notification.id, filter_dict["id"])

    # String comparator
    if "type" in filter_dict:
        query = apply_string_comparator(query, Notification.type, filter_dict["type"])

    return query


def build_date_condition(column, comparator):
    """Build a date comparison condition for use in OR filters."""

    conditions = []
    if "eq" in comparator:
        date_val = (
            datetime.fromisoformat(comparator["eq"])
            if isinstance(comparator["eq"], str)
            else comparator["eq"]
        )
        conditions.append(column == date_val)
    if "neq" in comparator:
        date_val = (
            datetime.fromisoformat(comparator["neq"])
            if isinstance(comparator["neq"], str)
            else comparator["neq"]
        )
        conditions.append(column != date_val)
    if "gt" in comparator:
        date_val = (
            datetime.fromisoformat(comparator["gt"])
            if isinstance(comparator["gt"], str)
            else comparator["gt"]
        )
        conditions.append(column > date_val)
    if "gte" in comparator:
        date_val = (
            datetime.fromisoformat(comparator["gte"])
            if isinstance(comparator["gte"], str)
            else comparator["gte"]
        )
        conditions.append(column >= date_val)
    if "lt" in comparator:
        date_val = (
            datetime.fromisoformat(comparator["lt"])
            if isinstance(comparator["lt"], str)
            else comparator["lt"]
        )
        conditions.append(column < date_val)
    if "lte" in comparator:
        date_val = (
            datetime.fromisoformat(comparator["lte"])
            if isinstance(comparator["lte"], str)
            else comparator["lte"]
        )
        conditions.append(column <= date_val)

    return (
        and_(*conditions)
        if len(conditions) > 1
        else conditions[0]
        if conditions
        else None
    )


def build_id_condition(column, comparator):
    """Build an ID comparison condition for use in OR filters."""
    conditions = []
    if "eq" in comparator:
        conditions.append(column == comparator["eq"])
    if "neq" in comparator:
        conditions.append(column != comparator["neq"])
    if "in" in comparator:
        conditions.append(column.in_(comparator["in"]))
    if "notIn" in comparator:
        conditions.append(~column.in_(comparator["notIn"]))

    return (
        and_(*conditions)
        if len(conditions) > 1
        else conditions[0]
        if conditions
        else None
    )


def build_string_condition(column, comparator):
    """Build a string comparison condition for use in OR filters."""
    conditions = []
    if "eq" in comparator:
        conditions.append(column == comparator["eq"])
    if "neq" in comparator:
        conditions.append(column != comparator["neq"])
    if "contains" in comparator:
        conditions.append(column.like(f"%{comparator['contains']}%"))
    if "notContains" in comparator:
        conditions.append(~column.like(f"%{comparator['notContains']}%"))
    if "startsWith" in comparator:
        conditions.append(column.like(f"{comparator['startsWith']}%"))
    if "endsWith" in comparator:
        conditions.append(column.like(f"%{comparator['endsWith']}"))
    if "in" in comparator:
        conditions.append(column.in_(comparator["in"]))
    if "notIn" in comparator:
        conditions.append(~column.in_(comparator["notIn"]))
    if "containsIgnoreCase" in comparator:
        conditions.append(column.ilike(f"%{comparator['containsIgnoreCase']}%"))
    if "notContainsIgnoreCase" in comparator:
        conditions.append(~column.ilike(f"%{comparator['notContainsIgnoreCase']}%"))
    if "startsWithIgnoreCase" in comparator:
        conditions.append(column.ilike(f"{comparator['startsWithIgnoreCase']}%"))
    if "endsWithIgnoreCase" in comparator:
        conditions.append(column.ilike(f"%{comparator['endsWithIgnoreCase']}"))

    return (
        and_(*conditions)
        if len(conditions) > 1
        else conditions[0]
        if conditions
        else None
    )


def build_number_condition(column, comparator):
    """Build a number comparison condition for use in OR filters."""
    conditions = []
    if "eq" in comparator:
        conditions.append(column == comparator["eq"])
    if "neq" in comparator:
        conditions.append(column != comparator["neq"])
    if "gt" in comparator:
        conditions.append(column > comparator["gt"])
    if "gte" in comparator:
        conditions.append(column >= comparator["gte"])
    if "lt" in comparator:
        conditions.append(column < comparator["lt"])
    if "lte" in comparator:
        conditions.append(column <= comparator["lte"])
    if "in" in comparator:
        conditions.append(column.in_(comparator["in"]))
    if "notIn" in comparator:
        conditions.append(~column.in_(comparator["notIn"]))

    return (
        and_(*conditions)
        if len(conditions) > 1
        else conditions[0]
        if conditions
        else None
    )


@query.field("initiative")
def resolve_initiative(obj, info, **kwargs):
    """
    Resolve the initiative query.

    Args:
        obj: Parent object (unused for root queries)
        info: GraphQL resolve info containing context
        **kwargs: Query arguments including 'id' (required)

    Returns:
        Initiative: The requested initiative object

    Raises:
        Exception: If the initiative is not found
    """
    session: Session = info.context["session"]
    initiative_id = kwargs.get("id")

    # Query for the initiative by ID
    initiative = (
        session.query(Initiative).filter(Initiative.id == initiative_id).first()
    )

    if initiative is None:
        raise Exception(f"Initiative with id '{initiative_id}' not found")

    return initiative


def validate_initiative_filter(filter_dict, path="filter"):
    """
    Validate that the filter dictionary only contains supported operations.

    This function checks for unsupported filter features and raises clear errors.

    Args:
        filter_dict: Dictionary containing filter criteria
        path: Current path in the filter tree (for error messages)

    Raises:
        Exception: If unsupported filter operations are detected
    """
    if not filter_dict:
        return

    # Check for OR filters (not implemented)
    if "or" in filter_dict:
        raise Exception(
            f"OR filters are not currently supported. "
            f"Found at: {path}.or. "
            f"Please use only AND filters or separate queries."
        )

    # Check for AND filters recursively
    if "and" in filter_dict:
        for i, sub_filter in enumerate(filter_dict["and"]):
            validate_initiative_filter(sub_filter, f"{path}.and[{i}]")

    # Check for nested collection filters (not fully implemented)
    unsupported_nested_filters = {
        "ancestors": "InitiativeCollectionFilter",
        "teams": "TeamCollectionFilter",
    }

    for filter_name, filter_type in unsupported_nested_filters.items():
        if filter_name in filter_dict:
            raise Exception(
                f"Nested collection filters are not currently supported. "
                f"Found at: {path}.{filter_name} (type: {filter_type}). "
                f"Please use simpler filter criteria."
            )

    # Check for nested relation filters (not fully implemented)
    unsupported_relation_keys = {
        "creator": [
            "email",
            "name",
            "displayName",
            "active",
            "admin",
            "createdAt",
            "updatedAt",
        ],
        "owner": [
            "email",
            "name",
            "displayName",
            "active",
            "admin",
            "createdAt",
            "updatedAt",
        ],
    }

    for relation_name, unsupported_keys in unsupported_relation_keys.items():
        if relation_name in filter_dict:
            relation_filter = filter_dict[relation_name]

            # Validate that relation filter is a dictionary
            if not isinstance(relation_filter, dict):
                raise Exception(
                    f"Invalid filter value for relation '{relation_name}'. "
                    f"Expected a dictionary with 'null' or 'id' keys, got {type(relation_filter).__name__}."
                )

            # Check if any unsupported nested keys are present
            for key in relation_filter.keys():
                if key in unsupported_keys:
                    raise Exception(
                        f"Nested relation filters are not currently supported. "
                        f"Found at: {path}.{relation_name}.{key}. "
                        f"Only 'null' and 'id' filters are supported for relation fields."
                    )


def apply_initiative_filter(query, filter_dict):
    """
    Apply InitiativeFilter criteria to a SQLAlchemy query.

    This is a helper function that processes the filter dictionary and applies
    the appropriate WHERE clauses to the query.

    Args:
        query: SQLAlchemy query object
        filter_dict: Dictionary containing filter criteria

    Returns:
        Modified query with filters applied
    """
    if not filter_dict:
        return query

    # Handle compound filters
    if "and" in filter_dict:
        for sub_filter in filter_dict["and"]:
            query = apply_initiative_filter(query, sub_filter)

    # Note: OR filters are validated and rejected in validate_initiative_filter()

    # String comparators
    if "activityType" in filter_dict:
        # activityType is a computed field, not stored in DB
        # Skip this filter for now
        pass

    if "health" in filter_dict:
        query = apply_string_comparator(query, Initiative.health, filter_dict["health"])

    if "healthWithAge" in filter_dict:
        # healthWithAge is a computed field, not stored in DB
        # For now, we'll use the health field as a fallback
        query = apply_string_comparator(
            query, Initiative.health, filter_dict["healthWithAge"]
        )

    if "name" in filter_dict:
        query = apply_string_comparator(query, Initiative.name, filter_dict["name"])

    if "slugId" in filter_dict:
        query = apply_string_comparator(query, Initiative.slugId, filter_dict["slugId"])

    if "status" in filter_dict:
        query = apply_string_comparator(query, Initiative.status, filter_dict["status"])

    # Date comparators
    if "createdAt" in filter_dict:
        query = apply_date_comparator(
            query, Initiative.createdAt, filter_dict["createdAt"]
        )

    if "updatedAt" in filter_dict:
        query = apply_date_comparator(
            query, Initiative.updatedAt, filter_dict["updatedAt"]
        )

    if "targetDate" in filter_dict:
        query = apply_date_comparator(
            query, Initiative.targetDate, filter_dict["targetDate"]
        )

    # ID comparator
    if "id" in filter_dict:
        query = apply_id_comparator(query, Initiative.id, filter_dict["id"])

    # Relation filters (simplified - full implementation would need joins)
    if "creator" in filter_dict:
        creator_filter = filter_dict["creator"]
        if creator_filter.get("null") is True:
            query = query.filter(Initiative.creatorId.is_(None))
        elif creator_filter.get("null") is False:
            query = query.filter(Initiative.creatorId.isnot(None))
        if "id" in creator_filter:
            query = apply_id_comparator(
                query, Initiative.creatorId, creator_filter["id"]
            )

    if "owner" in filter_dict:
        owner_filter = filter_dict["owner"]
        if owner_filter.get("null") is True:
            query = query.filter(Initiative.ownerId.is_(None))
        elif owner_filter.get("null") is False:
            query = query.filter(Initiative.ownerId.isnot(None))
        if "id" in owner_filter:
            query = apply_id_comparator(query, Initiative.ownerId, owner_filter["id"])

    return query


def apply_initiative_sort(query, sort_list):
    """
    Apply InitiativeSortInput criteria to a SQLAlchemy query.

    This handles the [INTERNAL] sort parameter which provides more granular
    control over sorting than the standard orderBy parameter.

    Args:
        query: SQLAlchemy query object
        sort_list: List of sort input dictionaries

    Returns:
        Modified query with sorting applied
    """
    from sqlalchemy import asc, desc

    if not sort_list:
        return query

    # Build a list of order_by clauses
    order_clauses = []

    for sort_input in sort_list:
        # Each sort_input is a dictionary with one or more sort fields
        # Each field value is a dictionary with direction (e.g., {"direction": "ASC"})

        if "createdAt" in sort_input:
            direction = sort_input["createdAt"].get("direction", "ASC")
            order_clauses.append(
                asc(Initiative.createdAt)
                if direction == "ASC"
                else desc(Initiative.createdAt)
            )

        if "updatedAt" in sort_input:
            direction = sort_input["updatedAt"].get("direction", "ASC")
            order_clauses.append(
                asc(Initiative.updatedAt)
                if direction == "ASC"
                else desc(Initiative.updatedAt)
            )

        if "health" in sort_input:
            direction = sort_input["health"].get("direction", "ASC")
            order_clauses.append(
                asc(Initiative.health)
                if direction == "ASC"
                else desc(Initiative.health)
            )

        if "healthUpdatedAt" in sort_input:
            direction = sort_input["healthUpdatedAt"].get("direction", "ASC")
            order_clauses.append(
                asc(Initiative.healthUpdatedAt)
                if direction == "ASC"
                else desc(Initiative.healthUpdatedAt)
            )

        if "manual" in sort_input:
            # Manual sort uses sortOrder field
            direction = sort_input["manual"].get("direction", "ASC")
            order_clauses.append(
                asc(Initiative.sortOrder)
                if direction == "ASC"
                else desc(Initiative.sortOrder)
            )

        if "name" in sort_input:
            direction = sort_input["name"].get("direction", "ASC")
            order_clauses.append(
                asc(Initiative.name) if direction == "ASC" else desc(Initiative.name)
            )

        if "owner" in sort_input:
            # Sort by owner name - would require join with User table
            # For now, we'll sort by ownerId as a simplified implementation
            direction = sort_input["owner"].get("direction", "ASC")
            order_clauses.append(
                asc(Initiative.ownerId)
                if direction == "ASC"
                else desc(Initiative.ownerId)
            )

        if "targetDate" in sort_input:
            direction = sort_input["targetDate"].get("direction", "ASC")
            order_clauses.append(
                asc(Initiative.targetDate)
                if direction == "ASC"
                else desc(Initiative.targetDate)
            )

    # Apply all order clauses
    if order_clauses:
        query = query.order_by(*order_clauses)

    return query


@query.field("initiatives")
def resolve_initiatives(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filter: Optional[dict] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
    sort: Optional[list] = None,
):
    """
    Query all initiatives with filtering, sorting, and pagination.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        filter: InitiativeFilter to apply to results
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived initiatives (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)
        sort: [INTERNAL] Sort options for initiatives

    Returns:
        InitiativeConnection: Paginated list of initiatives
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query
    base_query = session.query(Initiative)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(Initiative.archivedAt.is_(None))

    # Validate and apply additional filters if provided
    if filter:
        validate_initiative_filter(filter)
        base_query = apply_initiative_filter(base_query, filter)

    # Validate that sort parameter is not used with cursors
    # The [INTERNAL] sort parameter uses complex multi-field sorting that is
    # incompatible with cursor-based pagination
    if sort and (after or before):
        raise Exception(
            "Cannot use cursor pagination (after/before) with the [INTERNAL] sort parameter. Use orderBy instead."
        )

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(Initiative, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, Initiative.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(Initiative, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, Initiative.id < cursor_id),
            )
        )

    # Apply sorting if provided (INTERNAL parameter)
    # Note: The sort parameter is marked as [INTERNAL] in the GraphQL schema
    # and provides more granular control over sorting than orderBy
    if sort:
        base_query = apply_initiative_sort(base_query, sort)
    else:
        # Apply default ordering based on orderBy parameter
        order_column = getattr(Initiative, order_field)
        if last or before:
            # For backward pagination, reverse the order
            base_query = base_query.order_by(order_column.desc(), Initiative.id.desc())
        else:
            base_query = base_query.order_by(order_column.asc(), Initiative.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


@query.field("document")
def resolve_document(obj, info, **kwargs):
    """
    Resolve the document query.

    Args:
        obj: Parent object (unused for root queries)
        info: GraphQL resolve info containing context
        **kwargs: Query arguments including 'id' (required)

    Returns:
        Document: The requested document object

    Raises:
        Exception: If the document is not found
    """
    session: Session = info.context["session"]
    document_id = kwargs.get("id")

    # Query for the document by ID
    document = session.query(Document).filter(Document.id == document_id).first()

    if document is None:
        raise Exception(f"Document with id '{document_id}' not found")

    return document


def validate_document_filter(filter_dict, path="filter"):
    """
    Validate that the filter dictionary only contains supported operations.

    This function checks for unsupported filter features and raises clear errors.

    Args:
        filter_dict: Dictionary containing filter criteria
        path: Current path in the filter tree (for error messages)

    Raises:
        Exception: If unsupported filter operations are detected
    """
    if not filter_dict:
        return

    # Check for OR filters (not implemented)
    if "or" in filter_dict:
        raise Exception(
            f"OR filters are not currently supported. "
            f"Found at: {path}.or. "
            f"Please use only AND filters or separate queries."
        )

    # Check for AND filters recursively
    if "and" in filter_dict:
        for i, sub_filter in enumerate(filter_dict["and"]):
            validate_document_filter(sub_filter, f"{path}.and[{i}]")

    # Check for nested relation filters (simplified - only basic fields supported)
    nested_relation_filters = ["creator", "initiative", "project"]

    for relation_name in nested_relation_filters:
        if relation_name in filter_dict:
            # For now, we support these but with limited nested filtering
            # We'll handle basic ID filtering in apply_document_filter
            pass


def apply_document_filter(query, filter_dict):
    """
    Apply DocumentFilter criteria to a SQLAlchemy query.

    This is a helper function that processes the filter dictionary and applies
    the appropriate WHERE clauses to the query.

    Args:
        query: SQLAlchemy query object
        filter_dict: Dictionary containing filter criteria

    Returns:
        Modified query with filters applied
    """
    if not filter_dict:
        return query

    # Handle compound filters
    if "and" in filter_dict:
        for sub_filter in filter_dict["and"]:
            query = apply_document_filter(query, sub_filter)

    # Note: OR filters are validated and rejected in validate_document_filter()

    # ID comparator
    if "id" in filter_dict:
        query = apply_id_comparator(query, Document.id, filter_dict["id"])

    # String comparators
    if "slugId" in filter_dict:
        query = apply_string_comparator(query, Document.slugId, filter_dict["slugId"])

    if "title" in filter_dict:
        query = apply_string_comparator(query, Document.title, filter_dict["title"])

    # Date comparators
    if "createdAt" in filter_dict:
        query = apply_date_comparator(
            query, Document.createdAt, filter_dict["createdAt"]
        )

    if "updatedAt" in filter_dict:
        query = apply_date_comparator(
            query, Document.updatedAt, filter_dict["updatedAt"]
        )

    # Nested relation filters
    if "creator" in filter_dict:
        creator_filter = filter_dict["creator"]
        # Join with User table if needed
        if not any(
            desc["entity"] is User
            for desc in query.column_descriptions
            if "entity" in desc
        ):
            from sqlalchemy.orm import aliased

            CreatorAlias = aliased(User)
            query = query.join(CreatorAlias, Document.creatorId == CreatorAlias.id)
            # Apply user filters on the aliased table
            if "id" in creator_filter:
                query = apply_id_comparator(
                    query, CreatorAlias.id, creator_filter["id"]
                )
            if "email" in creator_filter:
                query = apply_string_comparator(
                    query, CreatorAlias.email, creator_filter["email"]
                )
            if "name" in creator_filter:
                query = apply_string_comparator(
                    query, CreatorAlias.name, creator_filter["name"]
                )
        else:
            # Simple ID filtering without join
            if "id" in creator_filter:
                query = apply_id_comparator(
                    query, Document.creatorId, creator_filter["id"]
                )

    if "initiative" in filter_dict:
        initiative_filter = filter_dict["initiative"]
        # Simple ID filtering
        if "id" in initiative_filter:
            query = apply_id_comparator(
                query, Document.initiativeId, initiative_filter["id"]
            )

    if "project" in filter_dict:
        project_filter = filter_dict["project"]
        # Simple ID filtering
        if "id" in project_filter:
            query = apply_id_comparator(query, Document.projectId, project_filter["id"])

    return query


def validate_cycle_filter(filter_dict, path="filter"):
    """
    Validate that the filter dictionary only contains supported operations.

    Args:
        filter_dict: Dictionary containing filter criteria
        path: Current path in the filter tree (for error messages)

    Raises:
        Exception: If unsupported filter operations are detected
    """
    if not filter_dict:
        return

    # Check for OR filters (not implemented)
    if "or" in filter_dict:
        raise Exception(
            f"OR filters are not currently supported. "
            f"Found at: {path}.or. "
            f"Please use only AND filters or separate queries."
        )

    # Check for AND filters recursively
    if "and" in filter_dict:
        for i, sub_filter in enumerate(filter_dict["and"]):
            validate_cycle_filter(sub_filter, f"{path}.and[{i}]")

    # Check for nested issue collection filters (not implemented)
    if "issues" in filter_dict:
        raise Exception(
            f"Nested collection filters are not currently supported. "
            f"Found at: {path}.issues. "
            f"Please filter cycles and issues separately."
        )

    # Check for nested team filters (limited support)
    if "team" in filter_dict:
        team_filter = filter_dict["team"]
        if team_filter and isinstance(team_filter, dict):
            # Only 'id' filter is supported for team
            unsupported_keys = [k for k in team_filter.keys() if k not in ["id"]]
            if unsupported_keys:
                raise Exception(
                    f"Complex nested team filters are not currently supported. "
                    f"Found at: {path}.team.{unsupported_keys[0]}. "
                    f"Only 'id' filter is supported for team field."
                )


def apply_cycle_filter(query, filter_dict):
    """
    Apply CycleFilter criteria to a SQLAlchemy query.

    Args:
        query: SQLAlchemy query object
        filter_dict: Dictionary containing filter criteria

    Returns:
        Modified query with filters applied
    """
    if not filter_dict:
        return query

    # Handle compound filters
    if "and" in filter_dict:
        for sub_filter in filter_dict["and"]:
            query = apply_cycle_filter(query, sub_filter)

    # ID comparator
    if "id" in filter_dict:
        query = apply_id_comparator(query, Cycle.id, filter_dict["id"])

    # String comparators
    if "name" in filter_dict:
        query = apply_nullable_string_comparator(query, Cycle.name, filter_dict["name"])

    # Number comparators
    if "number" in filter_dict:
        query = apply_number_comparator(query, Cycle.number, filter_dict["number"])

    # Date comparators
    if "completedAt" in filter_dict:
        query = apply_nullable_date_comparator(
            query, Cycle.completedAt, filter_dict["completedAt"]
        )

    if "createdAt" in filter_dict:
        query = apply_date_comparator(query, Cycle.createdAt, filter_dict["createdAt"])

    if "endsAt" in filter_dict:
        query = apply_date_comparator(query, Cycle.endsAt, filter_dict["endsAt"])

    if "startsAt" in filter_dict:
        query = apply_date_comparator(query, Cycle.startsAt, filter_dict["startsAt"])

    if "updatedAt" in filter_dict:
        query = apply_date_comparator(query, Cycle.updatedAt, filter_dict["updatedAt"])

    # Boolean comparators
    if "isActive" in filter_dict:
        query = apply_boolean_comparator(query, Cycle.isActive, filter_dict["isActive"])

    if "isFuture" in filter_dict:
        query = apply_boolean_comparator(query, Cycle.isFuture, filter_dict["isFuture"])

    if "isInCooldown" in filter_dict:
        # Note: isInCooldown is a computed field in GraphQL but not stored in the database
        # We'll skip this for now as it requires more complex logic
        pass

    if "isNext" in filter_dict:
        query = apply_boolean_comparator(query, Cycle.isNext, filter_dict["isNext"])

    if "isPast" in filter_dict:
        query = apply_boolean_comparator(query, Cycle.isPast, filter_dict["isPast"])

    if "isPrevious" in filter_dict:
        query = apply_boolean_comparator(
            query, Cycle.isPrevious, filter_dict["isPrevious"]
        )

    # Nested relation filters
    if "team" in filter_dict:
        team_filter = filter_dict["team"]
        # Simple ID filtering
        if "id" in team_filter:
            query = apply_id_comparator(query, Cycle.teamId, team_filter["id"])

    return query


@query.field("cycles")
def resolve_cycles(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filter: Optional[dict] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
):
    """
    Query all cycles with filtering, sorting, and pagination.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        filter: CycleFilter to apply to results
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived cycles (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)

    Returns:
        CycleConnection: Paginated list of cycles
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query
    base_query = session.query(Cycle)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(Cycle.archivedAt.is_(None))

    # Validate and apply additional filters if provided
    if filter:
        validate_cycle_filter(filter)
        base_query = apply_cycle_filter(base_query, filter)

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(Cycle, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, Cycle.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(Cycle, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, Cycle.id < cursor_id),
            )
        )

    # Apply ordering
    order_column = getattr(Cycle, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), Cycle.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), Cycle.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


@query.field("documents")
def resolve_documents(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filter: Optional[dict] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
):
    """
    Query all documents with filtering, sorting, and pagination.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        filter: DocumentFilter to apply to results
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived documents (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)

    Returns:
        DocumentConnection: Paginated list of documents
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query
    base_query = session.query(Document)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(Document.archivedAt.is_(None))

    # Validate and apply additional filters if provided
    if filter:
        validate_document_filter(filter)
        base_query = apply_document_filter(base_query, filter)

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(Document, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, Document.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(Document, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, Document.id < cursor_id),
            )
        )

    # Apply default ordering based on orderBy parameter
    order_column = getattr(Document, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), Document.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), Document.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


@query.field("searchDocuments")
def resolve_searchDocuments(
    obj,
    info,
    term: str,
    after: Optional[str] = None,
    before: Optional[str] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    includeComments: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
    snippetSize: Optional[float] = None,
    teamId: Optional[str] = None,
):
    """
    Search documents.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        term: Search string to look for
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived documents (default: false)
        includeComments: Whether to search associated comments (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)
        snippetSize: [Deprecated] Size of search snippet to return (default: 100)
        teamId: UUID of a team to use as a boost

    Returns:
        DocumentSearchPayload: Search results with edges, nodes, pageInfo, totalCount, and archivePayload
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query for documents
    base_query = session.query(Document)

    # Apply search term filter (search in title and content)
    if term:
        search_pattern = f"%{term}%"
        search_conditions = [
            Document.title.like(search_pattern),
            Document.content.like(search_pattern),
        ]

        # If includeComments is true, search in comments too
        if includeComments:
            # Subquery to find document IDs that have matching comments
            comment_subquery = (
                session.query(Comment.documentId)
                .filter(Comment.body.like(search_pattern))
                .distinct()
            )

            # Add condition to include documents with matching comments
            search_conditions.append(Document.id.in_(comment_subquery))

        base_query = base_query.filter(or_(*search_conditions))

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(Document.archivedAt.is_(None))

    # Apply team filter if provided (as a boost/filter)
    if teamId:
        base_query = base_query.filter(Document.teamId == teamId)

    # Get total count before pagination
    total_count = base_query.count()

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(Document, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, Document.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(Document, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, Document.id < cursor_id),
            )
        )

    # Apply ordering
    order_column = getattr(Document, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), Document.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), Document.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    pagination_result = apply_pagination(items, after, before, first, last, order_field)

    # DocumentSearchResult nodes are the Document objects with metadata
    # The metadata field will be empty for now
    nodes = []
    for doc in pagination_result["nodes"]:
        # Each node is a Document with an additional metadata field
        # In a real implementation, metadata might include search relevance scores, snippets, etc.
        # For now, we'll let the GraphQL layer handle the Document fields
        # and add an empty metadata object
        nodes.append(doc)

    # Build archivePayload (empty for now as we don't have archived entities)
    archive_payload = {"success": True, "lastSyncId": 0.0}

    # Build and return the DocumentSearchPayload
    return {
        "nodes": nodes,
        "edges": pagination_result["edges"],
        "pageInfo": pagination_result["pageInfo"],
        "totalCount": float(total_count),
        "archivePayload": archive_payload,
    }


@query.field("cycle")
def resolve_cycle(obj, info, id: str):
    """
    Query one specific cycle by its id.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        id: The cycle id to look up

    Returns:
        Cycle: The cycle with the specified id

    Raises:
        Exception: If the cycle is not found
    """
    session: Session = info.context["session"]

    # Query for the cycle by id
    cycle = session.query(Cycle).filter(Cycle.id == id).first()

    if not cycle:
        raise Exception(f"Cycle with id '{id}' not found")

    return cycle


@query.field("teamMembership")
def resolve_teamMembership(obj, info, id: str):
    """
    Query one specific team membership by its id.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        id: The team membership id to look up

    Returns:
        TeamMembership: The team membership with the specified id

    Raises:
        Exception: If the team membership is not found
    """
    session: Session = info.context["session"]

    # Query for the team membership by id
    team_membership = (
        session.query(TeamMembership).filter(TeamMembership.id == id).first()
    )

    if not team_membership:
        raise Exception(f"TeamMembership with id '{id}' not found")

    return team_membership


@query.field("teamMemberships")
def resolve_teamMemberships(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
):
    """
    Query all team memberships.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived team memberships (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)

    Returns:
        TeamMembershipConnection: Paginated list of team memberships
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query
    base_query = session.query(TeamMembership)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(TeamMembership.archivedAt.is_(None))

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(TeamMembership, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, TeamMembership.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(TeamMembership, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, TeamMembership.id < cursor_id),
            )
        )

    # Apply ordering
    order_column = getattr(TeamMembership, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), TeamMembership.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), TeamMembership.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


@query.field("initiativeRelation")
def resolve_initiativeRelation(obj, info, id: str):
    """
    One specific initiative relation.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        id: The initiative relation id to look up

    Returns:
        InitiativeRelation: The initiative relation with the specified id
    """
    session: Session = info.context["session"]

    # Query for the initiative relation by id
    initiative_relation = (
        session.query(InitiativeRelation).filter(InitiativeRelation.id == id).first()
    )

    if not initiative_relation:
        raise Exception(f"InitiativeRelation with id '{id}' not found")

    return initiative_relation


@query.field("initiativeRelations")
def resolve_initiativeRelations(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
):
    """
    All initiative relationships.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        first: Number of items for forward pagination
        includeArchived: Include archived initiative relations (default: False)
        last: Number of items for backward pagination
        orderBy: Order by field (createdAt or updatedAt)

    Returns:
        dict: InitiativeRelationConnection with edges, nodes, and pageInfo
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine order field
    order_field = orderBy if orderBy else "createdAt"
    if order_field not in ["createdAt", "updatedAt"]:
        raise Exception(
            f"Invalid orderBy field: {order_field}. Must be 'createdAt' or 'updatedAt'"
        )

    # Build base query
    base_query = session.query(InitiativeRelation)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(InitiativeRelation.archivedAt.is_(None))

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(InitiativeRelation, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(
                    order_column == cursor_field_value,
                    InitiativeRelation.id > cursor_id,
                ),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(InitiativeRelation, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(
                    order_column == cursor_field_value,
                    InitiativeRelation.id < cursor_id,
                ),
            )
        )

    # Apply ordering
    order_column = getattr(InitiativeRelation, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(
            order_column.desc(), InitiativeRelation.id.desc()
        )
    else:
        base_query = base_query.order_by(
            order_column.asc(), InitiativeRelation.id.asc()
        )

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


@query.field("initiativeToProject")
def resolve_initiativeToProject(obj, info, id: str):
    """
    One specific initiativeToProject.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        id: The initiativeToProject id to look up

    Returns:
        InitiativeToProject: The initiativeToProject with the specified id

    Raises:
        Exception: If the initiativeToProject is not found
    """
    session: Session = info.context["session"]

    # Query for the initiativeToProject by id
    initiative_to_project = (
        session.query(InitiativeToProject).filter(InitiativeToProject.id == id).first()
    )

    if not initiative_to_project:
        raise Exception(f"InitiativeToProject with id '{id}' not found")

    return initiative_to_project


@query.field("initiativeToProjects")
def resolve_initiativeToProjects(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
):
    """
    Query all initiativeToProject entities with pagination.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived records (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)

    Returns:
        InitiativeToProjectConnection: Paginated list of initiativeToProject entities
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query
    base_query = session.query(InitiativeToProject)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(InitiativeToProject.archivedAt.is_(None))

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(InitiativeToProject, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(
                    order_column == cursor_field_value,
                    InitiativeToProject.id > cursor_id,
                ),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(InitiativeToProject, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(
                    order_column == cursor_field_value,
                    InitiativeToProject.id < cursor_id,
                ),
            )
        )

    # Apply ordering
    order_column = getattr(InitiativeToProject, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(
            order_column.desc(), InitiativeToProject.id.desc()
        )
    else:
        base_query = base_query.order_by(
            order_column.asc(), InitiativeToProject.id.asc()
        )

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


# ============================================================================
# InitiativeToProject Mutations
# ============================================================================


@mutation.field("initiativeToProjectCreate")
def resolve_initiativeToProjectCreate(obj, info, **kwargs):
    """
    Creates a new initiativeToProject join.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'input' with InitiativeToProjectCreateInput data

    Returns:
        The created InitiativeToProject entity
    """
    import uuid

    session: Session = info.context["session"]
    input_data = kwargs.get("input", {})

    try:
        # Extract input fields
        initiative_to_project_id = input_data.get("id") or str(uuid.uuid4())
        initiative_id = input_data["initiativeId"]  # Required
        project_id = input_data["projectId"]  # Required
        sort_order = input_data.get("sortOrder", 0.0)  # Optional, default to 0.0

        # Generate timestamps
        now = datetime.now(timezone.utc)

        # Create the InitiativeToProject entity
        initiative_to_project = InitiativeToProject(
            id=initiative_to_project_id,
            initiativeId=initiative_id,
            projectId=project_id,
            sortOrder=str(sort_order),  # Convert to string as per ORM schema
            createdAt=now,
            updatedAt=now,
            archivedAt=None,
        )

        session.add(initiative_to_project)

        # Return the proper InitiativeToProjectPayload structure
        return {
            "success": True,
            "lastSyncId": 0.0,
            "initiativeToProject": initiative_to_project,
        }

    except KeyError as e:
        raise Exception(f"Missing required field: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to create initiativeToProject: {str(e)}")


@mutation.field("initiativeToProjectUpdate")
def resolve_initiativeToProjectUpdate(obj, info, **kwargs):
    """
    Updates an initiativeToProject.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (String!) and 'input' with InitiativeToProjectUpdateInput data

    Returns:
        The updated InitiativeToProject entity
    """

    session: Session = info.context["session"]
    entity_id = kwargs.get("id")
    input_data = kwargs.get("input", {})

    if not entity_id:
        raise Exception("Missing required field: id")

    try:
        # Query for the entity
        entity = session.query(InitiativeToProject).filter_by(id=entity_id).first()

        if not entity:
            raise Exception(f"InitiativeToProject with id '{entity_id}' not found")

        # Update fields from input
        if "sortOrder" in input_data:
            # Convert to string as per ORM schema
            entity.sortOrder = str(input_data["sortOrder"])

        # Update the updatedAt timestamp
        entity.updatedAt = datetime.now(timezone.utc)

        # Return the proper InitiativeToProjectPayload structure
        return {"success": True, "lastSyncId": 0.0, "initiativeToProject": entity}

    except Exception as e:
        raise Exception(f"Failed to update initiativeToProject: {str(e)}")


@mutation.field("initiativeToProjectDelete")
def resolve_initiativeToProjectDelete(obj, info, **kwargs):
    """
    Deletes an initiativeToProject.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (String!) - The identifier of the initiativeToProject to delete

    Returns:
        DeletePayload with success status and entityId
    """

    session: Session = info.context["session"]
    entity_id = kwargs.get("id")

    if not entity_id:
        raise Exception("Missing required field: id")

    try:
        # Query for the entity
        entity = session.query(InitiativeToProject).filter_by(id=entity_id).first()

        if not entity:
            raise Exception(f"InitiativeToProject with id '{entity_id}' not found")

        # Soft delete by setting archivedAt timestamp
        entity.archivedAt = datetime.now(timezone.utc)
        entity.updatedAt = datetime.now(timezone.utc)

        # Return DeletePayload structure
        return {
            "success": True,
            "entityId": entity_id,
            "lastSyncId": 0.0,  # Placeholder value - adjust based on your sync logic
        }

    except Exception as e:
        raise Exception(f"Failed to delete initiativeToProject: {str(e)}")


@query.field("externalUser")
def resolve_externalUser(obj, info, id: str):
    """
    Query one specific external user by its id.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        id: The identifier of the external user to retrieve

    Returns:
        ExternalUser: The external user with the specified id
    """
    session: Session = info.context["session"]

    # Query for the external user by id
    external_user = session.query(ExternalUser).filter(ExternalUser.id == id).first()

    if not external_user:
        raise Exception(f"ExternalUser with id '{id}' not found")

    return external_user


@query.field("externalUsers")
def resolve_externalUsers(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
):
    """
    Query all external users for the organization.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived users (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)

    Returns:
        ExternalUserConnection: Paginated list of external users
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query
    base_query = session.query(ExternalUser)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(ExternalUser.archivedAt.is_(None))

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(ExternalUser, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, ExternalUser.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(ExternalUser, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, ExternalUser.id < cursor_id),
            )
        )

    # Apply ordering based on orderBy parameter
    order_column = getattr(ExternalUser, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), ExternalUser.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), ExternalUser.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


# =============================================================================
# MUTATIONS - Comment
# =============================================================================


@mutation.field("commentCreate")
def resolve_commentCreate(obj, info, **kwargs):
    """
    Creates a new comment.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'input' with CommentCreateInput data

    Returns:
        Dict containing the created Comment entity
    """
    import uuid

    session: Session = info.context["session"]
    input_data = kwargs.get("input", {})

    try:
        # Extract input fields
        comment_id = input_data.get("id") or str(uuid.uuid4())
        body = input_data.get("body", "")
        body_data = input_data.get("bodyData", "{}")
        created_at = input_data.get("createdAt") or datetime.now(timezone.utc)
        issue_id = input_data.get("issueId")
        parent_id = input_data.get("parentId")
        document_content_id = input_data.get("documentContentId")
        initiative_update_id = input_data.get("initiativeUpdateId")
        post_id = input_data.get("postId")
        project_update_id = input_data.get("projectUpdateId")
        quoted_text = input_data.get("quotedText")

        # Fields not yet supported by ORM but in GraphQL schema
        # createAsUser, createOnSyncedSlackThread, displayIconUrl,
        # doNotSubscribeToIssue, subscriberIds - these would require additional logic

        # Generate URL (simplified - in production this would be based on issue/post context)
        url = f"https://linear.app/comment/{comment_id}"

        # Create the Comment entity
        comment = Comment(
            id=comment_id,
            body=body,
            bodyData=body_data,
            createdAt=created_at,
            updatedAt=created_at,
            url=url,
            reactionData={},  # Empty reaction data for new comments
            issueId=issue_id,
            parentId=parent_id,
            documentContentId=document_content_id,
            initiativeUpdateId=initiative_update_id,
            postId=post_id,
            projectUpdateId=project_update_id,
            quotedText=quoted_text,
        )

        # Handle subscribers if provided
        subscriber_ids = input_data.get("subscriberIds", [])
        if subscriber_ids:
            # Fetch subscriber users
            subscribers = session.query(User).filter(User.id.in_(subscriber_ids)).all()
            comment.subscribers = subscribers

        # Get current user from context for comment author
        current_user_id = info.context.get("user_id") or info.context.get(
            "impersonate_user_id"
        )
        if current_user_id:
            comment.userId = current_user_id

        session.add(comment)
        session.flush()
        session.refresh(comment)

        now_timestamp = datetime.now(timezone.utc)
        return {
            "success": True,
            "comment": comment,
            "lastSyncId": float(now_timestamp.timestamp()),
        }

    except Exception as e:
        # Ensure the DB session is clean for middleware commit
        try:
            session.rollback()
        except Exception:
            pass
        raise Exception(f"Failed to create comment: {str(e)}")


@mutation.field("commentResolve")
def resolve_commentResolve(obj, info, **kwargs):
    """
    Resolves a comment thread.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' and optional 'resolvingCommentId'

    Returns:
        The updated Comment entity
    """

    session: Session = info.context["session"]
    comment_id = kwargs.get("id")
    resolving_comment_id = kwargs.get("resolvingCommentId")

    try:
        # Fetch the comment to resolve
        comment = session.query(Comment).filter_by(id=comment_id).first()

        if not comment:
            raise Exception(f"Comment with id {comment_id} not found")

        # Update the resolution fields
        comment.resolvedAt = datetime.now(timezone.utc)
        comment.resolvingCommentId = resolving_comment_id
        comment.updatedAt = datetime.now(timezone.utc)

        # If a resolving comment is provided, we might want to set the resolvingUser
        # based on that comment's user (if available in the model)
        if resolving_comment_id:
            resolving_comment = (
                session.query(Comment).filter_by(id=resolving_comment_id).first()
            )
            if resolving_comment and hasattr(resolving_comment, "userId"):
                comment.resolvingUserId = resolving_comment.userId

        return comment

    except Exception as e:
        raise Exception(f"Failed to resolve comment: {str(e)}")


@mutation.field("commentUnresolve")
def resolve_commentUnresolve(obj, info, **kwargs):
    """
    Unresolves a comment thread.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' - the comment ID to unresolve

    Returns:
        The updated Comment entity
    """

    session: Session = info.context["session"]
    comment_id = kwargs.get("id")

    try:
        # Fetch the comment to unresolve
        comment = session.query(Comment).filter_by(id=comment_id).first()

        if not comment:
            raise Exception(f"Comment with id {comment_id} not found")

        # Clear the resolution fields
        comment.resolvedAt = None
        comment.resolvingCommentId = None
        comment.resolvingUserId = None
        comment.updatedAt = datetime.now(timezone.utc)

        return comment

    except Exception as e:
        raise Exception(f"Failed to unresolve comment: {str(e)}")


@mutation.field("commentUpdate")
def resolve_commentUpdate(obj, info, **kwargs):
    """
    Updates a comment.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (comment ID) and 'input' with CommentUpdateInput data

    Returns:
        The updated Comment entity
    """

    session: Session = info.context["session"]
    comment_id = kwargs.get("id")
    input_data = kwargs.get("input", {})

    try:
        # Fetch the comment to update
        comment = session.query(Comment).filter_by(id=comment_id).first()

        if not comment:
            raise Exception(f"Comment with id {comment_id} not found")

        # Update fields if provided in input
        if "body" in input_data:
            comment.body = input_data["body"]

        if "bodyData" in input_data:
            comment.bodyData = input_data["bodyData"]

        if "quotedText" in input_data:
            comment.quotedText = input_data["quotedText"]

        if "resolvingCommentId" in input_data:
            comment.resolvingCommentId = input_data["resolvingCommentId"]

        if "resolvingUserId" in input_data:
            comment.resolvingUserId = input_data["resolvingUserId"]

        # Handle subscribers if provided
        if "subscriberIds" in input_data:
            subscriber_ids = input_data["subscriberIds"]
            if subscriber_ids:
                # Fetch subscriber users
                subscribers = (
                    session.query(User).filter(User.id.in_(subscriber_ids)).all()
                )
                comment.subscribers = subscribers
            else:
                # Clear subscribers if empty list provided
                comment.subscribers = []

        # Update editedAt timestamp if body was modified
        if "body" in input_data or "bodyData" in input_data:
            comment.editedAt = datetime.now(timezone.utc)

        # Always update updatedAt
        comment.updatedAt = datetime.now(timezone.utc)

        return comment

    except Exception as e:
        raise Exception(f"Failed to update comment: {str(e)}")


@mutation.field("commentDelete")
def resolve_commentDelete(obj, info, **kwargs):
    """
    Deletes a comment.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (comment ID to delete)

    Returns:
        Dict containing DeletePayload with entityId, success, and lastSyncId
    """

    session: Session = info.context["session"]
    comment_id = kwargs.get("id")

    try:
        # Fetch the comment to delete
        comment = session.query(Comment).filter_by(id=comment_id).first()

        if not comment:
            raise Exception(f"Comment with id {comment_id} not found")

        # Soft delete by setting archivedAt timestamp
        comment.archivedAt = datetime.now(timezone.utc)
        comment.updatedAt = datetime.now(timezone.utc)

        # Return DeletePayload structure
        return {
            "entityId": comment_id,
            "success": True,
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
        }

    except Exception as e:
        raise Exception(f"Failed to delete comment: {str(e)}")


# ============================================================================
# Attachment Mutations
# ============================================================================


@mutation.field("attachmentCreate")
def resolve_attachmentCreate(obj, info, **kwargs):
    """
    Creates a new attachment, or updates existing if the same `url` and `issueId` is used.

    Args:
        obj: The parent object (unused for mutations)
        info: GraphQL resolve info containing context
        **kwargs: Mutation arguments including 'input'

    Returns:
        The created or updated Attachment entity
    """
    session: Session = info.context["session"]

    try:
        # Extract input data
        input_data = kwargs.get("input", {})

        # Validate required fields
        if not input_data.get("issueId"):
            raise Exception("Field 'issueId' is required")
        if not input_data.get("title"):
            raise Exception("Field 'title' is required")
        if not input_data.get("url"):
            raise Exception("Field 'url' is required")

        # Check if attachment already exists with same url and issueId
        # As per spec: "updates existing if the same `url` and `issueId` is used"
        existing_attachment = (
            session.query(Attachment)
            .filter(
                and_(
                    Attachment.url == input_data["url"],
                    Attachment.issueId == input_data["issueId"],
                )
            )
            .first()
        )

        if existing_attachment:
            # Update existing attachment
            attachment = existing_attachment

            # Update fields
            attachment.title = input_data["title"]
            if "subtitle" in input_data:
                attachment.subtitle = input_data.get("subtitle")
            if "iconUrl" in input_data:
                attachment.iconUrl = input_data.get("iconUrl")
            if "groupBySource" in input_data:
                attachment.groupBySource = input_data["groupBySource"]
            if "metadata" in input_data:
                attachment.metadata_ = input_data.get("metadata", {})

            # Update timestamp
            attachment.updatedAt = datetime.utcnow()

        else:
            # Create new attachment
            import uuid

            # Generate ID if not provided
            attachment_id = input_data.get("id", str(uuid.uuid4()))

            # Build attachment data
            attachment_data = {
                "id": attachment_id,
                "issueId": input_data["issueId"],
                "url": input_data["url"],
                "title": input_data["title"],
                "subtitle": input_data.get("subtitle"),
                "iconUrl": input_data.get("iconUrl"),
                "groupBySource": input_data.get("groupBySource", False),
                "metadata_": input_data.get("metadata", {}),
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }

            # Create the attachment entity
            attachment = Attachment(**attachment_data)
            session.add(attachment)

        # Handle linked comment creation if commentBody or commentBodyData is provided
        comment_body = input_data.get("commentBody")
        comment_body_data = input_data.get("commentBodyData")

        if comment_body or comment_body_data:
            import uuid

            # Create a linked comment
            comment_data = {
                "id": str(uuid.uuid4()),
                "issueId": input_data["issueId"],
                "body": comment_body or "",
                "bodyData": json.dumps(comment_body_data)
                if comment_body_data
                else comment_body or "",
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }

            # Handle createAsUser - this would set externalUserId
            # This is a special OAuth parameter that's not directly stored in attachment
            # In a real implementation, you would create an ExternalUser record
            create_as_user = input_data.get("createAsUser")
            if create_as_user:
                # For now, we'll skip this complex logic
                # In production, you'd create or find an ExternalUser with name=createAsUser
                pass

            comment = Comment(**comment_data)
            session.add(comment)

        return attachment

    except Exception as e:
        raise Exception(f"Failed to create attachment: {str(e)}")


@mutation.field("attachmentDelete")
def resolve_attachmentDelete(obj, info, **kwargs):
    """
    Deletes an issue attachment.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (attachment ID to delete)

    Returns:
        Dict containing DeletePayload with entityId, success, and lastSyncId
    """

    session: Session = info.context["session"]
    attachment_id = kwargs.get("id")

    try:
        # Fetch the attachment to delete
        attachment = session.query(Attachment).filter_by(id=attachment_id).first()

        if not attachment:
            raise Exception(f"Attachment with id {attachment_id} not found")

        # Soft delete by setting archivedAt timestamp
        attachment.archivedAt = datetime.now(timezone.utc)
        attachment.updatedAt = datetime.now(timezone.utc)

        # Return DeletePayload structure
        return {
            "entityId": attachment_id,
            "success": True,
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
        }

    except Exception as e:
        raise Exception(f"Failed to delete attachment: {str(e)}")


@mutation.field("attachmentLinkDiscord")
def resolve_attachmentLinkDiscord(obj, info, **kwargs):
    """
    Link an existing Discord message to an issue.

    Args:
        obj: The parent object (unused for mutations)
        info: GraphQL resolve info containing context
        **kwargs: Mutation arguments:
            - channelId: Discord channel ID (required)
            - messageId: Discord message ID (required)
            - url: Discord message URL (required)
            - issueId: Issue ID to link to (required)
            - id: Optional custom attachment ID
            - title: Optional attachment title
            - createAsUser: Optional user name for OAuth apps
            - displayIconUrl: Optional external user avatar URL

    Returns:
        The created Attachment entity
    """
    import uuid

    session: Session = info.context["session"]

    try:
        # Extract required fields
        channel_id = kwargs.get("channelId")
        message_id = kwargs.get("messageId")
        url = kwargs.get("url")
        issue_id = kwargs.get("issueId")

        # Validate required fields
        if not channel_id:
            raise Exception("Field 'channelId' is required")
        if not message_id:
            raise Exception("Field 'messageId' is required")
        if not url:
            raise Exception("Field 'url' is required")
        if not issue_id:
            raise Exception("Field 'issueId' is required")

        # Verify the issue exists
        issue = session.query(Issue).filter_by(id=issue_id).first()
        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        # Check if attachment with same URL and issueId already exists
        existing_attachment = (
            session.query(Attachment)
            .filter(and_(Attachment.url == url, Attachment.issueId == issue_id))
            .first()
        )

        if existing_attachment:
            # Update existing attachment
            attachment = existing_attachment
            if kwargs.get("title"):
                attachment.title = kwargs["title"]
            attachment.updatedAt = datetime.utcnow()
        else:
            # Generate ID if not provided
            attachment_id = kwargs.get("id", str(uuid.uuid4()))

            # Build source metadata for Discord
            source_metadata = {
                "type": "discord",
                "channelId": channel_id,
                "messageId": message_id,
            }

            # Build attachment data
            attachment_data = {
                "id": attachment_id,
                "issueId": issue_id,
                "url": url,
                "title": kwargs.get("title", f"Discord message {message_id}"),
                "sourceType": "discord",
                "source": source_metadata,
                "groupBySource": True,  # Discord messages should be grouped
                "metadata_": {},
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }

            # Handle displayIconUrl
            if kwargs.get("displayIconUrl"):
                attachment_data["iconUrl"] = kwargs["displayIconUrl"]

            # Handle createAsUser - create or find ExternalUser
            create_as_user = kwargs.get("createAsUser")
            if create_as_user:
                # Find or create external user
                external_user = (
                    session.query(ExternalUser).filter_by(name=create_as_user).first()
                )

                if not external_user:
                    external_user = ExternalUser(
                        id=str(uuid.uuid4()),
                        name=create_as_user,
                        avatarUrl=kwargs.get("displayIconUrl"),
                        createdAt=datetime.utcnow(),
                        updatedAt=datetime.utcnow(),
                    )
                    session.add(external_user)
                    session.flush()  # Ensure external_user.id is available

                attachment_data["externalUserCreatorId"] = external_user.id

            # Create the attachment entity
            attachment = Attachment(**attachment_data)
            session.add(attachment)

        return attachment

    except Exception as e:
        raise Exception(f"Failed to link Discord attachment: {str(e)}")


@mutation.field("attachmentLinkFront")
def resolve_attachmentLinkFront(obj, info, **kwargs):
    """
    Link an existing Front conversation to an issue.

    Args:
        conversationId: The Front conversation ID to link (required)
        issueId: The issue for which to link the Front conversation (required)
        title: The title to use for the attachment (optional)
        id: Optional attachment ID that may be provided through the API (optional)
        createAsUser: Create attachment as a user with the provided name (optional)
        displayIconUrl: Provide an external user avatar URL (optional)

    Returns:
        FrontAttachmentPayload with the created attachment
    """
    import uuid

    session: Session = info.context["session"]

    try:
        # Extract required fields
        conversation_id = kwargs.get("conversationId")
        issue_id = kwargs.get("issueId")

        # Validate required fields
        if not conversation_id:
            raise Exception("Field 'conversationId' is required")
        if not issue_id:
            raise Exception("Field 'issueId' is required")

        # Verify the issue exists
        issue = session.query(Issue).filter_by(id=issue_id).first()
        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        # Generate a URL for the Front conversation
        # Front URLs follow the pattern: https://app.frontapp.com/open/{conversationId}
        url = f"https://app.frontapp.com/open/{conversation_id}"

        # Check if attachment with same conversation ID and issueId already exists
        existing_attachment = (
            session.query(Attachment)
            .filter(and_(Attachment.url == url, Attachment.issueId == issue_id))
            .first()
        )

        if existing_attachment:
            # Update existing attachment
            attachment = existing_attachment
            if kwargs.get("title"):
                attachment.title = kwargs["title"]
            attachment.updatedAt = datetime.utcnow()
        else:
            # Generate ID if not provided
            attachment_id = kwargs.get("id", str(uuid.uuid4()))

            # Build source metadata for Front
            source_metadata = {"type": "front", "conversationId": conversation_id}

            # Build attachment data
            attachment_data = {
                "id": attachment_id,
                "issueId": issue_id,
                "url": url,
                "title": kwargs.get("title", f"Front conversation {conversation_id}"),
                "sourceType": "front",
                "source": source_metadata,
                "groupBySource": True,  # Front conversations should be grouped
                "metadata_": {},
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }

            # Handle displayIconUrl
            if kwargs.get("displayIconUrl"):
                attachment_data["iconUrl"] = kwargs["displayIconUrl"]

            # Handle createAsUser - create or find ExternalUser
            create_as_user = kwargs.get("createAsUser")
            if create_as_user:
                # Find or create external user
                external_user = (
                    session.query(ExternalUser).filter_by(name=create_as_user).first()
                )

                if not external_user:
                    external_user = ExternalUser(
                        id=str(uuid.uuid4()),
                        name=create_as_user,
                        avatarUrl=kwargs.get("displayIconUrl"),
                        createdAt=datetime.utcnow(),
                        updatedAt=datetime.utcnow(),
                    )
                    session.add(external_user)
                    session.flush()  # Ensure external_user.id is available

                attachment_data["externalUserCreatorId"] = external_user.id

            # Create the attachment entity
            attachment = Attachment(**attachment_data)
            session.add(attachment)

        # Flush to get the attachment ID
        session.flush()

        # Return the proper FrontAttachmentPayload structure
        return {"success": True, "lastSyncId": 0.0, "attachment": attachment}

    except Exception as e:
        raise Exception(f"Failed to link Front attachment: {str(e)}")


@mutation.field("attachmentLinkGitHubIssue")
def resolve_attachmentLinkGitHubIssue(obj, info, **kwargs):
    """
    Link a GitHub issue to a Linear issue.

    Args:
        url: The URL of the GitHub issue to link (required)
        issueId: The Linear issue for which to link the GitHub issue (required)
        title: The title to use for the attachment (optional)
        id: Optional attachment ID that may be provided through the API (optional)
        createAsUser: Create attachment as a user with the provided name (optional)
        displayIconUrl: Provide an external user avatar URL (optional)

    Returns:
        AttachmentPayload with the created attachment
    """
    import uuid

    session: Session = info.context["session"]

    try:
        # Extract required fields
        url = kwargs.get("url")
        issue_id = kwargs.get("issueId")

        # Validate required fields
        if not url:
            raise Exception("Field 'url' is required")
        if not issue_id:
            raise Exception("Field 'issueId' is required")

        # Verify the issue exists
        issue = session.query(Issue).filter_by(id=issue_id).first()
        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        # Check if attachment with same URL and issueId already exists
        existing_attachment = (
            session.query(Attachment)
            .filter(and_(Attachment.url == url, Attachment.issueId == issue_id))
            .first()
        )

        if existing_attachment:
            # Update existing attachment
            attachment = existing_attachment
            if kwargs.get("title"):
                attachment.title = kwargs["title"]
            attachment.updatedAt = datetime.utcnow()
        else:
            # Generate ID if not provided
            attachment_id = kwargs.get("id", str(uuid.uuid4()))

            # Build source metadata for GitHub
            source_metadata = {"type": "github", "url": url}

            # Build attachment data
            attachment_data = {
                "id": attachment_id,
                "issueId": issue_id,
                "url": url,
                "title": kwargs.get(
                    "title",
                    f"GitHub Issue: {url.split('/')[-1] if '/' in url else url}",
                ),
                "sourceType": "github",
                "source": source_metadata,
                "groupBySource": True,  # GitHub issues should be grouped
                "metadata_": {},
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }

            # Handle displayIconUrl
            if kwargs.get("displayIconUrl"):
                attachment_data["iconUrl"] = kwargs["displayIconUrl"]

            # Handle createAsUser - create or find ExternalUser
            create_as_user = kwargs.get("createAsUser")
            if create_as_user:
                # Find or create external user
                external_user = (
                    session.query(ExternalUser).filter_by(name=create_as_user).first()
                )

                if not external_user:
                    external_user = ExternalUser(
                        id=str(uuid.uuid4()),
                        name=create_as_user,
                        avatarUrl=kwargs.get("displayIconUrl"),
                        createdAt=datetime.utcnow(),
                        updatedAt=datetime.utcnow(),
                    )
                    session.add(external_user)
                    session.flush()  # Ensure external_user.id is available

                attachment_data["externalUserCreatorId"] = external_user.id

            # Create the attachment entity
            attachment = Attachment(**attachment_data)
            session.add(attachment)

        return attachment

    except Exception as e:
        raise Exception(f"Failed to link GitHub issue attachment: {str(e)}")


@mutation.field("attachmentLinkGitHubPR")
def resolve_attachmentLinkGitHubPR(obj, info, **kwargs):
    """
    Link a GitHub pull request to a Linear issue.

    Args:
        url: The URL of the GitHub pull request to link (required)
        issueId: The Linear issue for which to link the GitHub pull request (required)
        title: The title to use for the attachment (optional)
        id: Optional attachment ID that may be provided through the API (optional)
        createAsUser: Create attachment as a user with the provided name (optional)
        displayIconUrl: Provide an external user avatar URL (optional)
        linkKind: [Internal] The kind of link between the issue and the pull request (optional)
        number: The GitHub pull request number (deprecated, optional)
        owner: The owner of the GitHub repository (deprecated, optional)
        repo: The name of the GitHub repository (deprecated, optional)

    Returns:
        AttachmentPayload with the created attachment
    """
    import uuid

    session: Session = info.context["session"]

    try:
        # Extract required fields
        url = kwargs.get("url")
        issue_id = kwargs.get("issueId")

        # Validate required fields
        if not url:
            raise Exception("Field 'url' is required")
        if not issue_id:
            raise Exception("Field 'issueId' is required")

        # Verify the issue exists
        issue = session.query(Issue).filter_by(id=issue_id).first()
        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        # Check if attachment with same URL and issueId already exists
        existing_attachment = (
            session.query(Attachment)
            .filter(and_(Attachment.url == url, Attachment.issueId == issue_id))
            .first()
        )

        if existing_attachment:
            # Update existing attachment
            attachment = existing_attachment
            if kwargs.get("title"):
                attachment.title = kwargs["title"]
            attachment.updatedAt = datetime.utcnow()
        else:
            # Generate ID if not provided
            attachment_id = kwargs.get("id", str(uuid.uuid4()))

            # Build source metadata for GitHub PR
            source_metadata = {"type": "github", "url": url}

            # Add linkKind to source if provided
            link_kind = kwargs.get("linkKind")
            if link_kind:
                source_metadata["linkKind"] = link_kind

            # Add deprecated fields to source if provided (for backwards compatibility)
            if kwargs.get("number"):
                source_metadata["number"] = kwargs["number"]
            if kwargs.get("owner"):
                source_metadata["owner"] = kwargs["owner"]
            if kwargs.get("repo"):
                source_metadata["repo"] = kwargs["repo"]

            # Build attachment data
            attachment_data = {
                "id": attachment_id,
                "issueId": issue_id,
                "url": url,
                "title": kwargs.get(
                    "title", f"GitHub PR: {url.split('/')[-1] if '/' in url else url}"
                ),
                "sourceType": "github",
                "source": source_metadata,
                "groupBySource": True,  # GitHub PRs should be grouped
                "metadata_": {},
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }

            # Handle displayIconUrl
            if kwargs.get("displayIconUrl"):
                attachment_data["iconUrl"] = kwargs["displayIconUrl"]

            # Handle createAsUser - create or find ExternalUser
            create_as_user = kwargs.get("createAsUser")
            if create_as_user:
                # Find or create external user
                external_user = (
                    session.query(ExternalUser).filter_by(name=create_as_user).first()
                )

                if not external_user:
                    external_user = ExternalUser(
                        id=str(uuid.uuid4()),
                        name=create_as_user,
                        avatarUrl=kwargs.get("displayIconUrl"),
                        createdAt=datetime.utcnow(),
                        updatedAt=datetime.utcnow(),
                    )
                    session.add(external_user)
                    session.flush()  # Ensure external_user.id is available

                attachment_data["externalUserCreatorId"] = external_user.id

            # Create the attachment entity
            attachment = Attachment(**attachment_data)
            session.add(attachment)

        return attachment

    except Exception as e:
        raise Exception(f"Failed to link GitHub PR attachment: {str(e)}")


@mutation.field("attachmentLinkGitLabMR")
def resolve_attachmentLinkGitLabMR(obj, info, **kwargs):
    """
    Link a GitLab merge request to a Linear issue.

    Args:
        url: The URL of the GitLab merge request to link (required)
        issueId: The Linear issue for which to link the GitLab merge request (required)
        number: The GitLab merge request number to link (required)
        projectPathWithNamespace: The path name to the project including any (sub)groups (required)
        title: The title to use for the attachment (optional)
        id: Optional attachment ID that may be provided through the API (optional)
        createAsUser: Create attachment as a user with the provided name (optional)
        displayIconUrl: Provide an external user avatar URL (optional)

    Returns:
        AttachmentPayload with the created attachment
    """
    import uuid

    session: Session = info.context["session"]

    try:
        # Extract required fields
        url = kwargs.get("url")
        issue_id = kwargs.get("issueId")
        number = kwargs.get("number")
        project_path = kwargs.get("projectPathWithNamespace")

        # Validate required fields
        if not url:
            raise Exception("Field 'url' is required")
        if not issue_id:
            raise Exception("Field 'issueId' is required")
        if number is None:
            raise Exception("Field 'number' is required")
        if not project_path:
            raise Exception("Field 'projectPathWithNamespace' is required")

        # Verify the issue exists
        issue = session.query(Issue).filter_by(id=issue_id).first()
        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        # Check if attachment with same URL and issueId already exists
        existing_attachment = (
            session.query(Attachment)
            .filter(and_(Attachment.url == url, Attachment.issueId == issue_id))
            .first()
        )

        if existing_attachment:
            # Update existing attachment
            attachment = existing_attachment
            if kwargs.get("title"):
                attachment.title = kwargs["title"]
            attachment.updatedAt = datetime.utcnow()

            # Update source metadata with GitLab MR details
            if attachment.source:
                attachment.source["number"] = number
                attachment.source["projectPathWithNamespace"] = project_path
        else:
            # Generate ID if not provided
            attachment_id = kwargs.get("id", str(uuid.uuid4()))

            # Build source metadata for GitLab MR
            source_metadata = {
                "type": "gitlab",
                "url": url,
                "number": number,
                "projectPathWithNamespace": project_path,
            }

            # Build attachment data
            attachment_data = {
                "id": attachment_id,
                "issueId": issue_id,
                "url": url,
                "title": kwargs.get("title", f"GitLab MR !{number}"),
                "sourceType": "gitlab",
                "source": source_metadata,
                "groupBySource": True,  # GitLab MRs should be grouped
                "metadata_": {
                    "number": number,
                    "projectPathWithNamespace": project_path,
                },
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }

            # Handle displayIconUrl
            if kwargs.get("displayIconUrl"):
                attachment_data["iconUrl"] = kwargs["displayIconUrl"]

            # Handle createAsUser - create or find ExternalUser
            create_as_user = kwargs.get("createAsUser")
            if create_as_user:
                # Find or create external user
                external_user = (
                    session.query(ExternalUser).filter_by(name=create_as_user).first()
                )

                if not external_user:
                    external_user = ExternalUser(
                        id=str(uuid.uuid4()),
                        name=create_as_user,
                        avatarUrl=kwargs.get("displayIconUrl"),
                        createdAt=datetime.utcnow(),
                        updatedAt=datetime.utcnow(),
                    )
                    session.add(external_user)
                    session.flush()  # Ensure external_user.id is available

                attachment_data["externalUserCreatorId"] = external_user.id

            # Create the attachment entity
            attachment = Attachment(**attachment_data)
            session.add(attachment)

        return attachment

    except Exception as e:
        raise Exception(f"Failed to link GitLab MR attachment: {str(e)}")


@mutation.field("attachmentLinkIntercom")
def resolve_attachmentLinkIntercom(obj, info, **kwargs):
    """
    Link an existing Intercom conversation to an issue.

    Args:
        conversationId: The Intercom conversation ID to link (required)
        issueId: The issue for which to link the Intercom conversation (required)
        title: The title to use for the attachment (optional)
        partId: An optional Intercom conversation part ID to link to (optional)
        id: Optional attachment ID that may be provided through the API (optional)
        createAsUser: Create attachment as a user with the provided name (optional)
        displayIconUrl: Provide an external user avatar URL (optional)

    Returns:
        AttachmentPayload with the created attachment
    """
    import uuid

    session: Session = info.context["session"]

    try:
        # Extract required fields
        conversation_id = kwargs.get("conversationId")
        issue_id = kwargs.get("issueId")

        # Validate required fields
        if not conversation_id:
            raise Exception("Field 'conversationId' is required")
        if not issue_id:
            raise Exception("Field 'issueId' is required")

        # Verify the issue exists
        issue = session.query(Issue).filter_by(id=issue_id).first()
        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        # Generate a URL for the Intercom conversation
        # Intercom URLs follow the pattern: https://app.intercom.com/a/inbox/{workspace}/inbox/conversation/{conversationId}
        # For simplicity, we'll use a basic URL format
        url = f"https://app.intercom.com/conversations/{conversation_id}"

        # If partId is provided, append it to the URL
        part_id = kwargs.get("partId")
        if part_id:
            url = f"{url}#part-{part_id}"

        # Check if attachment with same conversation ID and issueId already exists
        existing_attachment = (
            session.query(Attachment)
            .filter(and_(Attachment.url == url, Attachment.issueId == issue_id))
            .first()
        )

        if existing_attachment:
            # Update existing attachment
            attachment = existing_attachment
            if kwargs.get("title"):
                attachment.title = kwargs["title"]
            attachment.updatedAt = datetime.utcnow()

            # Update source metadata with Intercom details if partId is provided
            if attachment.source and part_id:
                attachment.source["partId"] = part_id
        else:
            # Generate ID if not provided
            attachment_id = kwargs.get("id", str(uuid.uuid4()))

            # Build source metadata for Intercom
            source_metadata = {"type": "intercom", "conversationId": conversation_id}
            if part_id:
                source_metadata["partId"] = part_id

            # Build attachment data
            attachment_data = {
                "id": attachment_id,
                "issueId": issue_id,
                "url": url,
                "title": kwargs.get(
                    "title", f"Intercom conversation {conversation_id}"
                ),
                "sourceType": "intercom",
                "source": source_metadata,
                "groupBySource": True,  # Intercom conversations should be grouped
                "metadata_": {},
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }

            # Handle displayIconUrl
            if kwargs.get("displayIconUrl"):
                attachment_data["iconUrl"] = kwargs["displayIconUrl"]

            # Handle createAsUser - create or find ExternalUser
            create_as_user = kwargs.get("createAsUser")
            if create_as_user:
                # Find or create external user
                external_user = (
                    session.query(ExternalUser).filter_by(name=create_as_user).first()
                )

                if not external_user:
                    external_user = ExternalUser(
                        id=str(uuid.uuid4()),
                        name=create_as_user,
                        avatarUrl=kwargs.get("displayIconUrl"),
                        createdAt=datetime.utcnow(),
                        updatedAt=datetime.utcnow(),
                    )
                    session.add(external_user)
                    session.flush()  # Ensure external_user.id is available

                attachment_data["externalUserCreatorId"] = external_user.id

            # Create the attachment entity
            attachment = Attachment(**attachment_data)
            session.add(attachment)

        return attachment

    except Exception as e:
        raise Exception(f"Failed to link Intercom attachment: {str(e)}")


@mutation.field("attachmentLinkJiraIssue")
def resolve_attachmentLinkJiraIssue(obj, info, **kwargs):
    """
    Link an existing Jira issue to a Linear issue.

    Args:
        jiraIssueId: The Jira issue key or ID to link (required)
        issueId: The issue for which to link the Jira issue (required)
        title: The title to use for the attachment (optional)
        url: Optional fallback URL to use if the Jira issue cannot be found (optional)
        id: Optional attachment ID that may be provided through the API (optional)
        createAsUser: Create attachment as a user with the provided name (optional)
        displayIconUrl: Provide an external user avatar URL (optional)

    Returns:
        AttachmentPayload with the created attachment
    """
    import uuid

    session: Session = info.context["session"]

    try:
        # Extract required fields
        jira_issue_id = kwargs.get("jiraIssueId")
        issue_id = kwargs.get("issueId")

        # Validate required fields
        if not jira_issue_id:
            raise Exception("Field 'jiraIssueId' is required")
        if not issue_id:
            raise Exception("Field 'issueId' is required")

        # Verify the issue exists
        issue = session.query(Issue).filter_by(id=issue_id).first()
        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        # Generate a URL for the Jira issue
        # Use the provided URL fallback if available, otherwise construct a generic URL
        url = kwargs.get("url")
        if not url:
            # If no URL provided, create a placeholder URL using the Jira issue ID
            # In a real implementation, this might use the Jira workspace URL from organization settings
            url = f"https://jira.atlassian.com/browse/{jira_issue_id}"

        # Check if attachment with same Jira issue ID and issueId already exists
        # We check using the source metadata to identify Jira attachments
        existing_attachment = (
            session.query(Attachment)
            .filter(
                and_(Attachment.issueId == issue_id, Attachment.sourceType == "jira")
            )
            .all()
        )

        # Filter for matching jiraIssueId in source metadata
        matching_attachment = None
        for att in existing_attachment:
            if att.source and att.source.get("jiraIssueId") == jira_issue_id:
                matching_attachment = att
                break

        if matching_attachment:
            # Update existing attachment
            attachment = matching_attachment
            if kwargs.get("title"):
                attachment.title = kwargs["title"]
            if kwargs.get("url"):
                attachment.url = kwargs["url"]
            attachment.updatedAt = datetime.utcnow()
        else:
            # Generate ID if not provided
            attachment_id = kwargs.get("id", str(uuid.uuid4()))

            # Build source metadata for Jira
            source_metadata = {"type": "jira", "jiraIssueId": jira_issue_id}

            # Build attachment data
            attachment_data = {
                "id": attachment_id,
                "issueId": issue_id,
                "url": url,
                "title": kwargs.get("title", f"Jira Issue: {jira_issue_id}"),
                "sourceType": "jira",
                "source": source_metadata,
                "groupBySource": True,  # Jira issues should be grouped
                "metadata_": {},
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }

            # Handle displayIconUrl
            if kwargs.get("displayIconUrl"):
                attachment_data["iconUrl"] = kwargs["displayIconUrl"]

            # Handle createAsUser - create or find ExternalUser
            create_as_user = kwargs.get("createAsUser")
            if create_as_user:
                # Find or create external user
                external_user = (
                    session.query(ExternalUser).filter_by(name=create_as_user).first()
                )

                if not external_user:
                    external_user = ExternalUser(
                        id=str(uuid.uuid4()),
                        name=create_as_user,
                        avatarUrl=kwargs.get("displayIconUrl"),
                        createdAt=datetime.utcnow(),
                        updatedAt=datetime.utcnow(),
                    )
                    session.add(external_user)
                    session.flush()  # Ensure external_user.id is available

                attachment_data["externalUserCreatorId"] = external_user.id

            # Create the attachment entity
            attachment = Attachment(**attachment_data)
            session.add(attachment)

        return attachment

    except Exception as e:
        raise Exception(f"Failed to link Jira issue attachment: {str(e)}")


@mutation.field("attachmentLinkSalesforce")
def resolve_attachmentLinkSalesforce(obj, info, **kwargs):
    """
    Link an existing Salesforce case to an issue.

    Args:
        obj: The parent object (unused for mutations)
        info: GraphQL resolve info containing context
        **kwargs: Mutation arguments:
            - url: The URL of the Salesforce case to link (required)
            - issueId: The issue for which to link the Salesforce case (required)
            - title: The title to use for the attachment (optional)
            - id: Optional attachment ID that may be provided through the API
            - createAsUser: Create attachment as a user with the provided name (optional)
            - displayIconUrl: Provide an external user avatar URL (optional)

    Returns:
        The created Attachment entity
    """
    import uuid

    session: Session = info.context["session"]

    try:
        # Extract required fields
        url = kwargs.get("url")
        issue_id = kwargs.get("issueId")

        # Validate required fields
        if not url:
            raise Exception("Field 'url' is required")
        if not issue_id:
            raise Exception("Field 'issueId' is required")

        # Verify the issue exists
        issue = session.query(Issue).filter_by(id=issue_id).first()
        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        # Check if attachment with same URL and issueId already exists
        existing_attachment = (
            session.query(Attachment)
            .filter(and_(Attachment.url == url, Attachment.issueId == issue_id))
            .first()
        )

        if existing_attachment:
            # Update existing attachment
            attachment = existing_attachment
            if kwargs.get("title"):
                attachment.title = kwargs["title"]
            attachment.updatedAt = datetime.utcnow()
        else:
            # Generate ID if not provided
            attachment_id = kwargs.get("id", str(uuid.uuid4()))

            # Build source metadata for Salesforce
            source_metadata = {"type": "salesforce"}

            # Extract case ID from URL if possible (for better grouping)
            # Salesforce URLs typically have a case ID in the path
            # Example: https://domain.lightning.force.com/lightning/r/Case/5003000000XXXXX/view
            import re

            case_id_match = re.search(r"/Case/([a-zA-Z0-9]+)", url)
            if case_id_match:
                source_metadata["caseId"] = case_id_match.group(1)

            # Build attachment data
            attachment_data = {
                "id": attachment_id,
                "issueId": issue_id,
                "url": url,
                "title": kwargs.get("title", "Salesforce Case"),
                "sourceType": "salesforce",
                "source": source_metadata,
                "groupBySource": True,  # Salesforce cases should be grouped
                "metadata_": {},
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }

            # Handle displayIconUrl
            if kwargs.get("displayIconUrl"):
                attachment_data["iconUrl"] = kwargs["displayIconUrl"]

            # Handle createAsUser - create or find ExternalUser
            create_as_user = kwargs.get("createAsUser")
            if create_as_user:
                # Find or create external user
                external_user = (
                    session.query(ExternalUser).filter_by(name=create_as_user).first()
                )

                if not external_user:
                    external_user = ExternalUser(
                        id=str(uuid.uuid4()),
                        name=create_as_user,
                        avatarUrl=kwargs.get("displayIconUrl"),
                        createdAt=datetime.utcnow(),
                        updatedAt=datetime.utcnow(),
                    )
                    session.add(external_user)
                    session.flush()  # Ensure external_user.id is available

                attachment_data["externalUserCreatorId"] = external_user.id

            # Create the attachment entity
            attachment = Attachment(**attachment_data)
            session.add(attachment)

        return attachment

    except Exception as e:
        raise Exception(f"Failed to link Salesforce attachment: {str(e)}")


@mutation.field("attachmentLinkSlack")
def resolve_attachmentLinkSlack(obj, info, **kwargs):
    """
    Link an existing Slack message to an issue.

    Args:
        obj: The parent object (unused for mutations)
        info: GraphQL resolve info containing context
        **kwargs: Mutation arguments:
            - url: The Slack message URL for the message to link (required)
            - issueId: The issue to which to link the Slack message (required)
            - title: The title to use for the attachment (optional)
            - id: Optional attachment ID that may be provided through the API
            - createAsUser: Create attachment as a user with the provided name (optional)
            - displayIconUrl: Provide an external user avatar URL (optional)
            - syncToCommentThread: Whether to begin syncing the message's Slack thread with a comment thread on the issue (optional)
            - channel: [DEPRECATED] The Slack channel ID (ignored)
            - latest: [DEPRECATED] The latest timestamp (ignored)
            - ts: [DEPRECATED] Thread/message identifier (ignored)

    Returns:
        The created Attachment entity
    """
    import uuid

    session: Session = info.context["session"]

    try:
        # Extract required fields
        url = kwargs.get("url")
        issue_id = kwargs.get("issueId")

        # Validate required fields
        if not url:
            raise Exception("Field 'url' is required")
        if not issue_id:
            raise Exception("Field 'issueId' is required")

        # Verify the issue exists
        issue = session.query(Issue).filter_by(id=issue_id).first()
        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        # Check if attachment with same URL and issueId already exists
        existing_attachment = (
            session.query(Attachment)
            .filter(and_(Attachment.url == url, Attachment.issueId == issue_id))
            .first()
        )

        if existing_attachment:
            # Update existing attachment
            attachment = existing_attachment
            if kwargs.get("title"):
                attachment.title = kwargs["title"]
            attachment.updatedAt = datetime.utcnow()
        else:
            # Generate ID if not provided
            attachment_id = kwargs.get("id", str(uuid.uuid4()))

            # Build source metadata for Slack
            source_metadata = {"type": "slack"}

            # Extract workspace and message info from URL if possible
            # Slack URLs typically look like: https://workspace.slack.com/archives/CHANNEL_ID/pTIMESTAMP
            import re

            workspace_match = re.search(r"https://([^.]+)\.slack\.com", url)
            if workspace_match:
                source_metadata["workspace"] = workspace_match.group(1)

            channel_match = re.search(r"/archives/([^/]+)", url)
            if channel_match:
                source_metadata["channelId"] = channel_match.group(1)

            message_match = re.search(r"/p(\d+)", url)
            if message_match:
                source_metadata["messageTs"] = message_match.group(1)

            # Add syncToCommentThread flag if provided
            if kwargs.get("syncToCommentThread") is not None:
                source_metadata["syncToCommentThread"] = kwargs["syncToCommentThread"]

            # Build attachment data
            attachment_data = {
                "id": attachment_id,
                "issueId": issue_id,
                "url": url,
                "title": kwargs.get("title", "Slack Message"),
                "sourceType": "slack",
                "source": source_metadata,
                "groupBySource": True,  # Slack messages should be grouped
                "metadata_": {},
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }

            # Handle displayIconUrl
            if kwargs.get("displayIconUrl"):
                attachment_data["iconUrl"] = kwargs["displayIconUrl"]

            # Handle createAsUser - create or find ExternalUser
            create_as_user = kwargs.get("createAsUser")
            if create_as_user:
                # Find or create external user
                external_user = (
                    session.query(ExternalUser).filter_by(name=create_as_user).first()
                )

                if not external_user:
                    external_user = ExternalUser(
                        id=str(uuid.uuid4()),
                        name=create_as_user,
                        avatarUrl=kwargs.get("displayIconUrl"),
                        createdAt=datetime.utcnow(),
                        updatedAt=datetime.utcnow(),
                    )
                    session.add(external_user)
                    session.flush()  # Ensure external_user.id is available

                attachment_data["externalUserCreatorId"] = external_user.id

            # Create the attachment entity
            attachment = Attachment(**attachment_data)
            session.add(attachment)

        return attachment

    except Exception as e:
        raise Exception(f"Failed to link Slack attachment: {str(e)}")


@mutation.field("attachmentLinkURL")
def resolve_attachmentLinkURL(obj, info, **kwargs):
    """
    Link any url to an issue.

    Args:
        obj: The parent object (unused for mutations)
        info: GraphQL resolve info containing context
        **kwargs: Mutation arguments:
            - url: The url to link (required)
            - issueId: The issue for which to link the url (required)
            - title: The title to use for the attachment (optional)
            - id: The id for the attachment (optional)
            - createAsUser: Create attachment as a user with the provided name (optional)
            - displayIconUrl: Provide an external user avatar URL (optional)

    Returns:
        The created Attachment entity
    """
    import uuid

    session: Session = info.context["session"]

    try:
        # Extract required fields
        url = kwargs.get("url")
        issue_id = kwargs.get("issueId")

        # Validate required fields
        if not url:
            raise Exception("Field 'url' is required")
        if not issue_id:
            raise Exception("Field 'issueId' is required")

        # Verify the issue exists
        issue = session.query(Issue).filter_by(id=issue_id).first()
        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        # Check if attachment with same URL and issueId already exists
        existing_attachment = (
            session.query(Attachment)
            .filter(and_(Attachment.url == url, Attachment.issueId == issue_id))
            .first()
        )

        if existing_attachment:
            # Update existing attachment
            attachment = existing_attachment
            if kwargs.get("title"):
                attachment.title = kwargs["title"]
            attachment.updatedAt = datetime.utcnow()
        else:
            # Generate ID if not provided
            attachment_id = kwargs.get("id", str(uuid.uuid4()))

            # Build source metadata for generic URL
            source_metadata = {"type": "url"}

            # Build attachment data
            attachment_data = {
                "id": attachment_id,
                "issueId": issue_id,
                "url": url,
                "title": kwargs.get(
                    "title", url
                ),  # Default to URL if no title provided
                "sourceType": "url",
                "source": source_metadata,
                "groupBySource": False,  # Generic URLs are not grouped
                "metadata_": {},
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }

            # Handle displayIconUrl
            if kwargs.get("displayIconUrl"):
                attachment_data["iconUrl"] = kwargs["displayIconUrl"]

            # Handle createAsUser - create or find ExternalUser
            create_as_user = kwargs.get("createAsUser")
            if create_as_user:
                # Find or create external user
                external_user = (
                    session.query(ExternalUser).filter_by(name=create_as_user).first()
                )

                if not external_user:
                    external_user = ExternalUser(
                        id=str(uuid.uuid4()),
                        name=create_as_user,
                        avatarUrl=kwargs.get("displayIconUrl"),
                        createdAt=datetime.utcnow(),
                        updatedAt=datetime.utcnow(),
                    )
                    session.add(external_user)
                    session.flush()  # Ensure external_user.id is available

                attachment_data["externalUserCreatorId"] = external_user.id

            # Create the attachment entity
            attachment = Attachment(**attachment_data)
            session.add(attachment)

        return attachment

    except Exception as e:
        raise Exception(f"Failed to link URL attachment: {str(e)}")


@mutation.field("attachmentLinkZendesk")
def resolve_attachmentLinkZendesk(obj, info, **kwargs):
    """
    Link an existing Zendesk ticket to an issue.

    Args:
        ticketId: The Zendesk ticket ID to link (required)
        issueId: The issue for which to link the Zendesk ticket (required)
        url: The URL of the Zendesk ticket to link (optional)
        title: The title to use for the attachment (optional)
        id: Optional attachment ID that may be provided through the API (optional)
        createAsUser: Create attachment as a user with the provided name (optional)
        displayIconUrl: Provide an external user avatar URL (optional)

    Returns:
        AttachmentPayload with the created attachment
    """
    import uuid

    session: Session = info.context["session"]

    try:
        # Extract required fields
        ticket_id = kwargs.get("ticketId")
        issue_id = kwargs.get("issueId")

        # Validate required fields
        if not ticket_id:
            raise Exception("Field 'ticketId' is required")
        if not issue_id:
            raise Exception("Field 'issueId' is required")

        # Verify the issue exists
        issue = session.query(Issue).filter_by(id=issue_id).first()
        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        # Generate a URL for the Zendesk ticket
        # Use the provided URL if available, otherwise construct a generic URL
        url = kwargs.get("url")
        if not url:
            # If no URL provided, create a placeholder URL using the ticket ID
            # In a real implementation, this might use the Zendesk workspace URL from organization settings
            url = f"https://support.zendesk.com/hc/tickets/{ticket_id}"

        # Check if attachment with same Zendesk ticket ID and issueId already exists
        # We check using the source metadata to identify Zendesk attachments
        existing_attachment = (
            session.query(Attachment)
            .filter(
                and_(Attachment.issueId == issue_id, Attachment.sourceType == "zendesk")
            )
            .all()
        )

        # Filter for matching ticketId in source metadata
        matching_attachment = None
        for att in existing_attachment:
            if att.source and att.source.get("ticketId") == ticket_id:
                matching_attachment = att
                break

        if matching_attachment:
            # Update existing attachment
            attachment = matching_attachment
            if kwargs.get("title"):
                attachment.title = kwargs["title"]
            if kwargs.get("url"):
                attachment.url = kwargs["url"]
            attachment.updatedAt = datetime.utcnow()
        else:
            # Generate ID if not provided
            attachment_id = kwargs.get("id", str(uuid.uuid4()))

            # Build source metadata for Zendesk
            source_metadata = {"type": "zendesk", "ticketId": ticket_id}

            # Build attachment data
            attachment_data = {
                "id": attachment_id,
                "issueId": issue_id,
                "url": url,
                "title": kwargs.get("title", f"Zendesk Ticket: {ticket_id}"),
                "sourceType": "zendesk",
                "source": source_metadata,
                "groupBySource": True,  # Zendesk tickets should be grouped
                "metadata_": {},
                "createdAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow(),
            }

            # Handle displayIconUrl
            if kwargs.get("displayIconUrl"):
                attachment_data["iconUrl"] = kwargs["displayIconUrl"]

            # Handle createAsUser - create or find ExternalUser
            create_as_user = kwargs.get("createAsUser")
            if create_as_user:
                # Find or create external user
                external_user = (
                    session.query(ExternalUser).filter_by(name=create_as_user).first()
                )

                if not external_user:
                    external_user = ExternalUser(
                        id=str(uuid.uuid4()),
                        name=create_as_user,
                        avatarUrl=kwargs.get("displayIconUrl"),
                        createdAt=datetime.utcnow(),
                        updatedAt=datetime.utcnow(),
                    )
                    session.add(external_user)
                    session.flush()  # Ensure external_user.id is available

                attachment_data["externalUserCreatorId"] = external_user.id

            # Create the attachment entity
            attachment = Attachment(**attachment_data)
            session.add(attachment)

        return attachment

    except Exception as e:
        raise Exception(f"Failed to link Zendesk ticket attachment: {str(e)}")


@mutation.field("attachmentSyncToSlack")
def resolve_attachmentSyncToSlack(obj, info, **kwargs):
    """
    Begin syncing the thread for an existing Slack message attachment with a comment thread on its issue.

    Args:
        obj: The parent object (unused for mutations)
        info: GraphQL resolve info containing context
        **kwargs: Mutation arguments:
            - id: The ID of the Slack attachment to begin syncing (required)

    Returns:
        The updated Attachment entity
    """

    session: Session = info.context["session"]

    try:
        # Extract required field
        attachment_id = kwargs.get("id")

        # Validate required field
        if not attachment_id:
            raise Exception("Field 'id' is required")

        # Fetch the attachment
        attachment = session.query(Attachment).filter_by(id=attachment_id).first()
        if not attachment:
            raise Exception(f"Attachment with id {attachment_id} not found")

        # Verify this is a Slack attachment
        if attachment.sourceType != "slack":
            raise Exception(
                f"Attachment {attachment_id} is not a Slack attachment (sourceType: {attachment.sourceType})"
            )

        # Update the source metadata to enable thread syncing
        # This sets a flag in the source metadata to indicate that thread syncing should be enabled
        source_metadata = attachment.source or {}
        source_metadata["syncToCommentThread"] = True
        attachment.source = source_metadata

        # Update the timestamp
        attachment.updatedAt = datetime.utcnow()

        return attachment

    except Exception as e:
        raise Exception(f"Failed to sync Slack attachment to thread: {str(e)}")


@mutation.field("attachmentUpdate")
def resolve_attachmentUpdate(obj, info, **kwargs):
    """
    Updates an existing issue attachment.

    Args:
        obj: The parent object (unused for mutations)
        info: GraphQL resolve info containing context
        **kwargs: Mutation arguments:
            - id: The identifier of the attachment to update (required)
            - input: A partial attachment object to update the attachment with (required)
                - title: The attachment title (required in input)
                - subtitle: The attachment subtitle (optional)
                - iconUrl: An icon url to display with the attachment (optional)
                - metadata: Attachment metadata object with string and number values (optional)

    Returns:
        The updated Attachment entity
    """

    session: Session = info.context["session"]

    try:
        # Extract required fields
        attachment_id = kwargs.get("id")
        input_data = kwargs.get("input")

        # Validate required fields
        if not attachment_id:
            raise Exception("Field 'id' is required")
        if not input_data:
            raise Exception("Field 'input' is required")

        # Fetch the attachment
        attachment = session.query(Attachment).filter_by(id=attachment_id).first()
        if not attachment:
            raise Exception(f"Attachment with id {attachment_id} not found")

        # Update title (required in input)
        if "title" not in input_data:
            raise Exception("Field 'title' is required in input")
        attachment.title = input_data["title"]

        # Update optional fields if provided
        if "subtitle" in input_data:
            attachment.subtitle = input_data["subtitle"]

        if "iconUrl" in input_data:
            attachment.iconUrl = input_data["iconUrl"]

        if "metadata" in input_data:
            attachment.metadata_ = input_data["metadata"]

        # Update the timestamp
        attachment.updatedAt = datetime.utcnow()

        return attachment

    except Exception as e:
        raise Exception(f"Failed to update attachment: {str(e)}")


# ============================================================================
# Cycle Mutations
# ============================================================================


@mutation.field("cycleCreate")
def resolve_cycleCreate(obj, info, **kwargs):
    """
    Creates a new cycle.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'input' (CycleCreateInput)

    Returns:
        Dict containing CyclePayload with entity
    """
    import uuid

    session: Session = info.context["session"]
    input_data = kwargs.get("input", {})

    try:
        # Extract required fields
        ends_at = input_data.get("endsAt")
        starts_at = input_data.get("startsAt")
        team_id = input_data.get("teamId")

        if not all([ends_at, starts_at, team_id]):
            raise Exception(
                "Missing required fields: endsAt, startsAt, and teamId are required"
            )

        # Verify the team exists
        team = session.query(Team).filter_by(id=team_id).first()
        if not team:
            raise Exception(f"Team with id {team_id} not found")

        # Generate ID if not provided
        cycle_id = input_data.get("id", str(uuid.uuid4()))

        # Get the next cycle number for the team
        max_number_result = (
            session.query(Cycle)
            .filter_by(teamId=team_id)
            .order_by(Cycle.number.desc())
            .first()
        )
        next_number = (max_number_result.number + 1) if max_number_result else 1.0

        # Determine if the cycle is active, future, or past
        now = datetime.now(timezone.utc)
        is_active = starts_at <= now <= ends_at
        is_future = starts_at > now
        is_past = ends_at < now

        # Create the new cycle
        new_cycle = Cycle(
            id=cycle_id,
            teamId=team_id,
            endsAt=ends_at,
            startsAt=starts_at,
            completedAt=input_data.get("completedAt"),
            description=input_data.get("description"),
            name=input_data.get("name"),
            # Set required fields with defaults
            createdAt=now,
            updatedAt=now,
            number=next_number,
            isActive=is_active,
            isFuture=is_future,
            isPast=is_past,
            isNext=False,  # This would require more complex logic to determine
            isPrevious=False,  # This would require more complex logic to determine
            progress=0.0,
            # Initialize empty history arrays
            completedIssueCountHistory=[],
            completedScopeHistory=[],
            inProgressScopeHistory=[],
            issueCountHistory=[],
            scopeHistory=[],
            # Initialize empty JSON objects
            currentProgress={},
            progressHistory={},
        )

        session.add(new_cycle)

        return new_cycle

    except Exception as e:
        raise Exception(f"Failed to create cycle: {str(e)}")


@mutation.field("cycleArchive")
def resolve_cycleArchive(obj, info, **kwargs):
    """
    Archives a cycle.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (cycle ID to archive)

    Returns:
        Dict containing CycleArchivePayload with entity, success, and lastSyncId
    """

    session: Session = info.context["session"]
    cycle_id = kwargs.get("id")

    try:
        # Fetch the cycle to archive
        cycle = session.query(Cycle).filter_by(id=cycle_id).first()

        if not cycle:
            raise Exception(f"Cycle with id {cycle_id} not found")

        # Soft delete by setting archivedAt timestamp
        cycle.archivedAt = datetime.now(timezone.utc)
        cycle.updatedAt = datetime.now(timezone.utc)

        # Return CycleArchivePayload structure
        return {
            "entity": cycle,
            "success": True,
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
        }

    except Exception as e:
        raise Exception(f"Failed to archive cycle: {str(e)}")


@mutation.field("cycleShiftAll")
def resolve_cycleShiftAll(obj, info, **kwargs):
    """
    Shifts all cycles starts and ends by a certain number of days,
    starting from the provided cycle onwards.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'input' (CycleShiftAllInput) with:
            - id: String! - The cycle ID at which to start the shift
            - daysToShift: Float! - The number of days to shift the cycles by

    Returns:
        The updated cycle entity (CyclePayload)
    """

    session: Session = info.context["session"]
    input_data = kwargs.get("input", {})

    try:
        # Extract required fields
        cycle_id = input_data.get("id")
        days_to_shift = input_data.get("daysToShift")

        if cycle_id is None or days_to_shift is None:
            raise Exception("Missing required fields: id and daysToShift are required")

        # Fetch the starting cycle
        starting_cycle = session.query(Cycle).filter_by(id=cycle_id).first()

        if not starting_cycle:
            raise Exception(f"Cycle with id {cycle_id} not found")

        # Get all cycles for the same team that start at or after the starting cycle
        cycles_to_shift = (
            session.query(Cycle)
            .filter(
                Cycle.teamId == starting_cycle.teamId,
                Cycle.startsAt >= starting_cycle.startsAt,
            )
            .order_by(Cycle.startsAt)
            .all()
        )

        # Shift each cycle by the specified number of days
        shift_delta = timedelta(days=days_to_shift)
        now = datetime.now(timezone.utc)

        for cycle in cycles_to_shift:
            cycle.startsAt = cycle.startsAt + shift_delta
            cycle.endsAt = cycle.endsAt + shift_delta
            cycle.updatedAt = now

        return starting_cycle

    except Exception as e:
        raise Exception(f"Failed to shift cycles: {str(e)}")


@mutation.field("cycleStartUpcomingCycleToday")
def resolve_cycleStartUpcomingCycleToday(obj, info, **kwargs):
    """
    Shifts the upcoming cycle to start at midnight today, and shifts all
    subsequent cycles by the same amount.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains:
            - id: String! - The identifier of the upcoming cycle to start today

    Returns:
        The updated cycle entity (CyclePayload)
    """

    session: Session = info.context["session"]
    cycle_id = kwargs.get("id")

    try:
        if not cycle_id:
            raise Exception("Missing required field: id is required")

        # Fetch the upcoming cycle
        upcoming_cycle = session.query(Cycle).filter_by(id=cycle_id).first()

        if not upcoming_cycle:
            raise Exception(f"Cycle with id {cycle_id} not found")

        # Calculate midnight today in UTC
        now = datetime.now(timezone.utc)
        midnight_today = datetime(
            now.year, now.month, now.day, 0, 0, 0, tzinfo=timezone.utc
        )

        # Calculate the number of days to shift
        # This is the difference between midnight today and the current start time
        days_to_shift = (
            midnight_today - upcoming_cycle.startsAt
        ).total_seconds() / 86400

        # Get all cycles for the same team that start at or after the upcoming cycle
        cycles_to_shift = (
            session.query(Cycle)
            .filter(
                Cycle.teamId == upcoming_cycle.teamId,
                Cycle.startsAt >= upcoming_cycle.startsAt,
            )
            .order_by(Cycle.startsAt)
            .all()
        )

        # Shift each cycle by the calculated number of days
        shift_delta = timedelta(days=days_to_shift)

        for cycle in cycles_to_shift:
            cycle.startsAt = cycle.startsAt + shift_delta
            cycle.endsAt = cycle.endsAt + shift_delta
            cycle.updatedAt = now

        return upcoming_cycle

    except Exception as e:
        raise Exception(f"Failed to start upcoming cycle today: {str(e)}")


@mutation.field("cycleUpdate")
def resolve_cycleUpdate(obj, info, **kwargs):
    """
    Updates a cycle.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains:
            - id: String! - The identifier of the cycle to update
            - input: CycleUpdateInput! - A partial cycle object to update the cycle with

    Returns:
        The updated cycle entity (CyclePayload)
    """

    session: Session = info.context["session"]
    cycle_id = kwargs.get("id")
    input_data = kwargs.get("input")

    try:
        # Validate required arguments
        if not cycle_id:
            raise Exception("Missing required field: id is required")

        if not input_data:
            raise Exception("Missing required field: input is required")

        # Fetch the cycle to update
        cycle = session.query(Cycle).filter_by(id=cycle_id).first()

        if not cycle:
            raise Exception(f"Cycle with id {cycle_id} not found")

        # Update fields from input (all fields are optional in CycleUpdateInput)
        if "completedAt" in input_data:
            cycle.completedAt = input_data["completedAt"]

        if "description" in input_data:
            cycle.description = input_data["description"]

        if "endsAt" in input_data:
            cycle.endsAt = input_data["endsAt"]

        if "name" in input_data:
            cycle.name = input_data["name"]

        if "startsAt" in input_data:
            cycle.startsAt = input_data["startsAt"]

        # Update the updatedAt timestamp
        cycle.updatedAt = datetime.now(timezone.utc)

        return cycle

    except Exception as e:
        raise Exception(f"Failed to update cycle: {str(e)}")


# ============================================================================
# Document Mutations
# ============================================================================


@mutation.field("documentCreate")
def resolve_documentCreate(obj, info, **kwargs):
    """
    Creates a new document.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'input' with DocumentCreateInput data

    Returns:
        Document entity
    """
    import uuid

    session: Session = info.context["session"]
    input_data = kwargs.get("input", {})

    try:
        # Extract input fields
        document_id = input_data.get("id") or str(uuid.uuid4())
        title = input_data["title"]  # Required field
        color = input_data.get("color")
        content = input_data.get("content")
        content_data = input_data.get("contentData")
        icon = input_data.get("icon")
        initiative_id = input_data.get("initiativeId")
        last_applied_template_id = input_data.get("lastAppliedTemplateId")
        project_id = input_data.get("projectId")
        resource_folder_id = input_data.get("resourceFolderId")
        sort_order = input_data.get("sortOrder", 0.0)
        team_id = input_data.get("teamId")

        # Generate timestamps
        now = datetime.now(timezone.utc)

        # Generate slugId (simplified - in production this would be based on title)
        slug_id = str(uuid.uuid4())[:8]

        # Generate URL
        url = f"https://linear.app/document/{slug_id}"

        # Create the Document entity
        document = Document(
            id=document_id,
            title=title,
            color=color,
            content=content,
            contentState=content_data,  # contentData maps to contentState in ORM
            icon=icon,
            initiativeId=initiative_id,
            lastAppliedTemplateId=last_applied_template_id,
            projectId=project_id,
            resourceFolderId=resource_folder_id,
            sortOrder=sort_order,
            teamId=team_id,
            slugId=slug_id,
            url=url,
            createdAt=now,
            updatedAt=now,
            trashed=False,
        )

        # Handle subscribers if provided
        subscriber_ids = input_data.get("subscriberIds", [])
        if subscriber_ids:
            # Fetch subscriber users
            subscribers = session.query(User).filter(User.id.in_(subscriber_ids)).all()
            document.subscribers = subscribers

        session.add(document)

        return document

    except Exception as e:
        raise Exception(f"Failed to create document: {str(e)}")


@mutation.field("documentUpdate")
def resolve_documentUpdate(obj, info, **kwargs):
    """
    Updates an existing document.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (document ID) and 'input' with DocumentUpdateInput data

    Returns:
        Document entity
    """

    session: Session = info.context["session"]
    document_id = kwargs.get("id")
    input_data = kwargs.get("input", {})

    try:
        # Fetch the document to update
        document = session.query(Document).filter_by(id=document_id).first()

        if not document:
            raise Exception(f"Document with id {document_id} not found")

        # Update fields if provided in input
        if "color" in input_data:
            document.color = input_data["color"]

        if "content" in input_data:
            document.content = input_data["content"]

        if "contentData" in input_data:
            document.contentState = input_data["contentData"]

        if "hiddenAt" in input_data:
            document.hiddenAt = input_data["hiddenAt"]

        if "icon" in input_data:
            document.icon = input_data["icon"]

        if "initiativeId" in input_data:
            document.initiativeId = input_data["initiativeId"]

        if "lastAppliedTemplateId" in input_data:
            document.lastAppliedTemplateId = input_data["lastAppliedTemplateId"]

        if "projectId" in input_data:
            document.projectId = input_data["projectId"]

        if "resourceFolderId" in input_data:
            document.resourceFolderId = input_data["resourceFolderId"]

        if "sortOrder" in input_data:
            document.sortOrder = input_data["sortOrder"]

        if "teamId" in input_data:
            document.teamId = input_data["teamId"]

        if "title" in input_data:
            document.title = input_data["title"]

        if "trashed" in input_data:
            document.trashed = input_data["trashed"]

        # Handle subscribers if provided
        if "subscriberIds" in input_data:
            subscriber_ids = input_data["subscriberIds"]
            # Fetch subscriber users
            subscribers = session.query(User).filter(User.id.in_(subscriber_ids)).all()
            document.subscribers = subscribers

        # Update the updatedAt timestamp
        document.updatedAt = datetime.now(timezone.utc)

        return document

    except Exception as e:
        raise Exception(f"Failed to update document: {str(e)}")


@mutation.field("documentDelete")
def resolve_documentDelete(obj, info, **kwargs):
    """
    Deletes (trashes) a document.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (document ID to delete)

    Returns:
        Dict containing DocumentArchivePayload with entity, success, and lastSyncId
    """

    session: Session = info.context["session"]
    document_id = kwargs.get("id")

    try:
        # Fetch the document to delete
        document = session.query(Document).filter_by(id=document_id).first()

        if not document:
            raise Exception(f"Document with id {document_id} not found")

        # Soft delete by setting archivedAt timestamp
        document.archivedAt = datetime.now(timezone.utc)
        document.updatedAt = datetime.now(timezone.utc)

        # Return DocumentArchivePayload structure
        return {
            "entity": document,
            "success": True,
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
        }

    except Exception as e:
        raise Exception(f"Failed to delete document: {str(e)}")


@mutation.field("documentUnarchive")
def resolve_documentUnarchive(obj, info, **kwargs):
    """
    Restores a document by clearing its archivedAt timestamp.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (document ID to restore)

    Returns:
        Dict containing DocumentArchivePayload with entity, success, and lastSyncId
    """

    session: Session = info.context["session"]
    document_id = kwargs.get("id")

    try:
        # Fetch the document to restore
        document = session.query(Document).filter_by(id=document_id).first()

        if not document:
            raise Exception(f"Document with id {document_id} not found")

        # Restore by clearing archivedAt timestamp
        document.archivedAt = None
        document.updatedAt = datetime.now(timezone.utc)

        # Return DocumentArchivePayload structure
        return {
            "entity": document,
            "success": True,
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
        }

    except Exception as e:
        raise Exception(f"Failed to unarchive document: {str(e)}")


@mutation.field("initiativeCreate")
def resolve_initiativeCreate(obj, info, **kwargs):
    """
    Creates a new initiative.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'input' (InitiativeCreateInput)

    Returns:
        Dict containing InitiativePayload with initiative, success, and lastSyncId
    """
    import uuid

    session: Session = info.context["session"]
    input_data = kwargs.get("input", {})

    try:
        # Generate ID if not provided
        initiative_id = input_data.get("id") or str(uuid.uuid4())

        # Validate required fields
        if not input_data.get("name"):
            raise Exception("Initiative name is required")

        # Get current timestamp
        now = datetime.now(timezone.utc)

        # Create the initiative with required fields
        initiative = Initiative(
            id=initiative_id,
            name=input_data["name"],
            createdAt=now,
            updatedAt=now,
            # Optional fields from input
            color=input_data.get("color"),
            content=input_data.get("content"),
            description=input_data.get("description"),
            icon=input_data.get("icon"),
            ownerId=input_data.get("ownerId"),
            sortOrder=input_data.get("sortOrder", 0.0),
            status=input_data.get("status", "Planned"),
            targetDate=input_data.get("targetDate"),
            targetDateResolution=input_data.get("targetDateResolution"),
            # Required fields with defaults
            slugId=f"initiative-{initiative_id[:8]}",  # Generate a slug
            frequencyResolution="Weekly",  # Default frequency resolution
            url=f"/initiative/{initiative_id}",  # Generate URL
            trashed=False,
        )

        session.add(initiative)

        # Return InitiativePayload structure
        return {
            "initiative": initiative,
            "success": True,
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
        }

    except Exception as e:
        raise Exception(f"Failed to create initiative: {str(e)}")


@mutation.field("initiativeUpdate")
def resolve_initiativeUpdate(obj, info, **kwargs):
    """
    Updates an existing initiative.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (initiative ID) and 'input' (InitiativeUpdateInput)

    Returns:
        Dict containing InitiativePayload with initiative, success, and lastSyncId
    """

    session: Session = info.context["session"]
    initiative_id = kwargs.get("id")
    input_data = kwargs.get("input", {})

    try:
        # Fetch the initiative to update
        initiative = session.query(Initiative).filter_by(id=initiative_id).first()

        if not initiative:
            raise Exception(f"Initiative with id {initiative_id} not found")

        # Update fields from input - only update fields that are provided
        if "color" in input_data:
            initiative.color = input_data["color"]
        if "content" in input_data:
            initiative.content = input_data["content"]
        if "description" in input_data:
            initiative.description = input_data["description"]
        if "frequencyResolution" in input_data:
            initiative.frequencyResolution = input_data["frequencyResolution"]
        if "icon" in input_data:
            initiative.icon = input_data["icon"]
        if "name" in input_data:
            initiative.name = input_data["name"]
        if "ownerId" in input_data:
            initiative.ownerId = input_data["ownerId"]
        if "sortOrder" in input_data:
            initiative.sortOrder = input_data["sortOrder"]
        if "status" in input_data:
            initiative.status = input_data["status"]
        if "targetDate" in input_data:
            initiative.targetDate = input_data["targetDate"]
        if "targetDateResolution" in input_data:
            initiative.targetDateResolution = input_data["targetDateResolution"]
        if "trashed" in input_data:
            initiative.trashed = input_data["trashed"]
        if "updateReminderFrequency" in input_data:
            initiative.updateReminderFrequency = input_data["updateReminderFrequency"]
        if "updateReminderFrequencyInWeeks" in input_data:
            initiative.updateReminderFrequencyInWeeks = input_data[
                "updateReminderFrequencyInWeeks"
            ]
        if "updateRemindersDay" in input_data:
            initiative.updateRemindersDay = input_data["updateRemindersDay"]
        if "updateRemindersHour" in input_data:
            initiative.updateRemindersHour = input_data["updateRemindersHour"]

        # Update the updatedAt timestamp
        initiative.updatedAt = datetime.now(timezone.utc)

        # Return InitiativePayload structure
        return {
            "initiative": initiative,
            "success": True,
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
        }

    except Exception as e:
        raise Exception(f"Failed to update initiative: {str(e)}")


@mutation.field("initiativeArchive")
def resolve_initiativeArchive(obj, info, **kwargs):
    """
    Archives an initiative by setting its archivedAt timestamp.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (initiative ID to archive)

    Returns:
        Dict containing InitiativeArchivePayload with entity, success, and lastSyncId
    """

    session: Session = info.context["session"]
    initiative_id = kwargs.get("id")

    try:
        # Fetch the initiative to archive
        initiative = session.query(Initiative).filter_by(id=initiative_id).first()

        if not initiative:
            raise Exception(f"Initiative with id {initiative_id} not found")

        # Archive by setting archivedAt timestamp
        initiative.archivedAt = datetime.now(timezone.utc)
        initiative.updatedAt = datetime.now(timezone.utc)

        # Return InitiativeArchivePayload structure
        return {
            "entity": initiative,
            "success": True,
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
        }

    except Exception as e:
        raise Exception(f"Failed to archive initiative: {str(e)}")


@mutation.field("initiativeUnarchive")
def resolve_initiativeUnarchive(obj, info, **kwargs):
    """
    Unarchives an initiative by clearing its archivedAt timestamp.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (initiative ID to unarchive)

    Returns:
        Dict containing InitiativeArchivePayload with entity, success, and lastSyncId
    """

    session: Session = info.context["session"]
    initiative_id = kwargs.get("id")

    try:
        # Fetch the initiative to unarchive
        initiative = session.query(Initiative).filter_by(id=initiative_id).first()

        if not initiative:
            raise Exception(f"Initiative with id {initiative_id} not found")

        # Unarchive by clearing archivedAt timestamp
        initiative.archivedAt = None
        initiative.updatedAt = datetime.now(timezone.utc)

        # Return InitiativeArchivePayload structure
        return {
            "entity": initiative,
            "success": True,
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
        }

    except Exception as e:
        raise Exception(f"Failed to unarchive initiative: {str(e)}")


@mutation.field("initiativeDelete")
def resolve_initiativeDelete(obj, info, **kwargs):
    """
    Deletes (trashes) an initiative by setting its trashed flag.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (initiative ID to delete)

    Returns:
        Dict containing DeletePayload with entityId, success, and lastSyncId
    """

    session: Session = info.context["session"]
    initiative_id = kwargs.get("id")

    try:
        # Fetch the initiative to delete
        initiative = session.query(Initiative).filter_by(id=initiative_id).first()

        if not initiative:
            raise Exception(f"Initiative with id {initiative_id} not found")

        # Soft delete by setting trashed flag and archivedAt timestamp
        initiative.trashed = True
        initiative.archivedAt = datetime.now(timezone.utc)
        initiative.updatedAt = datetime.now(timezone.utc)

        # Return DeletePayload structure
        return {
            "entityId": initiative_id,
            "success": True,
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
        }

    except Exception as e:
        raise Exception(f"Failed to delete initiative: {str(e)}")


# InitiativeRelation mutation resolvers


@mutation.field("initiativeRelationCreate")
def resolve_initiativeRelationCreate(obj, info, **kwargs):
    """
    Creates a new initiative relation representing a dependency between two initiatives.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'input' (InitiativeRelationCreateInput)

    Returns:
        Dict containing InitiativeRelationPayload with the created entity, success, and lastSyncId
    """
    import uuid

    session: Session = info.context["session"]
    input_data = kwargs.get("input")

    if not input_data:
        raise Exception("Input data is required")

    try:
        # Generate ID if not provided
        entity_id = input_data.get("id", str(uuid.uuid4()))

        # Extract required fields
        initiative_id = input_data.get("initiativeId")
        related_initiative_id = input_data.get("relatedInitiativeId")

        if not initiative_id:
            raise Exception("initiativeId is required")
        if not related_initiative_id:
            raise Exception("relatedInitiativeId is required")

        # Extract optional fields
        sort_order = input_data.get("sortOrder", 0.0)

        # Verify that both initiatives exist
        initiative = session.query(Initiative).filter_by(id=initiative_id).first()
        if not initiative:
            raise Exception(f"Initiative with id {initiative_id} not found")

        related_initiative = (
            session.query(Initiative).filter_by(id=related_initiative_id).first()
        )
        if not related_initiative:
            raise Exception(f"Initiative with id {related_initiative_id} not found")

        # Create the initiative relation
        now = datetime.now(timezone.utc)
        initiative_relation = InitiativeRelation(
            id=entity_id,
            initiativeId=initiative_id,
            relatedInitiativeId=related_initiative_id,
            sortOrder=sort_order,
            createdAt=now,
            updatedAt=now,
            archivedAt=None,
        )

        session.add(initiative_relation)

        # Return InitiativeRelationPayload structure
        return {
            "initiativeRelation": initiative_relation,
            "success": True,
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
        }

    except Exception as e:
        raise Exception(f"Failed to create initiative relation: {str(e)}")


@mutation.field("initiativeRelationDelete")
def resolve_initiativeRelationDelete(obj, info, **kwargs):
    """
    Deletes an initiative relation.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (initiative relation ID to delete)

    Returns:
        Dict containing DeletePayload with entityId, success, and lastSyncId
    """

    session: Session = info.context["session"]
    relation_id = kwargs.get("id")

    try:
        # Fetch the initiative relation to delete
        initiative_relation = (
            session.query(InitiativeRelation).filter_by(id=relation_id).first()
        )

        if not initiative_relation:
            raise Exception(f"InitiativeRelation with id {relation_id} not found")

        # Soft delete by setting archivedAt timestamp
        initiative_relation.archivedAt = datetime.now(timezone.utc)
        initiative_relation.updatedAt = datetime.now(timezone.utc)

        # Return DeletePayload structure
        return {
            "entityId": relation_id,
            "success": True,
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
        }

    except Exception as e:
        raise Exception(f"Failed to delete initiative relation: {str(e)}")


@mutation.field("initiativeRelationUpdate")
def resolve_initiativeRelationUpdate(obj, info, **kwargs):
    """
    Updates an initiative relation.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (initiative relation ID) and 'input' (InitiativeRelationUpdateInput)

    Returns:
        Dict containing InitiativeRelationPayload with entityId, success, and lastSyncId
    """

    session: Session = info.context["session"]
    relation_id = kwargs.get("id")
    input_data = kwargs.get("input")

    if not relation_id:
        raise Exception("ID is required")

    if not input_data:
        raise Exception("Input data is required")

    try:
        # Fetch the initiative relation to update
        initiative_relation = (
            session.query(InitiativeRelation).filter_by(id=relation_id).first()
        )

        if not initiative_relation:
            raise Exception(f"InitiativeRelation with id {relation_id} not found")

        # Update sortOrder if provided
        if "sortOrder" in input_data:
            initiative_relation.sortOrder = input_data["sortOrder"]

        # Update the updatedAt timestamp
        initiative_relation.updatedAt = datetime.now(timezone.utc)

        # Return InitiativeRelationPayload structure
        return {
            "initiativeRelation": initiative_relation,
            "success": True,
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
        }

    except Exception as e:
        raise Exception(f"Failed to update initiative relation: {str(e)}")


@mutation.field("issueAddLabel")
def resolve_issueAddLabel(obj, info, **kwargs):
    """
    Resolver for issueAddLabel mutation.
    Adds a label to an issue.

    Args:
        id: The identifier of the issue to add the label to
        labelId: The identifier of the label to add

    Returns:
        The updated issue (IssuePayload!)
    """

    session: Session = info.context["session"]
    issue_id = kwargs.get("id")
    label_id = kwargs.get("labelId")

    if not issue_id:
        raise Exception("Issue ID is required")

    if not label_id:
        raise Exception("Label ID is required")

    try:
        # Fetch the issue
        issue = session.query(Issue).filter_by(id=issue_id).first()

        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        # Fetch the label
        label = session.query(IssueLabel).filter_by(id=label_id).first()

        if not label:
            raise Exception(f"IssueLabel with id {label_id} not found")

        # Check if the label is already associated with the issue
        if label in issue.labels:
            # Label already exists, just return the issue
            return issue

        # Add the label to the issue
        issue.labels.append(label)

        # Update the labelIds list
        if label_id not in issue.labelIds:
            issue.labelIds.append(label_id)

        # Update the updatedAt timestamp
        now = datetime.now(timezone.utc)
        issue.updatedAt = now

        session.flush()

        # Eagerly load the labels relationship
        from sqlalchemy.orm import selectinload

        issue = (
            session.query(Issue)
            .options(selectinload(Issue.labels))
            .filter_by(id=issue_id)
            .first()
        )

        # Return IssuePayload
        return {"success": True, "issue": issue, "lastSyncId": float(now.timestamp())}

    except Exception as e:
        raise Exception(f"Failed to add label to issue: {str(e)}")


@mutation.field("issueRemoveLabel")
def resolve_issueRemoveLabel(obj, info, **kwargs):
    """
    Resolver for issueRemoveLabel mutation.
    Removes a label from an issue.

    Args:
        id: The identifier of the issue to remove the label from
        labelId: The identifier of the label to remove

    Returns:
        The updated issue (IssuePayload!)
    """

    session: Session = info.context["session"]
    issue_id = kwargs.get("id")
    label_id = kwargs.get("labelId")

    if not issue_id:
        raise Exception("Issue ID is required")

    if not label_id:
        raise Exception("Label ID is required")

    try:
        # Fetch the issue
        issue = session.query(Issue).filter_by(id=issue_id).first()

        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        # Fetch the label
        label = session.query(IssueLabel).filter_by(id=label_id).first()

        if not label:
            raise Exception(f"IssueLabel with id {label_id} not found")

        # Check if the label is associated with the issue
        if label not in issue.labels:
            # Label is not associated, just return the issue
            return issue

        # Remove the label from the issue
        issue.labels.remove(label)

        # Update the labelIds list
        if label_id in issue.labelIds:
            issue.labelIds.remove(label_id)

        # Update the updatedAt timestamp
        now = datetime.now(timezone.utc)
        issue.updatedAt = now

        session.flush()

        # Eagerly load the labels relationship
        from sqlalchemy.orm import selectinload

        issue = (
            session.query(Issue)
            .options(selectinload(Issue.labels))
            .filter_by(id=issue_id)
            .first()
        )

        # Return IssuePayload
        return {"success": True, "issue": issue, "lastSyncId": float(now.timestamp())}

    except Exception as e:
        raise Exception(f"Failed to remove label from issue: {str(e)}")


@mutation.field("issueArchive")
def resolve_issueArchive(obj, info, **kwargs):
    """
    Resolver for issueArchive mutation.
    Archives an issue.

    Args:
        id: The identifier of the issue to archive
        trash: Whether to trash the issue (optional)

    Returns:
        IssueArchivePayload with success status and the archived entity
    """

    session: Session = info.context["session"]
    issue_id = kwargs.get("id")
    trash = kwargs.get("trash", False)

    if not issue_id:
        raise Exception("Issue ID is required")

    try:
        # Fetch the issue
        issue = session.query(Issue).filter_by(id=issue_id).first()

        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        # Soft delete: set archivedAt timestamp
        if issue.archivedAt is None:
            issue.archivedAt = datetime.now(timezone.utc)

        # Return the payload
        return {
            "success": True,
            "entity": issue,
            "lastSyncId": 0.0,  # This would typically come from a sync system
        }

    except Exception as e:
        raise Exception(f"Failed to archive issue: {str(e)}")


@mutation.field("issueUnarchive")
def resolve_issueUnarchive(obj, info, **kwargs):
    """
    Resolver for issueUnarchive mutation.
    Unarchives an issue.

    Args:
        id: The identifier of the issue to unarchive

    Returns:
        IssueArchivePayload with success status and the unarchived entity
    """
    session: Session = info.context["session"]
    issue_id = kwargs.get("id")

    if not issue_id:
        raise Exception("Issue ID is required")

    try:
        # Fetch the issue
        issue = session.query(Issue).filter_by(id=issue_id).first()

        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        # Unarchive: clear the archivedAt timestamp
        issue.archivedAt = None

        # Return the payload
        return {
            "success": True,
            "entity": issue,
            "lastSyncId": 0.0,  # This would typically come from a sync system
        }

    except Exception as e:
        raise Exception(f"Failed to unarchive issue: {str(e)}")


@mutation.field("issueUnsubscribe")
def resolve_issueUnsubscribe(obj, info, **kwargs):
    """
    Resolver for issueUnsubscribe mutation.
    Unsubscribes a user from an issue.

    Args:
        id: The identifier of the issue to unsubscribe from (required)
        userEmail: The email of the user to unsubscribe (optional)
        userId: The identifier of the user to unsubscribe (optional)

    Returns:
        IssuePayload with success status and the updated issue
    """
    session: Session = info.context["session"]
    issue_id = kwargs.get("id")
    user_email = kwargs.get("userEmail")
    user_id = kwargs.get("userId")

    if not issue_id:
        raise Exception("Issue ID is required")

    try:
        # Fetch the issue
        issue = session.query(Issue).filter_by(id=issue_id).first()

        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        # Determine which user to unsubscribe
        # Priority: userId, then userEmail, then current user from context
        user = None

        if user_id:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                raise Exception(f"User with id {user_id} not found")
        elif user_email:
            user = session.query(User).filter_by(email=user_email).first()
            if not user:
                raise Exception(f"User with email {user_email} not found")
        else:
            # Default to current authenticated user from context
            current_user_id = info.context.get("user_id")
            if current_user_id:
                user = session.query(User).filter_by(id=current_user_id).first()
            if not user:
                raise Exception(
                    "No user specified and no authenticated user in context"
                )

        # Remove the user from the issue's subscribers if they are subscribed
        if user in issue.subscribers:
            issue.subscribers.remove(user)

        # Return the payload
        return {
            "success": True,
            "issue": issue,
            "lastSyncId": 0.0,  # This would typically come from a sync system
        }

    except Exception as e:
        raise Exception(f"Failed to unsubscribe from issue: {str(e)}")


@mutation.field("issueDelete")
def resolve_issueDelete(obj, info, **kwargs):
    """
    Resolver for issueDelete mutation.
    Deletes (trashes) an issue.

    Args:
        id: The identifier of the issue to delete
        permanentlyDelete: Whether to permanently delete the issue and skip the grace period (optional, admin only)

    Returns:
        IssueArchivePayload with success status and the deleted/archived entity
    """

    session: Session = info.context["session"]
    issue_id = kwargs.get("id")
    permanently_delete = kwargs.get("permanentlyDelete", False)

    if not issue_id:
        raise Exception("Issue ID is required")

    try:
        # Fetch the issue
        issue = session.query(Issue).filter_by(id=issue_id).first()

        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        if permanently_delete:
            # Hard delete: permanently remove from database
            session.delete(issue)

            # Return success with null entity (as per spec: "Null if entity was deleted")
            return {"success": True, "entity": None, "lastSyncId": 0.0}
        else:
            # Soft delete: set archivedAt timestamp (trash with 30-day grace period)
            if issue.archivedAt is None:
                issue.archivedAt = datetime.now(timezone.utc)

            # Mark as trashed
            if hasattr(issue, "trashed"):
                issue.trashed = True

            # Return the payload with the trashed entity
            return {"success": True, "entity": issue, "lastSyncId": 0.0}

    except Exception as e:
        raise Exception(f"Failed to delete issue: {str(e)}")


@mutation.field("issueUpdate")
def resolve_issueUpdate(obj, info, **kwargs):
    """
    Updates an issue.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains:
            - id: String! - The identifier of the issue to update
            - input: IssueUpdateInput! - A partial issue object to update the issue with

    Returns:
        Dict with:
            - issue: The updated Issue entity
            - success: Boolean
            - lastSyncId: Float (sync operation identifier)
    """

    session: Session = info.context["session"]
    issue_id = kwargs.get("id")
    input_data = kwargs.get("input", {})

    try:
        # Validate required parameters
        if not issue_id:
            raise ValueError("Issue ID is required")

        # Query for the issue to update
        issue = session.query(Issue).filter_by(id=issue_id).first()

        if not issue:
            raise ValueError(f"Issue not found with ID: {issue_id}")

        now = datetime.now(timezone.utc)

        # Handle label updates (addedLabelIds and removedLabelIds)
        if "addedLabelIds" in input_data:
            added_labels = input_data["addedLabelIds"]
            current_labels = issue.labelIds if issue.labelIds else []
            # Add new labels that aren't already present
            for label_id in added_labels:
                if label_id not in current_labels:
                    current_labels.append(label_id)
            issue.labelIds = current_labels

        if "removedLabelIds" in input_data:
            removed_labels = input_data["removedLabelIds"]
            current_labels = issue.labelIds if issue.labelIds else []
            # Remove labels
            issue.labelIds = [
                lid for lid in current_labels if lid not in removed_labels
            ]

        # Handle labelIds (direct replacement)
        if "labelIds" in input_data:
            issue.labelIds = input_data["labelIds"]

        # Handle subscriberIds (direct replacement)
        if "subscriberIds" in input_data:
            # This would need to update the association table
            # For now, we'll skip this as it requires relationship handling
            pass

        # Update simple fields
        if "assigneeId" in input_data:
            issue.assigneeId = input_data["assigneeId"]

        if "autoClosedByParentClosing" in input_data:
            issue.autoClosedByParentClosing = input_data["autoClosedByParentClosing"]

        if "boardOrder" in input_data:
            issue.boardOrder = float(input_data["boardOrder"])

        if "cycleId" in input_data:
            issue.cycleId = input_data["cycleId"]

        if "delegateId" in input_data:
            issue.delegateId = input_data["delegateId"]

        if "description" in input_data:
            issue.description = input_data["description"]

        if "descriptionData" in input_data:
            issue.descriptionData = input_data["descriptionData"]

        if "dueDate" in input_data:
            issue.dueDate = input_data["dueDate"]

        if "estimate" in input_data:
            issue.estimate = (
                float(input_data["estimate"])
                if input_data["estimate"] is not None
                else None
            )

        if "lastAppliedTemplateId" in input_data:
            issue.lastAppliedTemplateId = input_data["lastAppliedTemplateId"]

        if "parentId" in input_data:
            issue.parentId = input_data["parentId"]

        if "priority" in input_data:
            issue.priority = float(input_data["priority"])

        if "prioritySortOrder" in input_data:
            issue.prioritySortOrder = float(input_data["prioritySortOrder"])

        if "projectId" in input_data:
            issue.projectId = input_data["projectId"]

        if "projectMilestoneId" in input_data:
            issue.projectMilestoneId = input_data["projectMilestoneId"]

        if "slaBreachesAt" in input_data:
            issue.slaBreachesAt = input_data["slaBreachesAt"]

        if "slaStartedAt" in input_data:
            issue.slaStartedAt = input_data["slaStartedAt"]

        if "slaType" in input_data:
            issue.slaType = input_data["slaType"]

        if "snoozedById" in input_data:
            issue.snoozedById = input_data["snoozedById"]

        if "snoozedUntilAt" in input_data:
            issue.snoozedUntilAt = input_data["snoozedUntilAt"]

        if "sortOrder" in input_data:
            issue.sortOrder = float(input_data["sortOrder"])

        if "stateId" in input_data:
            issue.stateId = input_data["stateId"]

        if "subIssueSortOrder" in input_data:
            issue.subIssueSortOrder = (
                float(input_data["subIssueSortOrder"])
                if input_data["subIssueSortOrder"] is not None
                else None
            )

        if "teamId" in input_data:
            issue.teamId = input_data["teamId"]

        if "title" in input_data:
            issue.title = input_data["title"]

        if "trashed" in input_data:
            issue.trashed = input_data["trashed"]

        # Always update the updatedAt timestamp
        issue.updatedAt = now

        # Return the payload
        return {"issue": issue, "success": True, "lastSyncId": float(now.timestamp())}

    except ValueError as e:
        raise Exception(f"Invalid input for issue update: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to update issue: {str(e)}")


@mutation.field("issueCreate")
def resolve_issueCreate(obj, info, **kwargs):
    """
    Creates a new issue.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'input' with IssueCreateInput data

    Returns:
        Dict with:
            - issue: The created Issue entity
            - success: Boolean
            - lastSyncId: Float (sync operation identifier)
    """
    import uuid

    session: Session = info.context["session"]
    input_data = kwargs.get("input", {})

    try:
        # Generate ID if not provided
        issue_id = input_data.get("id") or str(uuid.uuid4())

        # Extract required fields
        team_id = input_data["teamId"]  # Required field

        # Extract optional fields
        title = input_data.get("title", "")
        assignee_id = input_data.get("assigneeId")
        cycle_id = input_data.get("cycleId")
        delegate_id = input_data.get("delegateId")
        parent_id = input_data.get("parentId")
        project_id = input_data.get("projectId")
        project_milestone_id = input_data.get("projectMilestoneId")
        state_id = input_data.get("stateId")

        # If stateId is not provided, set it to the team's default Backlog state
        if not state_id:
            # Query for the team's Backlog state (position 1.0)
            backlog_state = (
                session.query(WorkflowState)
                .filter(WorkflowState.teamId == team_id)
                .filter(WorkflowState.position == 1.0)
                .first()
            )
            if backlog_state:
                state_id = backlog_state.id
            else:
                # Fallback: get any state for this team (shouldn't happen with auto-creation)
                fallback_state = (
                    session.query(WorkflowState)
                    .filter(WorkflowState.teamId == team_id)
                    .order_by(WorkflowState.position)
                    .first()
                )
                if fallback_state:
                    state_id = fallback_state.id
                else:
                    raise Exception(
                        f"No workflow states found for team {team_id}. "
                        "Workflow states should be created automatically when a team is created."
                    )

        description = input_data.get("description")
        description_data = input_data.get("descriptionData")
        last_applied_template_id = input_data.get("lastAppliedTemplateId")
        source_comment_id = input_data.get("sourceCommentId")
        reference_comment_id = input_data.get("referenceCommentId")

        # Date fields
        now = datetime.now(timezone.utc)
        created_at = input_data.get("createdAt", now)
        completed_at = input_data.get("completedAt")
        due_date = input_data.get("dueDate")

        # Numeric fields
        estimate = input_data.get("estimate")
        priority = input_data.get("priority", 0)  # Default to no priority
        # Validate priority value (must be 0-4)
        priority = _validate_priority(priority)
        board_order = input_data.get("boardOrder", 0.0)
        sort_order = input_data.get("sortOrder", 0.0)
        sub_issue_sort_order = input_data.get("subIssueSortOrder")
        priority_sort_order = input_data.get("prioritySortOrder", 0.0)

        # Array fields
        label_ids = input_data.get("labelIds", [])
        subscriber_ids = input_data.get("subscriberIds", [])

        # SLA fields
        sla_type = input_data.get("slaType")
        sla_breaches_at = input_data.get("slaBreachesAt")
        sla_started_at = input_data.get("slaStartedAt")

        # Special fields
        create_as_user = input_data.get("createAsUser")  # External user display name
        preserve_sort_order = input_data.get("preserveSortOrderOnCreate", False)

        # Create the Issue entity
        issue = Issue(
            id=issue_id,
            teamId=team_id,
            title=title,
            assigneeId=assignee_id,
            cycleId=cycle_id,
            delegateId=delegate_id,
            parentId=parent_id,
            projectId=project_id,
            projectMilestoneId=project_milestone_id,
            stateId=state_id,
            description=description,
            descriptionData=description_data,
            lastAppliedTemplateId=last_applied_template_id,
            sourceCommentId=source_comment_id,
            createdAt=created_at if isinstance(created_at, datetime) else now,
            updatedAt=now,
            completedAt=completed_at,
            dueDate=due_date,
            estimate=float(estimate) if estimate is not None else None,
            priority=float(priority),
            boardOrder=float(board_order),
            sortOrder=float(sort_order),
            subIssueSortOrder=float(sub_issue_sort_order)
            if sub_issue_sort_order is not None
            else None,
            prioritySortOrder=float(priority_sort_order),
            labelIds=label_ids,
            slaType=sla_type,
            slaBreachesAt=sla_breaches_at,
            slaStartedAt=sla_started_at,
            # Default values for required fields that are system-generated
            branchName="",  # Will be generated based on title
            customerTicketCount=0,
            identifier="",  # Will be generated based on team + number
            number=0.0,  # Will be auto-incremented by the system
            priorityLabel=_get_priority_label(priority),
            reactionData={},
            previousIdentifiers=[],
            url="",  # Will be generated from identifier
            archivedAt=None,
            trashed=False,
        )

        # Generate sequential issue number and identifier with row lock to avoid races
        from sqlalchemy.exc import OperationalError

        max_retries = 3
        for attempt in range(max_retries):
            try:
                team = (
                    session.query(Team)
                    .filter(Team.id == team_id)
                    .with_for_update()
                    .one_or_none()
                )
                if team is None:
                    raise Exception(f"Team not found: {team_id}")

                next_number_int = int((team.issueCount or 0) + 1)
                team.issueCount = next_number_int
                issue.number = float(next_number_int)
                issue.identifier = f"{team.key}-{next_number_int}"
                issue.url = issue.url or f"/issues/{issue.identifier}"

                # Persist while holding the lock
                session.add(issue)
                session.flush()
                session.refresh(issue)
                break
            except OperationalError as oe:
                if "deadlock detected" in str(oe).lower() and attempt < max_retries - 1:
                    session.rollback()
                    continue
                raise

        # Return the payload
        return {"issue": issue, "success": True, "lastSyncId": float(now.timestamp())}

    except KeyError as e:
        raise Exception(f"Missing required field in issue create: {str(e)}")
    except ValueError as e:
        raise Exception(f"Invalid value in issue create: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to create issue: {str(e)}")


# ================================================================================
# IssueBatch Mutation Resolvers
# ================================================================================


@mutation.field("issueBatchCreate")
def resolve_issueBatchCreate(obj, info, **kwargs):
    """
    Creates a batch of issues in one transaction.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'input' with IssueBatchCreateInput data
                  input has 'issues' field with list of IssueCreateInput

    Returns:
        Dict with:
            - issues: list of created Issue entities
            - success: Boolean
            - lastSyncId: Float (sync operation identifier)
    """
    import uuid

    session: Session = info.context["session"]
    input_data = kwargs.get("input", {})

    try:
        # Extract the list of issue inputs
        issues_input = input_data.get("issues", [])

        if not issues_input:
            raise ValueError("At least one issue must be provided in the batch")

        created_issues = []
        # Cache per-team data while holding row locks
        team_counters: dict[str, int] = {}
        team_rows: dict[str, Team] = {}
        team_keys: dict[str, str] = {}
        now = datetime.now(timezone.utc)

        # Create each issue in the batch
        for issue_input in issues_input:
            # Generate ID if not provided
            issue_id = issue_input.get("id") or str(uuid.uuid4())

            # Extract required fields
            team_id = issue_input["teamId"]  # Required
            title = issue_input.get("title", "")  # Default to empty if not provided

            # Extract optional fields with defaults
            assignee_id = issue_input.get("assigneeId")
            cycle_id = issue_input.get("cycleId")
            delegate_id = issue_input.get("delegateId")
            parent_id = issue_input.get("parentId")
            project_id = issue_input.get("projectId")
            project_milestone_id = issue_input.get("projectMilestoneId")
            state_id = issue_input.get("stateId")

            # If stateId is not provided, set it to the team's default Backlog state
            if not state_id:
                # Query for the team's Backlog state (position 1.0)
                backlog_state = (
                    session.query(WorkflowState)
                    .filter(WorkflowState.teamId == team_id)
                    .filter(WorkflowState.position == 1.0)
                    .first()
                )
                if backlog_state:
                    state_id = backlog_state.id
                else:
                    # Fallback: get any state for this team
                    fallback_state = (
                        session.query(WorkflowState)
                        .filter(WorkflowState.teamId == team_id)
                        .order_by(WorkflowState.position)
                        .first()
                    )
                    if fallback_state:
                        state_id = fallback_state.id
                    else:
                        raise Exception(
                            f"No workflow states found for team {team_id}. "
                            "Workflow states should be created automatically when a team is created."
                        )

            description = issue_input.get("description")
            description_data = issue_input.get("descriptionData")

            # Date fields
            created_at = issue_input.get("createdAt", now)
            completed_at = issue_input.get("completedAt")
            due_date = issue_input.get("dueDate")

            # Numeric fields
            estimate = issue_input.get("estimate")
            priority = issue_input.get("priority", 0)  # Default to no priority
            # Validate priority value (must be 0-4)
            priority = _validate_priority(priority)
            board_order = issue_input.get("boardOrder", 0.0)
            sort_order = issue_input.get("sortOrder", 0.0)
            sub_issue_sort_order = issue_input.get("subIssueSortOrder")
            priority_sort_order = issue_input.get("prioritySortOrder", 0.0)

            # Array fields
            label_ids = issue_input.get("labelIds", [])

            # SLA fields
            sla_type = issue_input.get("slaType")
            sla_breaches_at = issue_input.get("slaBreachesAt")
            sla_started_at = issue_input.get("slaStartedAt")

            # Comment references
            source_comment_id = issue_input.get("sourceCommentId")

            # Create the Issue entity
            issue = Issue(
                id=issue_id,
                teamId=team_id,
                title=title,
                assigneeId=assignee_id,
                cycleId=cycle_id,
                delegateId=delegate_id,
                parentId=parent_id,
                projectId=project_id,
                projectMilestoneId=project_milestone_id,
                stateId=state_id,
                description=description,
                descriptionState=description_data,  # Map descriptionData to descriptionState
                createdAt=created_at if isinstance(created_at, datetime) else now,
                updatedAt=now,
                completedAt=completed_at,
                dueDate=due_date,
                estimate=float(estimate) if estimate is not None else None,
                priority=float(priority),
                boardOrder=float(board_order),
                sortOrder=float(sort_order),
                subIssueSortOrder=float(sub_issue_sort_order)
                if sub_issue_sort_order is not None
                else None,
                prioritySortOrder=float(priority_sort_order),
                labelIds=label_ids,
                slaType=sla_type,
                slaBreachesAt=sla_breaches_at,
                slaStartedAt=sla_started_at,
                sourceCommentId=source_comment_id,
                # Default values for required fields
                branchName=issue_input.get("branchName", ""),
                customerTicketCount=0,
                identifier=issue_input.get(
                    "identifier", ""
                ),  # This should be generated by the system
                number=issue_input.get(
                    "number", 0.0
                ),  # This should be generated by the system
                priorityLabel=_get_priority_label(priority),
                reactionData={},
                previousIdentifiers=[],
                url=issue_input.get("url", ""),
                archivedAt=None,
                trashed=False,
            )

            # Generate sequential issue number and identifier with row lock
            if team_id not in team_counters:
                # Lock the team row on first encounter in this batch
                team_row = (
                    session.query(Team)
                    .filter(Team.id == team_id)
                    .with_for_update()
                    .one_or_none()
                )
                if team_row is None:
                    raise Exception(f"Team not found: {team_id}")
                team_rows[team_id] = team_row
                team_keys[team_id] = team_row.key
                team_counters[team_id] = int(team_row.issueCount or 0)
            # Increment atomically within the transaction
            next_number_int = team_counters[team_id] + 1
            team_counters[team_id] = next_number_int
            team_rows[team_id].issueCount = next_number_int
            issue.number = float(next_number_int)
            issue.identifier = f"{team_keys[team_id]}-{next_number_int}"
            issue.url = issue.url or f"/issues/{issue.identifier}"

            # Add to session
            session.add(issue)
            created_issues.append(issue)

        from sqlalchemy.exc import OperationalError

        max_retries = 3
        for attempt in range(max_retries):
            try:
                session.flush()
                for created in created_issues:
                    session.refresh(created)
                break
            except OperationalError as oe:
                if "deadlock detected" in str(oe).lower() and attempt < max_retries - 1:
                    session.rollback()
                    continue
                raise

        # Return the payload
        return {
            "issues": created_issues,
            "success": True,
            "lastSyncId": float(datetime.now(timezone.utc).timestamp()),
        }

    except KeyError as e:
        raise Exception(f"Missing required field in issue batch create: {str(e)}")
    except ValueError as e:
        raise Exception(f"Invalid value in issue batch create: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to create issue batch: {str(e)}")


@mutation.field("issueBatchUpdate")
def resolve_issueBatchUpdate(obj, info, **kwargs):
    """
    Updates multiple issues at once.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains:
            - ids: List of issue IDs to update (max 50)
            - input: IssueUpdateInput with fields to update

    Returns:
        Dict with:
            - issues: list of updated Issue entities
            - success: Boolean
            - lastSyncId: Float (sync operation identifier)
    """

    session: Session = info.context["session"]
    ids = kwargs.get("ids", [])
    input_data = kwargs.get("input", {})

    try:
        # Validate input
        if not ids:
            raise ValueError("At least one issue ID must be provided")

        if len(ids) > 50:
            raise ValueError("Cannot update more than 50 issues at once")

        # Query for all issues to update
        issues = session.query(Issue).filter(Issue.id.in_(ids)).all()

        if not issues:
            raise ValueError("No issues found with the provided IDs")

        # Track which issues were found
        found_ids = {issue.id for issue in issues}
        missing_ids = set(ids) - found_ids
        if missing_ids:
            raise ValueError(f"Issues not found: {', '.join(missing_ids)}")

        now = datetime.now(timezone.utc)

        # Update each issue with the provided fields
        for issue in issues:
            # Handle label updates (addedLabelIds and removedLabelIds)
            if "addedLabelIds" in input_data:
                added_labels = input_data["addedLabelIds"]
                current_labels = issue.labelIds if issue.labelIds else []
                # Add new labels that aren't already present
                for label_id in added_labels:
                    if label_id not in current_labels:
                        current_labels.append(label_id)
                issue.labelIds = current_labels

            if "removedLabelIds" in input_data:
                removed_labels = input_data["removedLabelIds"]
                current_labels = issue.labelIds if issue.labelIds else []
                # Remove labels
                issue.labelIds = [
                    lid for lid in current_labels if lid not in removed_labels
                ]

            # Handle labelIds (direct replacement)
            if "labelIds" in input_data:
                issue.labelIds = input_data["labelIds"]

            # Handle subscriberIds (direct replacement)
            if "subscriberIds" in input_data:
                # This would need to update the association table
                # For now, we'll skip this as it requires relationship handling
                pass

            # Update simple fields
            if "assigneeId" in input_data:
                issue.assigneeId = input_data["assigneeId"]

            if "autoClosedByParentClosing" in input_data:
                issue.autoClosedByParentClosing = input_data[
                    "autoClosedByParentClosing"
                ]

            if "boardOrder" in input_data:
                issue.boardOrder = float(input_data["boardOrder"])

            if "cycleId" in input_data:
                issue.cycleId = input_data["cycleId"]

            if "delegateId" in input_data:
                issue.delegateId = input_data["delegateId"]

            if "description" in input_data:
                issue.description = input_data["description"]

            if "descriptionData" in input_data:
                issue.descriptionData = input_data["descriptionData"]

            if "dueDate" in input_data:
                issue.dueDate = input_data["dueDate"]

            if "estimate" in input_data:
                issue.estimate = (
                    float(input_data["estimate"])
                    if input_data["estimate"] is not None
                    else None
                )

            if "lastAppliedTemplateId" in input_data:
                # This field exists in the Issue model
                issue.lastAppliedTemplateId = input_data["lastAppliedTemplateId"]

            if "parentId" in input_data:
                issue.parentId = input_data["parentId"]

            if "priority" in input_data:
                issue.priority = float(input_data["priority"])

            if "prioritySortOrder" in input_data:
                issue.prioritySortOrder = float(input_data["prioritySortOrder"])

            if "projectId" in input_data:
                issue.projectId = input_data["projectId"]

            if "projectMilestoneId" in input_data:
                issue.projectMilestoneId = input_data["projectMilestoneId"]

            if "slaBreachesAt" in input_data:
                issue.slaBreachesAt = input_data["slaBreachesAt"]

            if "slaStartedAt" in input_data:
                issue.slaStartedAt = input_data["slaStartedAt"]

            if "slaType" in input_data:
                issue.slaType = input_data["slaType"]

            if "snoozedById" in input_data:
                issue.snoozedById = input_data["snoozedById"]

            if "snoozedUntilAt" in input_data:
                issue.snoozedUntilAt = input_data["snoozedUntilAt"]

            if "sortOrder" in input_data:
                issue.sortOrder = float(input_data["sortOrder"])

            if "stateId" in input_data:
                issue.stateId = input_data["stateId"]

            if "subIssueSortOrder" in input_data:
                issue.subIssueSortOrder = (
                    float(input_data["subIssueSortOrder"])
                    if input_data["subIssueSortOrder"] is not None
                    else None
                )

            if "teamId" in input_data:
                issue.teamId = input_data["teamId"]

            if "title" in input_data:
                issue.title = input_data["title"]

            if "trashed" in input_data:
                issue.trashed = input_data["trashed"]

            # Always update the updatedAt timestamp
            issue.updatedAt = now

        # Return the payload
        return {
            "issues": issues,
            "success": True,
            "lastSyncId": float(datetime.now(timezone.utc).timestamp()),
        }

    except ValueError as e:
        raise Exception(f"Invalid input for issue batch update: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to update issue batch: {str(e)}")


@mutation.field("issueDescriptionUpdateFromFront")
def resolve_issueDescriptionUpdateFromFront(obj, info, **kwargs):
    """
    [INTERNAL] Updates an issue description from the Front app to handle Front attachments correctly.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains:
            - description: String! - Description to update the issue with
            - id: String! - The identifier of the issue to update

    Returns:
        Dict with:
            - issue: The updated Issue entity
            - success: Boolean
            - lastSyncId: Float (sync operation identifier)
    """

    session: Session = info.context["session"]
    issue_id = kwargs.get("id")
    description = kwargs.get("description")

    try:
        # Validate required arguments
        if not issue_id:
            raise ValueError("Issue ID is required")

        if description is None:  # Allow empty string but not None
            raise ValueError("Description is required")

        # Query for the issue
        issue = session.query(Issue).filter_by(id=issue_id).first()

        if not issue:
            raise ValueError(f"Issue with ID {issue_id} not found")

        # Update the description
        issue.description = description

        # Update the timestamp
        now = datetime.now(timezone.utc)
        issue.updatedAt = now

        # Return the payload
        return {"issue": issue, "success": True, "lastSyncId": float(now.timestamp())}

    except ValueError as e:
        raise Exception(f"Invalid input for issue description update: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to update issue description: {str(e)}")


@mutation.field("issueExternalSyncDisable")
def resolve_issueExternalSyncDisable(obj, info, **kwargs):
    """
    Disables external sync on an issue by archiving the sync attachment.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains:
            - attachmentId: String! - The ID of the sync attachment to disable

    Returns:
        The Issue entity that the attachment belonged to
    """

    session: Session = info.context["session"]
    attachment_id = kwargs.get("attachmentId")

    try:
        # Validate required argument
        if not attachment_id:
            raise ValueError("attachmentId is required")

        # Query for the attachment
        attachment = session.query(Attachment).filter_by(id=attachment_id).first()

        if not attachment:
            raise ValueError(f"Attachment with ID {attachment_id} not found")

        # Get the associated issue before we archive the attachment
        issue_id = attachment.issueId
        issue = session.query(Issue).filter_by(id=issue_id).first()

        if not issue:
            raise ValueError(f"Issue with ID {issue_id} not found")

        # Disable external sync by archiving the attachment (soft delete)
        attachment.archivedAt = datetime.now(timezone.utc)

        # Update the attachment's timestamp
        attachment.updatedAt = datetime.now(timezone.utc)

        # Update the issue's timestamp as well since its sync status changed
        issue.updatedAt = datetime.now(timezone.utc)

        return issue

    except ValueError as e:
        raise Exception(f"Invalid input for disabling external sync: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to disable external sync: {str(e)}")


# ================================================================================
# IssueImport Mutation Resolvers
# ================================================================================


@mutation.field("issueImportCreateAsana")
def resolve_issueImportCreateAsana(obj, info, **kwargs):
    """
    Kicks off an Asana import job.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains:
            - asanaTeamName: String! - Asana team name to choose which issues to import
            - asanaToken: String! - Asana token to fetch information from the Asana API
            - id: String (optional) - ID of issue import. If not provided it will be generated
            - includeClosedIssues: Boolean (optional) - Whether to collect data for closed issues
            - instantProcess: Boolean (optional) - Whether to instantly process with default config
            - organizationId: String (optional, deprecated) - Organization ID (ignored)
            - teamId: String (optional) - ID of the team into which to import data
            - teamName: String (optional) - Name of new team when teamId is not set

    Returns:
        IssueImport entity representing the created import job
    """
    import uuid

    session: Session = info.context["session"]

    try:
        # Validate required arguments
        asana_team_name = kwargs.get("asanaTeamName")
        asana_token = kwargs.get("asanaToken")

        if not asana_team_name:
            raise ValueError("asanaTeamName is required")
        if not asana_token:
            raise ValueError("asanaToken is required")

        # Get optional arguments
        import_id = kwargs.get("id") or str(uuid.uuid4())
        include_closed = kwargs.get("includeClosedIssues", False)
        instant_process = kwargs.get("instantProcess", False)
        team_id = kwargs.get("teamId")
        team_name = kwargs.get("teamName")

        # Create the import job
        now = datetime.now(timezone.utc)

        # Prepare service metadata
        service_metadata = {
            "asanaTeamName": asana_team_name,
            "includeClosedIssues": include_closed,
            "instantProcess": instant_process,
        }
        if team_id:
            service_metadata["teamId"] = team_id

        issue_import = IssueImport(
            id=import_id,
            createdAt=now,
            updatedAt=now,
            service="asana",
            displayName=f"Asana Import - {asana_team_name}",
            status="pending",
            progress=0.0,
            serviceMetadata=service_metadata,
            teamName=team_name,
        )

        # Add to session
        session.add(issue_import)

        return issue_import

    except ValueError as e:
        raise Exception(f"Invalid input for Asana import: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to create Asana import job: {str(e)}")


@mutation.field("issueImportCreateClubhouse")
def resolve_issueImportCreateClubhouse(obj, info, **kwargs):
    """
    Kicks off a Shortcut (formerly Clubhouse) import job.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains:
            - clubhouseGroupName: String! - Shortcut group name to choose which issues to import
            - clubhouseToken: String! - Shortcut token to fetch information from the Clubhouse API
            - id: String (optional) - ID of issue import. If not provided it will be generated
            - includeClosedIssues: Boolean (optional) - Whether to collect data for closed issues
            - instantProcess: Boolean (optional) - Whether to instantly process with default config
            - organizationId: String (optional, deprecated) - Organization ID (ignored)
            - teamId: String (optional) - ID of the team into which to import data
            - teamName: String (optional) - Name of new team when teamId is not set

    Returns:
        IssueImport entity representing the created import job
    """
    import uuid

    session: Session = info.context["session"]

    try:
        # Validate required arguments
        clubhouse_group_name = kwargs.get("clubhouseGroupName")
        clubhouse_token = kwargs.get("clubhouseToken")

        if not clubhouse_group_name:
            raise ValueError("clubhouseGroupName is required")
        if not clubhouse_token:
            raise ValueError("clubhouseToken is required")

        # Get optional arguments
        import_id = kwargs.get("id") or str(uuid.uuid4())
        include_closed = kwargs.get("includeClosedIssues", False)
        instant_process = kwargs.get("instantProcess", False)
        team_id = kwargs.get("teamId")
        team_name = kwargs.get("teamName")

        # Create the import job
        now = datetime.now(timezone.utc)

        # Prepare service metadata
        service_metadata = {
            "clubhouseGroupName": clubhouse_group_name,
            "includeClosedIssues": include_closed,
            "instantProcess": instant_process,
        }
        if team_id:
            service_metadata["teamId"] = team_id

        issue_import = IssueImport(
            id=import_id,
            createdAt=now,
            updatedAt=now,
            service="clubhouse",
            displayName=f"Shortcut Import - {clubhouse_group_name}",
            status="pending",
            progress=0.0,
            serviceMetadata=service_metadata,
            teamName=team_name,
        )

        session.add(issue_import)

        return issue_import

    except ValueError as e:
        raise Exception(f"Invalid input for Clubhouse import: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to create Clubhouse import job: {str(e)}")


@mutation.field("issueImportCreateCSVJira")
def resolve_issueImportCreateCSVJira(obj, info, **kwargs):
    """
    Kicks off a Jira import job from a CSV.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains:
            - csvUrl: String! - URL for the CSV
            - jiraEmail: String (optional) - Jira user account email
            - jiraHostname: String (optional) - Jira installation or cloud hostname
            - jiraToken: String (optional) - Jira personal access token to access Jira REST API
            - organizationId: String (optional, deprecated) - Organization ID (ignored)
            - teamId: String (optional) - ID of the team into which to import data
            - teamName: String (optional) - Name of new team when teamId is not set

    Returns:
        IssueImport entity representing the created import job
    """
    import uuid

    session: Session = info.context["session"]

    try:
        # Validate required arguments
        csv_url = kwargs.get("csvUrl")
        if not csv_url:
            raise ValueError("csvUrl is required")

        # Get optional arguments
        jira_email = kwargs.get("jiraEmail")
        jira_hostname = kwargs.get("jiraHostname")
        jira_token = kwargs.get("jiraToken")
        team_id = kwargs.get("teamId")
        team_name = kwargs.get("teamName")

        # Generate ID
        import_id = str(uuid.uuid4())

        # Create the import job
        now = datetime.now(timezone.utc)

        # Prepare service metadata
        service_metadata = {
            "csvUrl": csv_url,
        }
        if jira_email:
            service_metadata["jiraEmail"] = jira_email
        if jira_hostname:
            service_metadata["jiraHostname"] = jira_hostname
        if jira_token:
            service_metadata["jiraToken"] = jira_token
        if team_id:
            service_metadata["teamId"] = team_id

        # Determine display name based on available info
        display_name = "Jira CSV Import"
        if jira_hostname:
            display_name = f"Jira CSV Import - {jira_hostname}"

        issue_import = IssueImport(
            id=import_id,
            createdAt=now,
            updatedAt=now,
            service="jira",
            displayName=display_name,
            status="pending",
            progress=0.0,
            csvFileUrl=csv_url,
            serviceMetadata=service_metadata,
            teamName=team_name,
        )

        session.add(issue_import)

        return issue_import

    except ValueError as e:
        raise Exception(f"Invalid input for Jira CSV import: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to create Jira CSV import job: {str(e)}")


@mutation.field("issueImportCreateGithub")
def resolve_issueImportCreateGithub(obj, info, **kwargs):
    """
    Kicks off a GitHub import job.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains:
            - githubLabels: [String!] (optional) - Labels to filter import data
            - githubRepoIds: [Int!] (optional) - IDs of GitHub repositories to import from
            - githubShouldImportOrgProjects: Boolean (optional, deprecated) - Ignored
            - includeClosedIssues: Boolean (optional) - Whether to collect data for closed issues
            - instantProcess: Boolean (optional) - Whether to instantly process with default config
            - integrationId: String (optional, deprecated) - Ignored
            - organizationId: String (optional, deprecated) - Ignored
            - teamId: String (optional) - ID of the team into which to import data
            - teamName: String (optional) - Name of new team when teamId is not set

    Returns:
        IssueImport entity representing the created import job
    """
    import uuid

    session: Session = info.context["session"]

    try:
        # Get optional arguments
        github_labels = kwargs.get("githubLabels", [])
        github_repo_ids = kwargs.get("githubRepoIds", [])
        include_closed = kwargs.get("includeClosedIssues", False)
        instant_process = kwargs.get("instantProcess", False)
        team_id = kwargs.get("teamId")
        team_name = kwargs.get("teamName")

        # Generate ID
        import_id = str(uuid.uuid4())

        # Create the import job
        now = datetime.now(timezone.utc)

        # Prepare service metadata
        service_metadata = {
            "includeClosedIssues": include_closed,
            "instantProcess": instant_process,
        }
        if github_labels:
            service_metadata["githubLabels"] = github_labels
        if github_repo_ids:
            service_metadata["githubRepoIds"] = github_repo_ids
        if team_id:
            service_metadata["teamId"] = team_id

        # Determine display name based on available info
        display_name = "GitHub Import"
        if github_repo_ids:
            repo_count = len(github_repo_ids)
            display_name = f"GitHub Import - {repo_count} repositor{'y' if repo_count == 1 else 'ies'}"

        issue_import = IssueImport(
            id=import_id,
            createdAt=now,
            updatedAt=now,
            service="github",
            displayName=display_name,
            status="pending",
            progress=0.0,
            serviceMetadata=service_metadata,
            teamName=team_name,
        )

        # Add to session
        session.add(issue_import)

        return issue_import

    except ValueError as e:
        raise Exception(f"Invalid input for GitHub import: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to create GitHub import job: {str(e)}")


@mutation.field("issueImportCreateJira")
def resolve_issueImportCreateJira(obj, info, **kwargs):
    """
    Kicks off a Jira import job.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains:
            - jiraEmail: String! - Jira user account email
            - jiraHostname: String! - Jira installation or cloud hostname
            - jiraProject: String! - Jira project key from which to import data
            - jiraToken: String! - Jira personal access token to access Jira REST API
            - id: String (optional) - ID of issue import. If not provided it will be generated
            - includeClosedIssues: Boolean (optional) - Whether to collect data for closed issues
            - instantProcess: Boolean (optional) - Whether to instantly process with default config
            - jql: String (optional) - A custom JQL query to filter issues being imported
            - organizationId: String (optional, deprecated) - Organization ID (ignored)
            - teamId: String (optional) - ID of the team into which to import data
            - teamName: String (optional) - Name of new team when teamId is not set

    Returns:
        IssueImport entity representing the created import job
    """
    import uuid

    session: Session = info.context["session"]

    try:
        # Validate required arguments
        jira_email = kwargs.get("jiraEmail")
        jira_hostname = kwargs.get("jiraHostname")
        jira_project = kwargs.get("jiraProject")
        jira_token = kwargs.get("jiraToken")

        if not jira_email:
            raise ValueError("jiraEmail is required")
        if not jira_hostname:
            raise ValueError("jiraHostname is required")
        if not jira_project:
            raise ValueError("jiraProject is required")
        if not jira_token:
            raise ValueError("jiraToken is required")

        # Get optional arguments
        import_id = kwargs.get("id") or str(uuid.uuid4())
        include_closed = kwargs.get("includeClosedIssues", False)
        instant_process = kwargs.get("instantProcess", False)
        jql = kwargs.get("jql")
        team_id = kwargs.get("teamId")
        team_name = kwargs.get("teamName")

        # Create the import job
        now = datetime.now(timezone.utc)

        # Prepare service metadata
        service_metadata = {
            "jiraEmail": jira_email,
            "jiraHostname": jira_hostname,
            "jiraProject": jira_project,
            "includeClosedIssues": include_closed,
            "instantProcess": instant_process,
        }
        if jql:
            service_metadata["jql"] = jql
        if team_id:
            service_metadata["teamId"] = team_id

        issue_import = IssueImport(
            id=import_id,
            createdAt=now,
            updatedAt=now,
            service="jira",
            displayName=f"Jira Import - {jira_project}",
            status="pending",
            progress=0.0,
            serviceMetadata=service_metadata,
            teamName=team_name,
        )

        # Add to session
        session.add(issue_import)

        return issue_import

    except ValueError as e:
        raise Exception(f"Invalid input for Jira import: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to create Jira import job: {str(e)}")


@mutation.field("issueImportCreateLinearV2")
def resolve_issueImportCreateLinearV2(obj, info, **kwargs):
    """
    [INTERNAL] Kicks off a Linear to Linear import job.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains:
            - linearSourceOrganizationId: String! - The source organization to import from
            - id: String (optional) - ID of issue import. If not provided it will be generated

    Returns:
        IssueImport entity representing the created import job
    """
    import uuid

    session: Session = info.context["session"]

    try:
        # Validate required arguments
        source_org_id = kwargs.get("linearSourceOrganizationId")

        if not source_org_id:
            raise ValueError("linearSourceOrganizationId is required")

        # Get optional arguments
        import_id = kwargs.get("id") or str(uuid.uuid4())

        # Create the import job
        now = datetime.now(timezone.utc)

        # Prepare service metadata
        service_metadata = {
            "linearSourceOrganizationId": source_org_id,
        }

        issue_import = IssueImport(
            id=import_id,
            createdAt=now,
            updatedAt=now,
            service="linearV2",
            displayName=f"Linear Import - {source_org_id}",
            status="pending",
            progress=0.0,
            serviceMetadata=service_metadata,
        )

        session.add(issue_import)

        return issue_import

    except ValueError as e:
        raise Exception(f"Invalid input for Linear V2 import: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to create Linear V2 import job: {str(e)}")


@mutation.field("issueImportProcess")
def resolve_issueImportProcess(obj, info, **kwargs):
    """
    Kicks off import processing.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains:
            - issueImportId: String! - ID of the issue import which we're going to process
            - mapping: JSONObject! - The mapping configuration to use for processing the import

    Returns:
        IssueImport entity representing the import job being processed
    """

    session: Session = info.context["session"]

    try:
        # Validate required arguments
        issue_import_id = kwargs.get("issueImportId")
        mapping = kwargs.get("mapping")

        if not issue_import_id:
            raise ValueError("issueImportId is required")
        if not mapping:
            raise ValueError("mapping is required")

        # Fetch the existing import job
        issue_import = session.query(IssueImport).filter_by(id=issue_import_id).first()

        if not issue_import:
            raise ValueError(f"IssueImport with id '{issue_import_id}' not found")

        # Update the import job with the mapping configuration
        issue_import.mapping = mapping
        issue_import.status = "processing"
        issue_import.updatedAt = datetime.now(timezone.utc)
        issue_import.progress = 0.0

        return issue_import

    except ValueError as e:
        raise Exception(f"Invalid input for issue import process: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to process issue import: {str(e)}")


@mutation.field("issueReminder")
def resolve_issueReminder(obj, info, **kwargs):
    """
    Resolver for issueReminder mutation.
    Adds an issue reminder. Will cause a notification to be sent when the issue reminder time is reached.

    Args:
        id: The identifier of the issue to add a reminder for
        reminderAt: The time when a reminder notification will be sent

    Returns:
        IssuePayload with success status and the updated issue entity
    """

    session: Session = info.context["session"]
    issue_id = kwargs.get("id")
    reminder_at = kwargs.get("reminderAt")

    if not issue_id:
        raise Exception("Issue ID is required")
    if not reminder_at:
        raise Exception("reminderAt is required")

    try:
        # Fetch the issue
        issue = session.query(Issue).filter_by(id=issue_id).first()

        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        # Set the reminder time
        issue.reminderAt = reminder_at
        issue.updatedAt = datetime.now(timezone.utc)

        # Return the payload
        return {
            "success": True,
            "issue": issue,
            "lastSyncId": 0.0,  # This would typically come from a sync system
        }

    except Exception as e:
        raise Exception(f"Failed to add issue reminder: {str(e)}")


@mutation.field("issueSubscribe")
def resolve_issueSubscribe(obj, info, **kwargs):
    """
    Resolver for issueSubscribe mutation.
    Subscribes a user to an issue.

    Args:
        id: The identifier of the issue to subscribe to (required)
        userEmail: The email of the user to subscribe (optional, defaults to current user)
        userId: The identifier of the user to subscribe (optional, defaults to current user)

    Returns:
        The updated issue (IssuePayload!)
    """

    session: Session = info.context["session"]
    issue_id = kwargs.get("id")
    user_email = kwargs.get("userEmail")
    user_id = kwargs.get("userId")

    if not issue_id:
        raise Exception("Issue ID is required")

    try:
        # Fetch the issue
        issue = session.query(Issue).filter_by(id=issue_id).first()

        if not issue:
            raise Exception(f"Issue with id {issue_id} not found")

        # Determine which user to subscribe
        user = None

        if user_id:
            # Subscribe by user ID
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                raise Exception(f"User with id {user_id} not found")
        elif user_email:
            # Subscribe by email
            user = session.query(User).filter_by(email=user_email).first()
            if not user:
                raise Exception(f"User with email {user_email} not found")
        else:
            # Default to current user (from context)
            # In a real implementation, you'd get this from info.context['current_user']
            # For now, we'll require either userId or userEmail
            raise Exception("Either userId or userEmail must be provided")

        # Check if the user is already subscribed
        if user in issue.subscribers:
            # User already subscribed, just return the issue
            return issue

        # Subscribe the user to the issue
        issue.subscribers.append(user)

        # Update the updatedAt timestamp
        issue.updatedAt = datetime.now(timezone.utc)

        # Return the updated issue
        return issue

    except Exception as e:
        raise Exception(f"Failed to subscribe user to issue: {str(e)}")


@mutation.field("issueLabelCreate")
def resolve_issueLabelCreate(obj, info, **kwargs):
    """
    Creates a new label.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'input' with IssueLabelCreateInput data and optional 'replaceTeamLabels'

    Returns:
        IssueLabel: The created IssueLabel entity
    """
    import uuid

    session: Session = info.context["session"]
    input_data = kwargs.get("input", {})
    replace_team_labels = kwargs.get("replaceTeamLabels", False)

    try:
        # Extract input fields
        label_id = input_data.get("id") or str(uuid.uuid4())
        name = input_data.get("name")
        color = input_data.get("color", "#000000")  # Default to black if not provided
        description = input_data.get("description")
        is_group = input_data.get("isGroup", False)
        parent_id = input_data.get("parentId")
        retired_at = input_data.get("retiredAt")
        team_id = input_data.get("teamId")

        # Validate required fields
        if not name:
            raise Exception("Label name is required")

        # Determine organization_id
        # If team_id is provided, get organization from team
        # Otherwise, get from user context
        organization_id = None
        if team_id:
            team = session.query(Team).filter_by(id=team_id).first()
            if not team:
                raise Exception(f"Team with id {team_id} not found")
            organization_id = team.organizationId
        else:
            # For workspace-level labels, get organization from authenticated user
            user_id = info.context.get("user_id")
            if not user_id:
                raise Exception(
                    "No authenticated user found. Please provide authentication credentials."
                )

            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise Exception(
                    f"Authenticated user with id '{user_id}' not found in database"
                )

            organization_id = user.organizationId
            if not organization_id:
                raise Exception("User does not have an associated organization")

        # Get current timestamp
        now = datetime.now(timezone.utc)

        # Create the IssueLabel entity
        issue_label = IssueLabel(
            id=label_id,
            name=name,
            color=color,
            description=description,
            isGroup=is_group,
            parentId=parent_id,
            retiredAt=retired_at,
            teamId=team_id,
            organizationId=organization_id,
            createdAt=now,
            updatedAt=now,
        )

        # Add to session
        session.add(issue_label)

        # Handle replaceTeamLabels if requested
        # This would replace all team-specific labels with the same name
        # with this newly created workspace label
        if replace_team_labels and not team_id:
            # Find all team-specific labels with the same name
            team_labels = (
                session.query(IssueLabel)
                .filter(
                    IssueLabel.name == name,
                    IssueLabel.teamId.isnot(None),
                    IssueLabel.organizationId == organization_id,
                )
                .all()
            )

            # Update issues using those labels to use the new workspace label instead
            for team_label in team_labels:
                # Transfer issues from team label to workspace label
                for issue in team_label.issues:
                    if issue_label not in issue.labels:
                        issue.labels.append(issue_label)
                    if team_label in issue.labels:
                        issue.labels.remove(team_label)

                # Archive the old team-specific label
                team_label.archivedAt = now

        # Flush and refresh to load relationships
        session.flush()
        session.refresh(issue_label)

        # Return IssueLabelPayload
        return {
            "success": True,
            "issueLabel": issue_label,
            "lastSyncId": float(now.timestamp()),
        }

    except Exception as e:
        raise Exception(f"Failed to create issue label: {str(e)}")


@mutation.field("issueLabelUpdate")
def resolve_issueLabelUpdate(obj, info, **kwargs):
    """
    Updates an existing label.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (label identifier), 'input' with IssueLabelUpdateInput data,
                 and optional 'replaceTeamLabels'

    Returns:
        IssueLabel: The updated IssueLabel entity
    """

    session: Session = info.context["session"]
    label_id = kwargs.get("id")
    input_data = kwargs.get("input", {})
    replace_team_labels = kwargs.get("replaceTeamLabels", False)

    try:
        # Validate required field
        if not label_id:
            raise Exception("Label id is required")

        # Find the label to update
        issue_label = session.query(IssueLabel).filter_by(id=label_id).first()
        if not issue_label:
            raise Exception(f"IssueLabel with id {label_id} not found")

        # Store original values for replaceTeamLabels logic
        original_name = issue_label.name
        original_team_id = issue_label.teamId

        # Update fields if provided in input
        if "color" in input_data:
            issue_label.color = input_data["color"]

        if "description" in input_data:
            issue_label.description = input_data["description"]

        if "isGroup" in input_data:
            issue_label.isGroup = input_data["isGroup"]

        if "name" in input_data:
            issue_label.name = input_data["name"]

        if "parentId" in input_data:
            issue_label.parentId = input_data["parentId"]

        if "retiredAt" in input_data:
            issue_label.retiredAt = input_data["retiredAt"]

        # Update timestamp
        now = datetime.now(timezone.utc)
        issue_label.updatedAt = now

        # Handle replaceTeamLabels if requested
        # This replaces all team-specific labels with the same name with this updated workspace label
        if replace_team_labels and issue_label.teamId is None:
            # Find all team-specific labels with the same name
            team_labels = (
                session.query(IssueLabel)
                .filter(
                    IssueLabel.name == issue_label.name,
                    IssueLabel.teamId.isnot(None),
                    IssueLabel.organizationId == issue_label.organizationId,
                    IssueLabel.id != issue_label.id,  # Exclude the current label
                )
                .all()
            )

            # Update issues using those labels to use the workspace label instead
            for team_label in team_labels:
                # Transfer issues from team label to workspace label
                for issue in team_label.issues:
                    if issue_label not in issue.labels:
                        issue.labels.append(issue_label)
                    if team_label in issue.labels:
                        issue.labels.remove(team_label)

                # Archive the old team-specific label
                team_label.archivedAt = now
                team_label.updatedAt = now

        # Flush and refresh
        session.flush()
        session.refresh(issue_label)

        # Return IssueLabelPayload
        return {
            "success": True,
            "issueLabel": issue_label,
            "lastSyncId": float(now.timestamp()),
        }

    except Exception as e:
        raise Exception(f"Failed to update issue label: {str(e)}")


@mutation.field("issueLabelDelete")
def resolve_issueLabelDelete(obj, info, **kwargs):
    """
    Deletes an issue label.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' - the identifier of the label to delete

    Returns:
        Dict: DeletePayload with success status and entityId
    """

    session: Session = info.context["session"]
    label_id = kwargs.get("id")

    try:
        # Validate required field
        if not label_id:
            raise Exception("Label id is required")

        # Find the label to delete
        issue_label = session.query(IssueLabel).filter_by(id=label_id).first()
        if not issue_label:
            raise Exception(f"IssueLabel with id {label_id} not found")

        # Soft delete by setting archivedAt timestamp
        now = datetime.now(timezone.utc)
        issue_label.archivedAt = now
        issue_label.updatedAt = now

        # Return DeletePayload
        return {
            "success": True,
            "entityId": label_id,
            "lastSyncId": 0.0,  # This would be managed by Linear's sync system
        }

    except Exception as e:
        raise Exception(f"Failed to delete issue label: {str(e)}")


# ============================================================================
# IssueRelation Mutations
# ============================================================================


@mutation.field("issueRelationCreate")
def resolve_issueRelationCreate(obj, info, **kwargs):
    """
    Creates a new issue relation.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'input' with IssueRelationCreateInput data and optional 'overrideCreatedAt'

    Returns:
        The created IssueRelation entity
    """
    import uuid

    session: Session = info.context["session"]
    input_data = kwargs.get("input", {})
    override_created_at = kwargs.get("overrideCreatedAt")

    try:
        # Extract input fields
        issue_relation_id = input_data.get("id") or str(uuid.uuid4())
        issue_id = input_data["issueId"]  # Required
        related_issue_id = input_data["relatedIssueId"]  # Required
        relation_type = input_data["type"]  # Required

        # Generate timestamps
        now = override_created_at if override_created_at else datetime.now(timezone.utc)

        # Create the IssueRelation entity
        issue_relation = IssueRelation(
            id=issue_relation_id,
            issueId=issue_id,
            relatedIssueId=related_issue_id,
            type=relation_type,
            createdAt=now,
            updatedAt=now,
            archivedAt=None,
        )

        session.add(issue_relation)

        # Return the proper IssueRelationPayload structure
        return {"success": True, "lastSyncId": 0.0, "issueRelation": issue_relation}

    except KeyError as e:
        raise Exception(f"Missing required field: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to create issue relation: {str(e)}")


@mutation.field("issueRelationUpdate")
def resolve_issueRelationUpdate(obj, info, **kwargs):
    """
    Updates an existing issue relation.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (String!) and 'input' with IssueRelationUpdateInput data

    Returns:
        The updated IssueRelation entity
    """

    session: Session = info.context["session"]
    relation_id = kwargs.get("id")
    input_data = kwargs.get("input", {})

    if not relation_id:
        raise Exception("Missing required field: id")

    try:
        # Query for the existing issue relation
        issue_relation = session.query(IssueRelation).filter_by(id=relation_id).first()

        if not issue_relation:
            raise Exception(f"IssueRelation with id '{relation_id}' not found")

        # Update fields if provided in input
        if "issueId" in input_data:
            issue_relation.issueId = input_data["issueId"]

        if "relatedIssueId" in input_data:
            issue_relation.relatedIssueId = input_data["relatedIssueId"]

        if "type" in input_data:
            issue_relation.type = input_data["type"]

        # Always update the updatedAt timestamp
        issue_relation.updatedAt = datetime.now(timezone.utc)

        # Return the proper IssueRelationPayload structure
        return {"success": True, "lastSyncId": 0.0, "issueRelation": issue_relation}

    except Exception as e:
        raise Exception(f"Failed to update issue relation: {str(e)}")


@mutation.field("issueRelationDelete")
def resolve_issueRelationDelete(obj, info, **kwargs):
    """
    Deletes an issue relation.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (String!) - identifier of the issue relation to delete

    Returns:
        DeletePayload with success status and entityId
    """

    session: Session = info.context["session"]
    relation_id = kwargs.get("id")

    if not relation_id:
        return {"success": False, "entityId": "", "lastSyncId": 0.0}

    try:
        # Query for the issue relation
        issue_relation = session.query(IssueRelation).filter_by(id=relation_id).first()

        if not issue_relation:
            return {"success": False, "entityId": relation_id, "lastSyncId": 0.0}

        # Soft delete by setting archivedAt timestamp
        issue_relation.archivedAt = datetime.now(timezone.utc)
        issue_relation.updatedAt = datetime.now(timezone.utc)

        # Return success payload
        return {
            "success": True,
            "entityId": relation_id,
            "lastSyncId": 0.0,  # This would typically be incremented from a sync counter
        }

    except Exception as e:
        raise Exception(f"Failed to delete issue relation: {str(e)}")


@mutation.field("userPromoteAdmin")
def resolve_userPromoteAdmin(obj, info, **kwargs):
    """
    Makes user an admin. Can only be called by an admin.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (String!) - identifier of the user to make an admin

    Returns:
        UserAdminPayload with success status
    """
    session: Session = info.context["session"]
    user_id = kwargs.get("id")

    if not user_id:
        return {"success": False}

    try:
        # Query for the user
        user = session.query(User).filter_by(id=user_id).first()

        if not user:
            raise Exception(f"User with id {user_id} not found")

        # Promote the user by setting admin to True
        user.admin = True

        # Return success payload
        return {"success": True}

    except Exception as e:
        raise Exception(f"Failed to promote user to admin: {str(e)}")


@mutation.field("userDemoteAdmin")
def resolve_userDemoteAdmin(obj, info, **kwargs):
    """
    Makes user a regular user. Can only be called by an admin.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (String!) - identifier of the user to demote

    Returns:
        UserAdminPayload with success status
    """
    session: Session = info.context["session"]
    user_id = kwargs.get("id")

    if not user_id:
        return {"success": False}

    try:
        # Query for the user
        user = session.query(User).filter_by(id=user_id).first()

        if not user:
            raise Exception(f"User with id {user_id} not found")

        # Demote the user by setting admin to False
        user.admin = False

        # Return success payload
        return {"success": True}

    except Exception as e:
        raise Exception(f"Failed to demote user admin: {str(e)}")


@mutation.field("userDemoteMember")
def resolve_userDemoteMember(obj, info, **kwargs):
    """
    Makes user a guest. Can only be called by an admin.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (String!) - identifier of the user to make a guest

    Returns:
        UserAdminPayload with success status
    """
    session: Session = info.context["session"]
    user_id = kwargs.get("id")

    if not user_id:
        return {"success": False}

    try:
        # Query for the user
        user = session.query(User).filter_by(id=user_id).first()

        if not user:
            raise Exception(f"User with id {user_id} not found")

        # Demote the user to guest by setting guest to True
        user.guest = True

        # Return success payload
        return {"success": True}

    except Exception as e:
        raise Exception(f"Failed to demote user to member/guest: {str(e)}")


@mutation.field("userPromoteMember")
def resolve_userPromoteMember(obj, info, **kwargs):
    """
    Makes user a regular user. Can only be called by an admin.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (String!) - identifier of the user to make a regular user

    Returns:
        UserAdminPayload with success status
    """
    session: Session = info.context["session"]
    user_id = kwargs.get("id")

    if not user_id:
        return {"success": False}

    try:
        # Query for the user
        user = session.query(User).filter_by(id=user_id).first()

        if not user:
            raise Exception(f"User with id {user_id} not found")

        # Promote the user from guest to regular member by setting guest to False
        user.guest = False

        # Return success payload
        return {"success": True}

    except Exception as e:
        raise Exception(f"Failed to promote user to member: {str(e)}")


@mutation.field("userSuspend")
def resolve_userSuspend(obj, info, **kwargs):
    """
    Suspends a user. Can only be called by an admin.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (String!) - identifier of the user to suspend

    Returns:
        UserAdminPayload with success status
    """
    session: Session = info.context["session"]
    user_id = kwargs.get("id")

    if not user_id:
        return {"success": False}

    try:
        # Query for the user
        user = session.query(User).filter_by(id=user_id).first()

        if not user:
            raise Exception(f"User with id {user_id} not found")

        # Suspend the user by setting active to False
        user.active = False

        # Return success payload
        return {"success": True}

    except Exception as e:
        raise Exception(f"Failed to suspend user: {str(e)}")


@mutation.field("userUnsuspend")
def resolve_userUnsuspend(obj, info, **kwargs):
    """
    Un-suspends a user. Can only be called by an admin.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (String!) - identifier of the user to unsuspend

    Returns:
        UserAdminPayload with success status
    """
    session: Session = info.context["session"]
    user_id = kwargs.get("id")

    if not user_id:
        return {"success": False}

    try:
        # Query for the user
        user = session.query(User).filter_by(id=user_id).first()

        if not user:
            raise Exception(f"User with id {user_id} not found")

        # Unsuspend the user by setting active to True
        user.active = True

        # Return success payload
        return {"success": True}

    except Exception as e:
        raise Exception(f"Failed to unsuspend user: {str(e)}")


@mutation.field("userUnlinkFromIdentityProvider")
def resolve_userUnlinkFromIdentityProvider(obj, info, **kwargs):
    """
    Unlinks a guest user from their identity provider. Can only be called by an admin when SCIM is enabled.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (String!) - identifier of the guest user to unlink from their identity provider

    Returns:
        UserAdminPayload with success status
    """
    session: Session = info.context["session"]
    user_id = kwargs.get("id")

    if not user_id:
        return {"success": False}

    try:
        # Query for the user
        user = session.query(User).filter_by(id=user_id).first()

        if not user:
            raise Exception(f"User with id {user_id} not found")

        # Verify user is a guest
        if not user.guest:
            raise Exception(f"User with id {user_id} is not a guest user")

        # Unlink from identity provider by clearing identity provider fields
        # This includes clearing any OAuth/SSO identity provider connections
        user.gitHubUserId = None
        user.discordUserId = None

        # Return success payload
        return {"success": True}

    except Exception as e:
        raise Exception(f"Failed to unlink user from identity provider: {str(e)}")


@mutation.field("userDiscordConnect")
def resolve_userDiscordConnect(obj, info, **kwargs):
    """
    Connects the Discord user to this Linear account via OAuth2.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains:
            - code (String!): The Discord OAuth code
            - redirectUri (String!): The Discord OAuth redirect URI

    Returns:
        UserPayload with the updated user object
    """
    session: Session = info.context["session"]
    code = kwargs.get("code")
    redirect_uri = kwargs.get("redirectUri")

    if not code:
        raise Exception("Discord OAuth code is required")

    if not redirect_uri:
        raise Exception("Discord OAuth redirect URI is required")

    try:
        # In a real implementation, we would:
        # 1. Exchange the OAuth code for an access token with Discord API
        # 2. Use the access token to fetch the Discord user information
        # 3. Store the Discord user ID on the current user

        # For this implementation, we'll simulate the OAuth flow
        # In production, you would make requests to:
        # - POST https://discord.com/api/oauth2/token (to exchange code for token)
        # - GET https://discord.com/api/users/@me (to get Discord user info)

        # Get the current user from context (assuming authentication middleware sets this)
        current_user_id = info.context.get("user_id")

        if not current_user_id:
            raise Exception("User must be authenticated to connect Discord account")

        # Query for the current user
        user = session.query(User).filter_by(id=current_user_id).first()

        if not user:
            raise Exception(f"User with id {current_user_id} not found")

        # Simulate Discord OAuth flow
        # In a real implementation, this would be the Discord user ID returned from the API
        # For now, we'll generate a placeholder value based on the code
        discord_user_id = f"discord_{code[:16]}"

        # Check if Discord account is already connected to another user
        existing_user = (
            session.query(User).filter_by(discordUserId=discord_user_id).first()
        )
        if existing_user and existing_user.id != user.id:
            raise Exception(
                "This Discord account is already connected to another Linear account"
            )

        # Connect the Discord account to the user
        user.discordUserId = discord_user_id

        # Return the updated user in a UserPayload format
        return {"success": True, "user": user}

    except Exception as e:
        raise Exception(f"Failed to connect Discord account: {str(e)}")


@mutation.field("userExternalUserDisconnect")
def resolve_userExternalUserDisconnect(obj, info, **kwargs):
    """
    Disconnects the external user from this Linear account.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains:
            - service (String!): The external service to disconnect (e.g., "github", "discord")

    Returns:
        UserPayload with the updated user object
    """
    session: Session = info.context["session"]
    service = kwargs.get("service")

    if not service:
        raise Exception("Service name is required")

    try:
        # Get the current user from context (assuming authentication middleware sets this)
        current_user_id = info.context.get("user_id")

        if not current_user_id:
            raise Exception("User must be authenticated to disconnect external account")

        # Query for the current user
        user = session.query(User).filter_by(id=current_user_id).first()

        if not user:
            raise Exception(f"User with id {current_user_id} not found")

        # Normalize service name to lowercase for comparison
        service_lower = service.lower()

        # Disconnect the appropriate external service
        if service_lower == "github":
            if not user.gitHubUserId:
                raise Exception("GitHub account is not connected to this user")
            user.gitHubUserId = None
        elif service_lower == "discord":
            if not user.discordUserId:
                raise Exception("Discord account is not connected to this user")
            user.discordUserId = None
        else:
            raise Exception(
                f"Unknown external service: {service}. Supported services: github, discord"
            )

        # Return the updated user in a UserPayload format
        return {"success": True, "user": user}

    except Exception as e:
        raise Exception(f"Failed to disconnect external account: {str(e)}")


@mutation.field("userFlagUpdate")
def resolve_userFlagUpdate(obj, info, **kwargs):
    """
    Updates a user's settings flag.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains:
            - flag: UserFlagType! - The flag to update
            - operation: UserFlagUpdateOperation! - The operation to perform (incr/decr/clear/lock)

    Returns:
        UserSettingsFlagPayload with:
            - success: Boolean! - Whether the operation was successful
            - lastSyncId: Float! - The identifier of the last sync operation
            - flag: String - The flag key which was updated
            - value: Int - The flag value after update
    """
    session = info.context["session"]

    try:
        # Get the current user from context (assuming authentication middleware sets this)
        current_user_id = info.context.get("user_id")

        if not current_user_id:
            raise Exception("User must be authenticated to update flags")

        # Extract arguments
        flag = kwargs.get("flag")
        operation = kwargs.get("operation")

        if not flag or not operation:
            raise Exception("Both 'flag' and 'operation' arguments are required")

        # Query for existing flag or create new one
        user_flag = (
            session.query(UserFlag).filter_by(userId=current_user_id, flag=flag).first()
        )

        # Generate a new sync ID (incrementing timestamp)
        new_sync_id = datetime.utcnow().timestamp()

        if user_flag is None:
            # Create new flag entry
            user_flag = UserFlag(
                id=str(uuid.uuid4()),
                userId=current_user_id,
                flag=flag,
                value=0,
                lastSyncId=new_sync_id,
                createdAt=datetime.utcnow(),
                updatedAt=datetime.utcnow(),
            )
            session.add(user_flag)

        # Apply the operation
        if operation == "incr":
            user_flag.value += 1
        elif operation == "decr":
            user_flag.value = max(0, user_flag.value - 1)  # Don't go below 0
        elif operation == "clear":
            user_flag.value = 0
        elif operation == "lock":
            # Lock operation sets value to a high number (commonly used to prevent further changes)
            user_flag.value = 999999
        else:
            raise Exception(f"Unknown operation: {operation}")

        # Update metadata
        user_flag.lastSyncId = new_sync_id
        user_flag.updatedAt = datetime.utcnow()

        # Return the payload
        return {
            "success": True,
            "lastSyncId": user_flag.lastSyncId,
            "flag": user_flag.flag,
            "value": user_flag.value,
        }

    except Exception as e:
        raise Exception(f"Failed to update user flag: {str(e)}")


@mutation.field("userSettingsFlagsReset")
def resolve_userSettingsFlagsReset(obj, info, **kwargs):
    """
    Reset user's setting flags.

    This mutation resets one or more user flags to their default state (value=0).
    If no flags are specified, all flags for the user will be reset.

    Arguments:
        - flags: [UserFlagType!] (optional) - The flags to reset. If not provided, all flags will be reset.

    Returns:
        UserSettingsFlagsResetPayload with:
            - success: Boolean! - Whether the operation was successful
            - lastSyncId: Float! - The identifier of the last sync operation
    """
    session = info.context["session"]

    try:
        # Get the current user from context
        current_user_id = info.context.get("user_id")

        if not current_user_id:
            raise Exception("User must be authenticated to reset flags")

        # Extract the flags argument (optional)
        flags_to_reset = kwargs.get("flags")

        # Generate a new sync ID
        new_sync_id = datetime.utcnow().timestamp()

        if flags_to_reset:
            # Reset specific flags
            for flag in flags_to_reset:
                # Query for existing flag
                user_flag = (
                    session.query(UserFlag)
                    .filter_by(userId=current_user_id, flag=flag)
                    .first()
                )

                if user_flag is None:
                    # Create new flag entry with default value
                    user_flag = UserFlag(
                        id=str(uuid.uuid4()),
                        userId=current_user_id,
                        flag=flag,
                        value=0,
                        lastSyncId=new_sync_id,
                        createdAt=datetime.utcnow(),
                        updatedAt=datetime.utcnow(),
                    )
                    session.add(user_flag)
                else:
                    # Reset existing flag to 0
                    user_flag.value = 0
                    user_flag.lastSyncId = new_sync_id
                    user_flag.updatedAt = datetime.utcnow()
        else:
            # Reset all flags for the user
            user_flags = session.query(UserFlag).filter_by(userId=current_user_id).all()

            for user_flag in user_flags:
                user_flag.value = 0
                user_flag.lastSyncId = new_sync_id
                user_flag.updatedAt = datetime.utcnow()

        # Create and return the payload
        # Return the proper UserSettingsFlagsResetPayload structure
        return {"success": True, "lastSyncId": new_sync_id}

    except Exception as e:
        raise Exception(f"Failed to reset user flags: {str(e)}")


@mutation.field("userSettingsUpdate")
def resolve_userSettingsUpdate(obj, info, **kwargs):
    """
    Updates the user's settings.

    Arguments:
        - id: String! - The identifier of the userSettings to update
        - input: UserSettingsUpdateInput! - A partial notification object to update the settings with

    Returns:
        UserSettingsPayload! with the updated UserSettings entity
    """
    session = info.context["session"]

    try:
        # Extract arguments
        settings_id = kwargs.get("id")
        input_data = kwargs.get("input", {})

        if not settings_id:
            raise Exception("User settings ID is required")

        # Query for existing user settings
        user_settings = session.query(UserSettings).filter_by(id=settings_id).first()

        if not user_settings:
            raise Exception(f"UserSettings with id '{settings_id}' not found")

        # Update fields from input
        # Handle optional fields - only update if provided in input
        if "feedSummarySchedule" in input_data:
            user_settings.feedSummarySchedule = input_data["feedSummarySchedule"]

        if "notificationCategoryPreferences" in input_data:
            user_settings.notificationCategoryPreferences = input_data[
                "notificationCategoryPreferences"
            ]

        if "notificationChannelPreferences" in input_data:
            user_settings.notificationChannelPreferences = input_data[
                "notificationChannelPreferences"
            ]

        if "notificationDeliveryPreferences" in input_data:
            user_settings.notificationDeliveryPreferences = input_data[
                "notificationDeliveryPreferences"
            ]

        if "settings" in input_data:
            user_settings.settings = input_data["settings"]

        if "subscribedToChangelog" in input_data:
            user_settings.subscribedToChangelog = input_data["subscribedToChangelog"]

        if "subscribedToDPA" in input_data:
            user_settings.subscribedToDPA = input_data["subscribedToDPA"]

        if "subscribedToGeneralMarketingCommunications" in input_data:
            user_settings.subscribedToGeneralMarketingCommunications = input_data[
                "subscribedToGeneralMarketingCommunications"
            ]

        if "subscribedToInviteAccepted" in input_data:
            user_settings.subscribedToInviteAccepted = input_data[
                "subscribedToInviteAccepted"
            ]

        if "subscribedToPrivacyLegalUpdates" in input_data:
            user_settings.subscribedToPrivacyLegalUpdates = input_data[
                "subscribedToPrivacyLegalUpdates"
            ]

        if "unsubscribedFrom" in input_data:
            # This field is deprecated but still supported
            user_settings.unsubscribedFrom = input_data["unsubscribedFrom"]

        if "usageWarningHistory" in input_data:
            user_settings.usageWarningHistory = input_data["usageWarningHistory"]

        # Update the updatedAt timestamp
        user_settings.updatedAt = datetime.utcnow()

        return user_settings

    except Exception as e:
        raise Exception(f"Failed to update user settings: {str(e)}")


@mutation.field("userUpdate")
def resolve_userUpdate(obj, info, **kwargs):
    """
    Updates a user. Only available to organization admins and the user themselves.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains:
            - id: String! - The identifier of the user to update. Use `me` to reference currently authenticated user.
            - input: UserUpdateInput! - A partial user object to update the user with

    Returns:
        UserPayload with:
            - success: Boolean
            - user: User - The updated user object
    """

    session: Session = info.context["session"]
    user_id = kwargs.get("id")
    input_data = kwargs.get("input", {})

    try:
        # Validate required parameters
        if not user_id:
            raise ValueError("User ID is required")

        # Handle 'me' as a special identifier for the current user
        if user_id == "me":
            current_user_id = info.context.get("user_id")
            if not current_user_id:
                raise ValueError(
                    "Cannot use 'me' identifier: user is not authenticated"
                )
            user_id = current_user_id

        # Query for the user to update
        user = session.query(User).filter_by(id=user_id).first()

        if not user:
            raise ValueError(f"User not found with ID: {user_id}")

        # Update optional fields from UserUpdateInput
        if "avatarUrl" in input_data:
            user.avatarUrl = input_data["avatarUrl"]

        if "description" in input_data:
            user.description = input_data["description"]

        if "displayName" in input_data:
            user.displayName = input_data["displayName"]

        if "name" in input_data:
            user.name = input_data["name"]

        if "statusEmoji" in input_data:
            user.statusEmoji = input_data["statusEmoji"]

        if "statusLabel" in input_data:
            user.statusLabel = input_data["statusLabel"]

        if "statusUntilAt" in input_data:
            user.statusUntilAt = input_data["statusUntilAt"]

        if "timezone" in input_data:
            user.timezone = input_data["timezone"]

        # Always update the updatedAt timestamp
        user.updatedAt = datetime.now(timezone.utc)

        # Return the UserPayload
        return {"success": True, "user": user}

    except ValueError as e:
        raise Exception(f"Invalid input for user update: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to update user: {str(e)}")


@mutation.field("notificationArchive")
def resolve_notificationArchive(obj, info, **kwargs):
    """
    Resolver for notificationArchive mutation.
    Archives a notification.

    Args:
        id: The id of the notification to archive

    Returns:
        NotificationArchivePayload with success status and the archived entity
    """

    session: Session = info.context["session"]
    notification_id = kwargs.get("id")

    if not notification_id:
        raise Exception("Notification ID is required")

    try:
        # Fetch the notification
        notification = session.query(Notification).filter_by(id=notification_id).first()

        if not notification:
            raise Exception(f"Notification with id {notification_id} not found")

        # Soft delete: set archivedAt timestamp
        if notification.archivedAt is None:
            notification.archivedAt = datetime.now(timezone.utc)

        # Return the payload
        return {
            "success": True,
            "entity": notification,
            "lastSyncId": 0.0,  # This would typically come from a sync system
        }

    except Exception as e:
        raise Exception(f"Failed to archive notification: {str(e)}")


@mutation.field("notificationUnarchive")
def resolve_notificationUnarchive(obj, info, **kwargs):
    """
    Resolver for notificationUnarchive mutation.
    Unarchives a notification.

    Args:
        id: The id of the notification to unarchive

    Returns:
        NotificationArchivePayload with success status and the unarchived entity
    """

    session: Session = info.context["session"]
    notification_id = kwargs.get("id")

    if not notification_id:
        raise Exception("Notification ID is required")

    try:
        # Fetch the notification
        notification = session.query(Notification).filter_by(id=notification_id).first()

        if not notification:
            raise Exception(f"Notification with id {notification_id} not found")

        # Unarchive: clear archivedAt timestamp
        notification.archivedAt = None

        # Return the payload
        return {
            "success": True,
            "entity": notification,
            "lastSyncId": 0.0,  # This would typically come from a sync system
        }

    except Exception as e:
        raise Exception(f"Failed to unarchive notification: {str(e)}")


@mutation.field("notificationUpdate")
def resolve_notificationUpdate(obj, info, **kwargs):
    """
    Resolver for notificationUpdate mutation.
    Updates a notification.

    Args:
        id: The identifier of the notification to update
        input: A partial notification object to update the notification with

    Returns:
        NotificationPayload with success status and the updated entity
    """

    session: Session = info.context["session"]
    notification_id = kwargs.get("id")
    input_data = kwargs.get("input", {})

    if not notification_id:
        raise Exception("Notification ID is required")

    if not input_data:
        raise Exception("Input data is required")

    try:
        # Fetch the notification
        notification = session.query(Notification).filter_by(id=notification_id).first()

        if not notification:
            raise Exception(f"Notification with id {notification_id} not found")

        # Update fields from input
        if "readAt" in input_data:
            notification.readAt = input_data["readAt"]

        if "snoozedUntilAt" in input_data:
            notification.snoozedUntilAt = input_data["snoozedUntilAt"]

        if "initiativeUpdateId" in input_data:
            notification.initiativeUpdateId = input_data["initiativeUpdateId"]

        if "projectUpdateId" in input_data:
            notification.projectUpdateId = input_data["projectUpdateId"]

        # Update the updatedAt timestamp
        notification.updatedAt = datetime.now(timezone.utc)

        # Return the payload
        return {
            "success": True,
            "notification": notification,
            "lastSyncId": 0.0,  # This would typically come from a sync system
        }

    except Exception as e:
        raise Exception(f"Failed to update notification: {str(e)}")


@mutation.field("notificationArchiveAll")
def resolve_notificationArchiveAll(obj, info, **kwargs):
    """
    Resolver for notificationArchiveAll mutation.
    Archives a notification and all related notifications.

    Args:
        input: NotificationEntityInput containing the entity type and id

    Returns:
        NotificationBatchActionPayload with success status, notifications list, and lastSyncId
    """

    session: Session = info.context["session"]
    input_data = kwargs.get("input")

    if not input_data:
        raise Exception("Input is required")

    try:
        # Extract entity identifiers from input
        notification_id = input_data.get("id")
        issue_id = input_data.get("issueId")
        initiative_id = input_data.get("initiativeId")
        initiative_update_id = input_data.get("initiativeUpdateId")
        project_id = input_data.get("projectId")
        project_update_id = input_data.get("projectUpdateId")
        oauth_client_approval_id = input_data.get("oauthClientApprovalId")

        # Build the query based on which entity ID was provided
        query = session.query(Notification)

        if notification_id:
            query = query.filter(Notification.id == notification_id)
        elif issue_id:
            query = query.filter(Notification.issueId == issue_id)
        elif initiative_id:
            query = query.filter(Notification.initiativeId == initiative_id)
        elif initiative_update_id:
            query = query.filter(
                Notification.initiativeUpdateId == initiative_update_id
            )
        elif project_id:
            query = query.filter(Notification.projectId == project_id)
        elif project_update_id:
            query = query.filter(Notification.projectUpdateId == project_update_id)
        elif oauth_client_approval_id:
            query = query.filter(
                Notification.oauthClientApprovalId == oauth_client_approval_id
            )
        else:
            raise Exception("At least one entity identifier must be provided")

        # Fetch all matching notifications
        notifications = query.all()

        if not notifications:
            # No notifications found, but still return success
            return {"success": True, "notifications": [], "lastSyncId": 0.0}

        # Archive all matching notifications by setting archivedAt timestamp
        now = datetime.now(timezone.utc)
        for notification in notifications:
            if notification.archivedAt is None:
                notification.archivedAt = now

        # Return the payload
        return {
            "success": True,
            "notifications": notifications,
            "lastSyncId": 0.0,  # This would typically come from a sync system
        }

    except Exception as e:
        raise Exception(f"Failed to archive notifications: {str(e)}")


# ============================================================================
# NotificationCategoryChannelSubscription Mutations
# ============================================================================


@mutation.field("notificationCategoryChannelSubscriptionUpdate")
def resolve_notificationCategoryChannelSubscriptionUpdate(
    obj, info, category, channel, subscribe
):
    """
    Subscribe to or unsubscribe from a notification category for a given notification channel.

    Args:
        category: NotificationCategory enum value (e.g., 'assignments', 'mentions', 'statusChanges')
        channel: NotificationChannel enum value (e.g., 'email', 'desktop', 'mobile', 'slack')
        subscribe: True to subscribe, False to unsubscribe

    Returns:
        UserSettingsPayload with success status and updated UserSettings object
    """
    session: Session = info.context["session"]

    try:
        # Get the current user from context
        # In a real implementation, this would come from authentication context
        # For now, we'll assume there's a user_id in the context or we need to get it somehow
        user_id = info.context.get("user_id")
        if not user_id:
            raise Exception("User not authenticated")

        # Get or create the user's settings
        user_settings = session.query(UserSettings).filter_by(userId=user_id).first()

        if not user_settings:
            # Create new settings if they don't exist
            now = datetime.now(timezone.utc)
            user_settings = UserSettings(
                id=str(uuid.uuid4()),
                userId=user_id,
                createdAt=now,
                updatedAt=now,
                notificationChannelPreferences={},
                notificationCategoryPreferences={},
                notificationDeliveryPreferences={},
            )
            session.add(user_settings)

        # Update the notification preferences
        # The structure is typically: channelPreferences[channel][category] = boolean
        if user_settings.notificationChannelPreferences is None:
            user_settings.notificationChannelPreferences = {}

        if channel not in user_settings.notificationChannelPreferences:
            user_settings.notificationChannelPreferences[channel] = {}

        # Set the subscription preference for this category on this channel
        user_settings.notificationChannelPreferences[channel][category] = subscribe

        # Also update the category preferences to track overall category subscriptions
        if user_settings.notificationCategoryPreferences is None:
            user_settings.notificationCategoryPreferences = {}

        if category not in user_settings.notificationCategoryPreferences:
            user_settings.notificationCategoryPreferences[category] = {}

        user_settings.notificationCategoryPreferences[category][channel] = subscribe

        # Update the timestamp
        user_settings.updatedAt = datetime.now(timezone.utc)

        # Return the payload
        return {
            "success": True,
            "userSettings": user_settings,
            "lastSyncId": 0.0,  # This would typically come from a sync system
        }

    except Exception as e:
        raise Exception(f"Failed to update notification subscription: {str(e)}")


@mutation.field("notificationMarkReadAll")
def resolve_notificationMarkReadAll(obj, info, **kwargs):
    """
    Resolver for notificationMarkReadAll mutation.
    Marks notification and all related notifications as read.

    Args:
        input: NotificationEntityInput containing the entity type and id
        readAt: DateTime timestamp when notification was marked as read

    Returns:
        NotificationBatchActionPayload with success status, notifications list, and lastSyncId
    """
    session: Session = info.context["session"]
    input_data = kwargs.get("input")
    read_at = kwargs.get("readAt")

    if not input_data:
        raise Exception("Input is required")

    if not read_at:
        raise Exception("readAt timestamp is required")

    try:
        # Extract entity identifiers from input
        notification_id = input_data.get("id")
        issue_id = input_data.get("issueId")
        initiative_id = input_data.get("initiativeId")
        initiative_update_id = input_data.get("initiativeUpdateId")
        project_id = input_data.get("projectId")
        project_update_id = input_data.get("projectUpdateId")
        oauth_client_approval_id = input_data.get("oauthClientApprovalId")

        # Build the query based on which entity ID was provided
        query = session.query(Notification)

        if notification_id:
            query = query.filter(Notification.id == notification_id)
        elif issue_id:
            query = query.filter(Notification.issueId == issue_id)
        elif initiative_id:
            query = query.filter(Notification.initiativeId == initiative_id)
        elif initiative_update_id:
            query = query.filter(
                Notification.initiativeUpdateId == initiative_update_id
            )
        elif project_id:
            query = query.filter(Notification.projectId == project_id)
        elif project_update_id:
            query = query.filter(Notification.projectUpdateId == project_update_id)
        elif oauth_client_approval_id:
            query = query.filter(
                Notification.oauthClientApprovalId == oauth_client_approval_id
            )
        else:
            raise Exception("At least one entity identifier must be provided")

        # Fetch all matching notifications
        notifications = query.all()

        if not notifications:
            # No notifications found, but still return success
            return {"success": True, "notifications": [], "lastSyncId": 0.0}

        # Create a NotificationBatchActionPayload to track this batch operation
        # Mark all matching notifications as read
        # Convert readAt to datetime if it's a string
        if isinstance(read_at, str):
            read_at_dt = datetime.fromisoformat(read_at.replace("Z", "+00:00"))
        else:
            read_at_dt = read_at

        for notification in notifications:
            if notification.readAt is None:
                notification.readAt = read_at_dt

        # Return the proper NotificationBatchActionPayload structure
        return {"success": True, "notifications": notifications, "lastSyncId": 0.0}

    except Exception as e:
        raise Exception(f"Failed to mark notifications as read: {str(e)}")


@mutation.field("notificationMarkUnreadAll")
def resolve_notificationMarkUnreadAll(obj, info, **kwargs):
    """
    Resolver for notificationMarkUnreadAll mutation.
    Marks notification and all related notifications as unread.

    Args:
        input: NotificationEntityInput containing the entity type and id

    Returns:
        NotificationBatchActionPayload with success status, notifications list, and lastSyncId
    """
    session: Session = info.context["session"]
    input_data = kwargs.get("input")

    if not input_data:
        raise Exception("Input is required")

    try:
        # Extract entity identifiers from input
        notification_id = input_data.get("id")
        issue_id = input_data.get("issueId")
        initiative_id = input_data.get("initiativeId")
        initiative_update_id = input_data.get("initiativeUpdateId")
        project_id = input_data.get("projectId")
        project_update_id = input_data.get("projectUpdateId")
        oauth_client_approval_id = input_data.get("oauthClientApprovalId")

        # Build the query based on which entity ID was provided
        query = session.query(Notification)

        if notification_id:
            query = query.filter(Notification.id == notification_id)
        elif issue_id:
            query = query.filter(Notification.issueId == issue_id)
        elif initiative_id:
            query = query.filter(Notification.initiativeId == initiative_id)
        elif initiative_update_id:
            query = query.filter(
                Notification.initiativeUpdateId == initiative_update_id
            )
        elif project_id:
            query = query.filter(Notification.projectId == project_id)
        elif project_update_id:
            query = query.filter(Notification.projectUpdateId == project_update_id)
        elif oauth_client_approval_id:
            query = query.filter(
                Notification.oauthClientApprovalId == oauth_client_approval_id
            )
        else:
            raise Exception("At least one entity identifier must be provided")

        # Fetch all matching notifications
        notifications = query.all()

        if not notifications:
            # No notifications found, but still return success
            return {"success": True, "notifications": [], "lastSyncId": 0.0}

        # Mark all matching notifications as unread by clearing readAt
        for notification in notifications:
            notification.readAt = None

        # Return the proper NotificationBatchActionPayload structure
        return {"success": True, "notifications": notifications, "lastSyncId": 0.0}

    except Exception as e:
        raise Exception(f"Failed to mark notifications as unread: {str(e)}")


@mutation.field("notificationSnoozeAll")
def resolve_notificationSnoozeAll(obj, info, **kwargs):
    """
    Resolver for notificationSnoozeAll mutation.
    Snoozes a notification and all related notifications until a specified time.

    Args:
        input: NotificationEntityInput containing the entity type and id
        snoozedUntilAt: DateTime when the notifications should be unsnoozed

    Returns:
        NotificationBatchActionPayload with success status, notifications list, and lastSyncId
    """
    session: Session = info.context["session"]
    input_data = kwargs.get("input")
    snoozed_until_at = kwargs.get("snoozedUntilAt")

    if not input_data:
        raise Exception("Input is required")

    if not snoozed_until_at:
        raise Exception("snoozedUntilAt is required")

    try:
        # Parse the snoozedUntilAt parameter if it's a string
        if isinstance(snoozed_until_at, str):
            snoozed_until_at = datetime.fromisoformat(
                snoozed_until_at.replace("Z", "+00:00")
            )

        # Extract entity identifiers from input
        notification_id = input_data.get("id")
        issue_id = input_data.get("issueId")
        initiative_id = input_data.get("initiativeId")
        initiative_update_id = input_data.get("initiativeUpdateId")
        project_id = input_data.get("projectId")
        project_update_id = input_data.get("projectUpdateId")
        oauth_client_approval_id = input_data.get("oauthClientApprovalId")

        # Build the query based on which entity ID was provided
        query = session.query(Notification)

        if notification_id:
            query = query.filter(Notification.id == notification_id)
        elif issue_id:
            query = query.filter(Notification.issueId == issue_id)
        elif initiative_id:
            query = query.filter(Notification.initiativeId == initiative_id)
        elif initiative_update_id:
            query = query.filter(
                Notification.initiativeUpdateId == initiative_update_id
            )
        elif project_id:
            query = query.filter(Notification.projectId == project_id)
        elif project_update_id:
            query = query.filter(Notification.projectUpdateId == project_update_id)
        elif oauth_client_approval_id:
            query = query.filter(
                Notification.oauthClientApprovalId == oauth_client_approval_id
            )
        else:
            raise Exception("At least one entity identifier must be provided")

        # Fetch all matching notifications
        notifications = query.all()

        if not notifications:
            # No notifications found, but still return success
            return {"success": True, "notifications": [], "lastSyncId": 0.0}

        # Snooze all matching notifications by setting snoozedUntilAt timestamp
        for notification in notifications:
            notification.snoozedUntilAt = snoozed_until_at

        # Return the proper NotificationBatchActionPayload structure
        return {"success": True, "notifications": notifications, "lastSyncId": 0.0}

    except Exception as e:
        raise Exception(f"Failed to snooze notifications: {str(e)}")


@mutation.field("notificationUnsnoozeAll")
def resolve_notificationUnsnoozeAll(obj, info, **kwargs):
    """
    Resolver for notificationUnsnoozeAll mutation.
    Unsnoozes a notification and all related notifications.

    Args:
        input: NotificationEntityInput containing the entity type and id
        unsnoozedAt: DateTime when the notifications were unsnoozed

    Returns:
        NotificationBatchActionPayload with success status, notifications list, and lastSyncId
    """
    session: Session = info.context["session"]
    input_data = kwargs.get("input")
    unsnoozed_at = kwargs.get("unsnoozedAt")

    if not input_data:
        raise Exception("Input is required")

    if not unsnoozed_at:
        raise Exception("unsnoozedAt is required")

    try:
        # Parse the unsnoozedAt parameter if it's a string
        if isinstance(unsnoozed_at, str):
            unsnoozed_at = datetime.fromisoformat(unsnoozed_at.replace("Z", "+00:00"))

        # Extract entity identifiers from input
        notification_id = input_data.get("id")
        issue_id = input_data.get("issueId")
        initiative_id = input_data.get("initiativeId")
        initiative_update_id = input_data.get("initiativeUpdateId")
        project_id = input_data.get("projectId")
        project_update_id = input_data.get("projectUpdateId")
        oauth_client_approval_id = input_data.get("oauthClientApprovalId")

        # Build the query based on which entity ID was provided
        query = session.query(Notification)

        if notification_id:
            query = query.filter(Notification.id == notification_id)
        elif issue_id:
            query = query.filter(Notification.issueId == issue_id)
        elif initiative_id:
            query = query.filter(Notification.initiativeId == initiative_id)
        elif initiative_update_id:
            query = query.filter(
                Notification.initiativeUpdateId == initiative_update_id
            )
        elif project_id:
            query = query.filter(Notification.projectId == project_id)
        elif project_update_id:
            query = query.filter(Notification.projectUpdateId == project_update_id)
        elif oauth_client_approval_id:
            query = query.filter(
                Notification.oauthClientApprovalId == oauth_client_approval_id
            )
        else:
            raise Exception("At least one entity identifier must be provided")

        # Fetch all matching notifications
        notifications = query.all()

        if not notifications:
            # No notifications found, but still return success
            return {"success": True, "notifications": [], "lastSyncId": 0.0}

        # Unsnooze all matching notifications by setting unsnoozedAt timestamp
        # and clearing snoozedUntilAt
        for notification in notifications:
            notification.unsnoozedAt = unsnoozed_at
            notification.snoozedUntilAt = None  # Clear the snooze timestamp

        # Return the proper NotificationBatchActionPayload structure
        return {"success": True, "notifications": notifications, "lastSyncId": 0.0}

    except Exception as e:
        raise Exception(f"Failed to unsnooze notifications: {str(e)}")


@mutation.field("organizationCancelDelete")
def resolve_organizationCancelDelete(obj, info, **kwargs):
    """
    Resolver for organizationCancelDelete mutation.
    Cancels the deletion of an organization. Administrator privileges required.

    Returns:
        OrganizationCancelDeletePayload with success status
    """
    session: Session = info.context["session"]

    try:
        # Get the organization from the context (assuming it's set by auth middleware)
        # For now, we'll query for the first organization with a deletionRequestedAt date
        # In a production system, you would get the organization ID from the authenticated user's context
        organization = (
            session.query(Organization)
            .filter(Organization.deletionRequestedAt.isnot(None))
            .first()
        )

        if not organization:
            raise Exception("No organization with pending deletion found")

        # Cancel the deletion by clearing the deletionRequestedAt timestamp
        organization.deletionRequestedAt = None
        organization.updatedAt = datetime.now(timezone.utc)

        # Return success payload
        return {"success": True}

    except Exception as e:
        raise Exception(f"Failed to cancel organization deletion: {str(e)}")


@mutation.field("organizationDeleteChallenge")
def resolve_organizationDeleteChallenge(obj, info, **kwargs):
    """
    Resolver for organizationDeleteChallenge mutation.
    Get an organization's delete confirmation token. Administrator privileges required.

    Returns:
        OrganizationDeletePayload with success status
    """
    session: Session = info.context["session"]

    try:
        user_id = info.context.get("user_id")
        if not user_id:
            raise Exception(
                "No authenticated user found. Please provide authentication credentials."
            )

        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise Exception(
                f"Authenticated user with id '{user_id}' not found in database"
            )

        if not user.organizationId:
            raise Exception("User does not have an associated organization")

        organization = (
            session.query(Organization)
            .filter(Organization.id == user.organizationId)
            .first()
        )
        if not organization:
            raise Exception(f"Organization with id '{user.organizationId}' not found")

        # Return success payload
        return {"success": True}

    except Exception as e:
        raise Exception(f"Failed to generate organization delete challenge: {str(e)}")


@mutation.field("organizationDelete")
def resolve_organizationDelete(obj, info, **kwargs):
    """
    Resolver for organizationDelete mutation.
    Delete's an organization. Administrator privileges required.

    Args:
        input: DeleteOrganizationInput containing deletionCode

    Returns:
        OrganizationDeletePayload with success status
    """
    session: Session = info.context["session"]

    try:
        # Extract input argument
        input_data = kwargs.get("input")
        if not input_data:
            raise Exception("Missing required input argument")

        # Extract deletionCode from input
        deletion_code = input_data.get("deletionCode")
        if not deletion_code:
            raise Exception("Missing required deletionCode field")

        # Get the organization from the authenticated user's context
        # In a production system, you would also:
        # 1. Verify the user has administrator privileges
        # 2. Verify the deletionCode matches the expected code for this organization
        user_id = info.context.get("user_id")
        if not user_id:
            raise Exception(
                "No authenticated user found. Please provide authentication credentials."
            )

        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise Exception(
                f"Authenticated user with id '{user_id}' not found in database"
            )

        if not user.organizationId:
            raise Exception("User does not have an associated organization")

        organization = (
            session.query(Organization)
            .filter(Organization.id == user.organizationId)
            .first()
        )
        if not organization:
            raise Exception(f"Organization with id '{user.organizationId}' not found")

        # Verify deletion code (in a real system, this would be validated against a stored code)
        # For now, we'll just check that it's provided and non-empty
        # The actual validation logic would depend on how deletion codes are generated and stored

        # Perform hard delete of the organization
        # WARNING: This will cascade delete all related entities unless cascade rules prevent it
        # Consider soft delete instead by setting archivedAt:
        # organization.archivedAt = datetime.now(timezone.utc)
        session.delete(organization)
        # Return success payload
        return {"success": True}

    except Exception as e:
        raise Exception(f"Failed to delete organization: {str(e)}")


@mutation.field("organizationDomainClaim")
def resolve_organizationDomainClaim(obj, info, **kwargs):
    """
    Resolver for organizationDomainClaim mutation.
    [INTERNAL] Verifies a domain claim.

    Args:
        id: String! - The ID of the organization domain to claim.

    Returns:
        OrganizationDomainSimplePayload with success status
    """
    session: Session = info.context["session"]

    try:
        # Extract id argument
        domain_id = kwargs.get("id")
        if not domain_id:
            raise Exception("Missing required id argument")

        # Query for the organization domain
        organization_domain = (
            session.query(OrganizationDomain).filter_by(id=domain_id).first()
        )

        if not organization_domain:
            raise Exception(f"Organization domain not found with id: {domain_id}")

        # Verify the domain claim by setting claimed to True
        # In a real system, this would involve:
        # 1. Verifying DNS records or other verification methods
        # 2. Checking verification codes
        # 3. Validating the verification email
        organization_domain.claimed = True
        organization_domain.verified = True
        organization_domain.updatedAt = datetime.now(timezone.utc)

        # Return success payload
        return {"success": True}

    except Exception as e:
        raise Exception(f"Failed to claim organization domain: {str(e)}")


@mutation.field("organizationDomainVerify")
def resolve_organizationDomainVerify(obj, info, **kwargs):
    """
    Resolver for organizationDomainVerify mutation.
    [INTERNAL] Verifies a domain to be added to an organization.

    Args:
        input: OrganizationDomainVerificationInput! - Contains:
            - organizationDomainId: String! - The identifier in UUID v4 format of the domain being verified.
            - verificationCode: String! - The verification code sent via email.

    Returns:
        OrganizationDomainPayload with the verified domain or error
    """
    session: Session = info.context["session"]

    try:
        # Extract input argument
        input_data = kwargs.get("input")
        if not input_data:
            raise Exception("Missing required input argument")

        # Extract required fields from input
        organization_domain_id = input_data.get("organizationDomainId")
        verification_code = input_data.get("verificationCode")

        if not organization_domain_id:
            raise Exception("Missing required organizationDomainId in input")
        if not verification_code:
            raise Exception("Missing required verificationCode in input")

        # Query for the organization domain
        organization_domain = (
            session.query(OrganizationDomain)
            .filter_by(id=organization_domain_id)
            .first()
        )

        if not organization_domain:
            raise Exception(
                f"Organization domain not found with id: {organization_domain_id}"
            )

        # Verify the domain using the verification code
        # In a real system, this would:
        # 1. Check the verification code against a stored value (e.g., sent via email)
        # 2. Validate the code hasn't expired
        # 3. Handle rate limiting on verification attempts
        # For this implementation, we'll simulate the verification

        # Note: In a production system, you would validate the verification_code
        # against a stored code, possibly with expiration logic
        # For now, we'll accept any non-empty verification code as valid

        # Mark the domain as verified
        organization_domain.verified = True
        organization_domain.updatedAt = datetime.now(timezone.utc)

        return organization_domain

    except Exception as e:
        raise Exception(f"Failed to verify organization domain: {str(e)}")


@mutation.field("organizationStartTrial")
def resolve_organizationStartTrial(obj, info, **kwargs):
    """
    Resolver for organizationStartTrial mutation.
    [DEPRECATED] Starts a trial for the organization. Administrator privileges required.

    Note: This mutation is deprecated. Use organizationStartTrialForPlan instead.

    Returns:
        OrganizationStartTrialPayload with success status
    """
    session: Session = info.context["session"]

    try:
        # Get the organization from the authenticated user's context
        user_id = info.context.get("user_id")
        if not user_id:
            raise Exception(
                "No authenticated user found. Please provide authentication credentials."
            )

        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise Exception(
                f"Authenticated user with id '{user_id}' not found in database"
            )

        if not user.organizationId:
            raise Exception("User does not have an associated organization")

        organization = (
            session.query(Organization)
            .filter(Organization.id == user.organizationId)
            .first()
        )
        if not organization:
            raise Exception(f"Organization with id '{user.organizationId}' not found")

        # Start the trial with a 14-day trial period
        now = datetime.now(timezone.utc)
        trial_duration_days = 14

        # Set trial end date (14 days from now)
        organization.trialEndsAt = now + timedelta(days=trial_duration_days)
        organization.updatedAt = now

        # Return success payload
        return {"success": True}

    except Exception as e:
        raise Exception(f"Failed to start organization trial: {str(e)}")


@mutation.field("organizationStartTrialForPlan")
def resolve_organizationStartTrialForPlan(obj, info, **kwargs):
    """
    Resolver for organizationStartTrialForPlan mutation.
    Starts a trial for the organization on the specified plan type. Administrator privileges required.

    Args:
        obj: Parent object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'input' with OrganizationStartTrialInput data
            - planType: String! - The plan type to trial

    Returns:
        OrganizationStartTrialPayload with success status
    """
    session: Session = info.context["session"]

    try:
        # Extract input from kwargs
        input_data = kwargs.get("input")
        if not input_data:
            raise Exception("Input data is required")

        # Validate required fields
        plan_type = input_data.get("planType")
        if not plan_type:
            raise Exception("planType is required")

        # Get the organization from the authenticated user's context
        user_id = info.context.get("user_id")
        if not user_id:
            raise Exception(
                "No authenticated user found. Please provide authentication credentials."
            )

        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise Exception(
                f"Authenticated user with id '{user_id}' not found in database"
            )

        if not user.organizationId:
            raise Exception("User does not have an associated organization")

        organization = (
            session.query(Organization)
            .filter(Organization.id == user.organizationId)
            .first()
        )
        if not organization:
            raise Exception(f"Organization with id '{user.organizationId}' not found")

        # Start the trial for the specified plan type with a 14-day trial period
        now = datetime.now(timezone.utc)
        trial_duration_days = 14

        # Set trial end date (14 days from now)
        # Note: In a production system, you would also:
        # 1. Validate the plan_type is valid
        # 2. Update billing/subscription status with the specific plan type
        # 3. Store the trial plan type in organization settings (if field exists)
        # 4. Send confirmation email with plan details
        organization.trialEndsAt = now + timedelta(days=trial_duration_days)
        organization.updatedAt = now

        return {"success": True}

    except Exception as e:
        raise Exception(f"Failed to start organization trial for plan: {str(e)}")


@mutation.field("organizationUpdate")
def resolve_organizationUpdate(obj, info, **kwargs):
    """
    Resolver for organizationUpdate mutation.
    Updates the user's organization.

    Args:
        obj: Parent object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'input' with OrganizationUpdateInput data

    Returns:
        OrganizationPayload with the updated organization
    """
    session: Session = info.context["session"]

    try:
        # Extract input from kwargs
        input_data = kwargs.get("input")
        if not input_data:
            raise Exception("Input data is required")

        # Get the organization from the authenticated user's context
        user_id = info.context.get("user_id")
        if not user_id:
            raise Exception(
                "No authenticated user found. Please provide authentication credentials."
            )

        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise Exception(
                f"Authenticated user with id '{user_id}' not found in database"
            )

        if not user.organizationId:
            raise Exception("User does not have an associated organization")

        organization = (
            session.query(Organization)
            .filter(Organization.id == user.organizationId)
            .first()
        )
        if not organization:
            raise Exception(f"Organization with id '{user.organizationId}' not found")

        # Update fields if provided in input
        if "aiAddonEnabled" in input_data:
            organization.aiAddonEnabled = input_data["aiAddonEnabled"]

        if "aiTelemetryEnabled" in input_data:
            organization.aiTelemetryEnabled = input_data["aiTelemetryEnabled"]

        if "allowMembersToInvite" in input_data:
            organization.allowMembersToInvite = input_data["allowMembersToInvite"]

        if "allowedAuthServices" in input_data:
            organization.allowedAuthServices = input_data["allowedAuthServices"]

        if "allowedFileUploadContentTypes" in input_data:
            organization.allowedFileUploadContentTypes = input_data[
                "allowedFileUploadContentTypes"
            ]

        if "customersConfiguration" in input_data:
            organization.customersConfiguration = input_data["customersConfiguration"]

        if "customersEnabled" in input_data:
            organization.customersEnabled = input_data["customersEnabled"]

        if "defaultFeedSummarySchedule" in input_data:
            organization.defaultFeedSummarySchedule = input_data[
                "defaultFeedSummarySchedule"
            ]

        if "feedEnabled" in input_data:
            organization.feedEnabled = input_data["feedEnabled"]

        if "fiscalYearStartMonth" in input_data:
            organization.fiscalYearStartMonth = input_data["fiscalYearStartMonth"]

        if "gitBranchFormat" in input_data:
            organization.gitBranchFormat = input_data["gitBranchFormat"]

        if "gitLinkbackMessagesEnabled" in input_data:
            organization.gitLinkbackMessagesEnabled = input_data[
                "gitLinkbackMessagesEnabled"
            ]

        if "gitPublicLinkbackMessagesEnabled" in input_data:
            organization.gitPublicLinkbackMessagesEnabled = input_data[
                "gitPublicLinkbackMessagesEnabled"
            ]

        if "initiativeUpdateReminderFrequencyInWeeks" in input_data:
            organization.initiativeUpdateReminderFrequencyInWeeks = input_data[
                "initiativeUpdateReminderFrequencyInWeeks"
            ]

        if "initiativeUpdateRemindersDay" in input_data:
            organization.initiativeUpdateRemindersDay = input_data[
                "initiativeUpdateRemindersDay"
            ]

        if "initiativeUpdateRemindersHour" in input_data:
            organization.initiativeUpdateRemindersHour = input_data[
                "initiativeUpdateRemindersHour"
            ]

        # Note: ipRestrictions is skipped in the ORM model
        # if 'ipRestrictions' in input_data:
        #     organization.ipRestrictions = input_data['ipRestrictions']

        if "logoUrl" in input_data:
            organization.logoUrl = input_data["logoUrl"]

        if "name" in input_data:
            organization.name = input_data["name"]

        if "oauthAppReview" in input_data:
            organization.oauthAppReview = input_data["oauthAppReview"]

        if "personalApiKeysEnabled" in input_data:
            organization.personalApiKeysEnabled = input_data["personalApiKeysEnabled"]

        if "projectUpdateReminderFrequencyInWeeks" in input_data:
            organization.projectUpdateReminderFrequencyInWeeks = input_data[
                "projectUpdateReminderFrequencyInWeeks"
            ]

        if "projectUpdateRemindersDay" in input_data:
            organization.projectUpdateRemindersDay = input_data[
                "projectUpdateRemindersDay"
            ]

        if "projectUpdateRemindersHour" in input_data:
            organization.projectUpdateRemindersHour = input_data[
                "projectUpdateRemindersHour"
            ]

        if "reducedPersonalInformation" in input_data:
            organization.reducedPersonalInformation = input_data[
                "reducedPersonalInformation"
            ]

        if "restrictAgentInvocationToMembers" in input_data:
            organization.restrictAgentInvocationToMembers = input_data[
                "restrictAgentInvocationToMembers"
            ]

        if "restrictLabelManagementToAdmins" in input_data:
            organization.restrictLabelManagementToAdmins = input_data[
                "restrictLabelManagementToAdmins"
            ]

        if "restrictTeamCreationToAdmins" in input_data:
            organization.restrictTeamCreationToAdmins = input_data[
                "restrictTeamCreationToAdmins"
            ]

        if "roadmapEnabled" in input_data:
            organization.roadmapEnabled = input_data["roadmapEnabled"]

        if "slaEnabled" in input_data:
            organization.slaEnabled = input_data["slaEnabled"]

        if "themeSettings" in input_data:
            organization.themeSettings = input_data["themeSettings"]

        if "urlKey" in input_data:
            organization.urlKey = input_data["urlKey"]

        if "workingDays" in input_data:
            organization.workingDays = input_data["workingDays"]

        # Update the updatedAt timestamp
        organization.updatedAt = datetime.now(timezone.utc)

        return organization

    except Exception as e:
        raise Exception(f"Failed to update organization: {str(e)}")


# ============================================================================
# Project Mutations
# ============================================================================


def _validate_priority(priority: float) -> int:
    """Validate and convert priority to int

    Linear priority values:
    0 - No priority (default)
    1 - Urgent
    2 - High
    3 - Medium
    4 - Low

    Args:
        priority: Priority value (can be float)

    Returns:
        int: Validated priority value

    Raises:
        ValueError: If priority is not in valid range 0-4
    """
    priority_int = int(priority)
    if priority_int < 0 or priority_int > 4:
        raise ValueError(
            f"Invalid priority value: {priority}. Priority must be between 0 (No priority) and 4 (Low). "
            "Valid values: 0=No priority, 1=Urgent, 2=High, 3=Medium, 4=Low"
        )
    return priority_int


def _get_priority_label(priority: int) -> str:
    """Map priority number to label

    Linear priority values:
    0 - No priority (default)
    1 - Urgent
    2 - High
    3 - Medium
    4 - Low
    """
    priority_map = {0: "No priority", 1: "Urgent", 2: "High", 3: "Medium", 4: "Low"}
    return priority_map.get(priority, "No priority")


def _generate_slug_id(name: str, project_id: str) -> str:
    """Generate a URL-friendly slug from the project name"""
    import re

    # Convert to lowercase and replace spaces with hyphens
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    # Append first 8 chars of ID for uniqueness
    slug = f"{slug}-{project_id[:8]}"
    return slug


@mutation.field("projectCreate")
def resolve_projectCreate(obj, info, **kwargs):
    """
    Creates a new project.

    Arguments:
        input: ProjectCreateInput! - The project object to create.
        connectSlackChannel: Boolean - Whether to connect a Slack channel to the project.

    Returns:
        Project: The newly created project.
    """
    session: Session = info.context["session"]

    try:
        # Extract arguments
        input_data = kwargs.get("input")

        if not input_data:
            raise Exception("Input data is required")

        # Validate required fields
        if not input_data.get("name"):
            raise Exception("Project name is required")
        if not input_data.get("teamIds"):
            raise Exception("At least one team ID is required")

        # Generate ID if not provided
        project_id = input_data.get("id", str(uuid.uuid4()))

        # Set defaults for non-nullable fields
        current_time = datetime.now(timezone.utc)

        # Priority: 0 = No priority, 1 = Urgent, 2 = High, 3 = Medium, 4 = Low
        priority = input_data.get("priority", 0)
        # Validate priority value (must be 0-4)
        priority = _validate_priority(priority)

        # Build the project entity
        project = Project(
            id=project_id,
            name=input_data["name"],
            description=input_data.get("description", ""),
            color=input_data.get(
                "color", "#000000"
            ),  # Default to black if not provided
            icon=input_data.get("icon"),
            content=input_data.get("content"),
            state=input_data.get("state", "planned"),
            priority=priority,
            priorityLabel=_get_priority_label(priority),
            prioritySortOrder=input_data.get("prioritySortOrder", 0.0),
            sortOrder=input_data.get("sortOrder", 0.0),
            startDate=input_data.get("startDate"),
            startDateResolution=input_data.get("startDateResolution"),
            targetDate=input_data.get("targetDate"),
            targetDateResolution=input_data.get("targetDateResolution"),
            leadId=input_data.get("leadId"),
            convertedFromIssueId=input_data.get("convertedFromIssueId"),
            lastAppliedTemplateId=input_data.get("lastAppliedTemplateId"),
            statusId=input_data.get("statusId"),
            labelIds=input_data.get("labelIds", []),
            # Set default values for required fields
            createdAt=current_time,
            updatedAt=current_time,
            completedIssueCountHistory=[],
            completedScopeHistory=[],
            inProgressScopeHistory=[],
            issueCountHistory=[],
            scopeHistory=[],
            currentProgress={},
            progressHistory={},
            progress=0.0,
            scope=0.0,
            frequencyResolution="weekly",
            slackIssueComments=False,
            slackIssueStatuses=False,
            slackNewIssue=False,
            slugId=_generate_slug_id(input_data["name"], project_id),
            url=f"https://linear.app/project/{project_id}",  # Placeholder URL
        )

        # Add the project to the session
        session.add(project)

        # Flush to get the project ID if relationships need it
        session.flush()

        # Handle team relationships (many-to-many)
        team_ids = input_data.get("teamIds", [])
        if team_ids:
            teams = session.query(Team).filter(Team.id.in_(team_ids)).all()
            if len(teams) != len(team_ids):
                raise Exception("One or more team IDs are invalid")
            project.teams = teams

        # Handle member relationships (many-to-many)
        member_ids = input_data.get("memberIds", [])
        if member_ids:
            members = session.query(User).filter(User.id.in_(member_ids)).all()
            if len(members) != len(member_ids):
                raise Exception("One or more member IDs are invalid")
            project.members = members

        # Handle label relationships (many-to-many)
        label_ids = input_data.get("labelIds", [])
        if label_ids:
            labels = (
                session.query(ProjectLabel).filter(ProjectLabel.id.in_(label_ids)).all()
            )
            if len(labels) != len(label_ids):
                raise Exception("One or more label IDs are invalid")
            project.labels = labels

        return project

    except Exception as e:
        raise Exception(f"Failed to create project: {str(e)}")


@mutation.field("projectAddLabel")
def resolve_projectAddLabel(obj, info, **kwargs):
    """
    Adds a label to a project.

    Arguments:
        id: The identifier of the project to add the label to.
        labelId: The identifier of the label to add.

    Returns:
        Project: The updated project.
    """
    session: Session = info.context["session"]

    try:
        # Extract arguments
        project_id = kwargs.get("id")
        label_id = kwargs.get("labelId")

        if not project_id:
            raise Exception("Project ID is required")
        if not label_id:
            raise Exception("Label ID is required")

        # Fetch the project
        project = session.query(Project).filter_by(id=project_id).first()
        if not project:
            raise Exception(f"Project with ID {project_id} not found")

        # Fetch the label
        label = session.query(ProjectLabel).filter_by(id=label_id).first()
        if not label:
            raise Exception(f"ProjectLabel with ID {label_id} not found")

        # Check if the label is already associated with the project
        if label in project.labels:
            # Label already associated, just return the project
            return project

        # Add the label to the project's labels relationship
        project.labels.append(label)

        # Also update the labelIds JSON array
        if label_id not in project.labelIds:
            project.labelIds.append(label_id)

        # Update the updatedAt timestamp
        project.updatedAt = datetime.now(timezone.utc)

        return project

    except Exception as e:
        raise Exception(f"Failed to add label to project: {str(e)}")


@mutation.field("projectRemoveLabel")
def resolve_projectRemoveLabel(obj, info, **kwargs):
    """
    Removes a label from a project.

    Arguments:
        id: The identifier of the project to remove the label from.
        labelId: The identifier of the label to remove.

    Returns:
        Project: The updated project.
    """
    session: Session = info.context["session"]

    try:
        # Extract arguments
        project_id = kwargs.get("id")
        label_id = kwargs.get("labelId")

        if not project_id:
            raise Exception("Project ID is required")
        if not label_id:
            raise Exception("Label ID is required")

        # Fetch the project
        project = session.query(Project).filter_by(id=project_id).first()
        if not project:
            raise Exception(f"Project with ID {project_id} not found")

        # Fetch the label
        label = session.query(ProjectLabel).filter_by(id=label_id).first()
        if not label:
            raise Exception(f"ProjectLabel with ID {label_id} not found")

        # Check if the label is currently associated with the project
        if label not in project.labels:
            # Label not associated, just return the project
            return project

        # Remove the label from the project's labels relationship
        project.labels.remove(label)

        # Also update the labelIds JSON array
        if label_id in project.labelIds:
            project.labelIds.remove(label_id)

        # Update the updatedAt timestamp
        project.updatedAt = datetime.now(timezone.utc)

        return project

    except Exception as e:
        raise Exception(f"Failed to remove label from project: {str(e)}")


@mutation.field("projectArchive")
def resolve_projectArchive(obj, info, **kwargs):
    """
    Archives a project.

    Arguments:
        id: The identifier of the project to archive.
        trash: Whether to trash the project (optional).

    Returns:
        ProjectArchivePayload: The archive payload with success status and entity.
    """
    session: Session = info.context["session"]

    try:
        # Extract arguments
        project_id = kwargs.get("id")
        trash = kwargs.get("trash", False)

        if not project_id:
            raise Exception("Project ID is required")

        # Fetch the project
        project = session.query(Project).filter_by(id=project_id).first()
        if not project:
            raise Exception(f"Project with ID {project_id} not found")

        # Archive the project by setting archivedAt timestamp
        project.archivedAt = datetime.now(timezone.utc)

        # Set trashed flag if requested
        if trash:
            project.trashed = True

        # Update the updatedAt timestamp
        project.updatedAt = datetime.now(timezone.utc)

        # Generate lastSyncId (using timestamp as sync ID)
        last_sync_id = datetime.now(timezone.utc).timestamp()

        # Return the payload
        return {"success": True, "entity": project, "lastSyncId": last_sync_id}

    except Exception as e:
        raise Exception(f"Failed to archive project: {str(e)}")


@mutation.field("projectUnarchive")
def resolve_projectUnarchive(obj, info, **kwargs):
    """
    Unarchives a project.

    Arguments:
        id: The identifier of the project to restore.

    Returns:
        ProjectArchivePayload: The archive payload with success status and entity.
    """
    session: Session = info.context["session"]

    try:
        # Extract arguments
        project_id = kwargs.get("id")

        if not project_id:
            raise Exception("Project ID is required")

        # Fetch the project
        project = session.query(Project).filter_by(id=project_id).first()
        if not project:
            raise Exception(f"Project with ID {project_id} not found")

        # Unarchive the project by clearing archivedAt timestamp
        project.archivedAt = None

        # Update the updatedAt timestamp
        project.updatedAt = datetime.now(timezone.utc)

        # Commit the changes

        # Generate lastSyncId (using timestamp as sync ID)
        last_sync_id = datetime.now(timezone.utc).timestamp()

        # Return the payload
        return {"success": True, "entity": project, "lastSyncId": last_sync_id}

    except Exception as e:
        raise Exception(f"Failed to unarchive project: {str(e)}")


@mutation.field("projectDelete")
def resolve_projectDelete(obj, info, **kwargs):
    """
    Deletes (trashes) a project.

    Arguments:
        id: The identifier of the project to delete.

    Returns:
        ProjectArchivePayload: The archive payload with success status and entity.
    """
    session: Session = info.context["session"]

    try:
        # Extract arguments
        project_id = kwargs.get("id")

        if not project_id:
            raise Exception("Project ID is required")

        # Fetch the project
        project = session.query(Project).filter_by(id=project_id).first()
        if not project:
            raise Exception(f"Project with ID {project_id} not found")

        # Delete the project by setting archivedAt timestamp (soft delete/trash)
        project.archivedAt = datetime.now(timezone.utc)

        # Update the updatedAt timestamp if it exists
        if hasattr(project, "updatedAt"):
            project.updatedAt = datetime.now(timezone.utc)

        # Generate lastSyncId (using timestamp as sync ID)
        last_sync_id = datetime.now(timezone.utc).timestamp()

        # Return the payload
        return {"success": True, "entity": project, "lastSyncId": last_sync_id}

    except Exception as e:
        raise Exception(f"Failed to delete project: {str(e)}")


@mutation.field("projectReassignStatus")
def resolve_projectReassignStatus(obj, info, **kwargs):
    """
    [INTERNAL] Updates all projects currently assigned to a project status to a new project status.

    Arguments:
        newProjectStatusId: The identifier of the new project status to update the projects to.
        originalProjectStatusId: The identifier of the project status with which projects will be updated.

    Returns:
        SuccessPayload: The success payload with lastSyncId and success status.
    """
    session: Session = info.context["session"]

    try:
        # Extract arguments
        new_project_status_id = kwargs.get("newProjectStatusId")
        original_project_status_id = kwargs.get("originalProjectStatusId")

        if not new_project_status_id:
            raise Exception("newProjectStatusId is required")
        if not original_project_status_id:
            raise Exception("originalProjectStatusId is required")

        # Verify that the new project status exists
        new_status = (
            session.query(ProjectStatus).filter_by(id=new_project_status_id).first()
        )
        if not new_status:
            raise Exception(f"ProjectStatus with ID {new_project_status_id} not found")

        # Verify that the original project status exists
        original_status = (
            session.query(ProjectStatus)
            .filter_by(id=original_project_status_id)
            .first()
        )
        if not original_status:
            raise Exception(
                f"ProjectStatus with ID {original_project_status_id} not found"
            )

        # Find all projects with the original status
        projects = (
            session.query(Project).filter_by(statusId=original_project_status_id).all()
        )

        # Update all projects to the new status
        for project in projects:
            project.statusId = new_project_status_id
            # Update the updatedAt timestamp
            if hasattr(project, "updatedAt"):
                project.updatedAt = datetime.now(timezone.utc)

        # Generate lastSyncId (using timestamp as sync ID)
        last_sync_id = datetime.now(timezone.utc).timestamp()

        # Return the payload
        return {"success": True, "lastSyncId": last_sync_id}

    except Exception as e:
        raise Exception(f"Failed to reassign project status: {str(e)}")


@mutation.field("projectUpdate")
def resolve_projectUpdate(obj, info, **kwargs):
    """
    Updates a project.

    Arguments:
        id: The identifier of the project to update. Also the identifier from the URL is accepted.
        input: A partial project object to update the project with.

    Returns:
        ProjectPayload: The updated project wrapped in a payload.
    """
    session: Session = info.context["session"]

    try:
        # Extract arguments
        project_id = kwargs.get("id")
        input_data = kwargs.get("input", {})

        if not project_id:
            raise Exception("id is required")

        # Query for the project
        project = session.query(Project).filter_by(id=project_id).first()
        if not project:
            raise Exception(f"Project with ID {project_id} not found")

        # Update scalar fields
        if "canceledAt" in input_data:
            project.canceledAt = input_data["canceledAt"]
        if "color" in input_data:
            project.color = input_data["color"]
        if "completedAt" in input_data:
            project.completedAt = input_data["completedAt"]
        if "content" in input_data:
            project.content = input_data["content"]
        if "convertedFromIssueId" in input_data:
            project.convertedFromIssueId = input_data["convertedFromIssueId"]
        if "description" in input_data:
            project.description = input_data["description"]
        if "frequencyResolution" in input_data:
            project.frequencyResolution = input_data["frequencyResolution"]
        if "icon" in input_data:
            project.icon = input_data["icon"]
        if "labelIds" in input_data:
            # Handle many-to-many relationship with project labels
            label_ids = input_data["labelIds"]
            project.labelIds = label_ids
            # Update the labels relationship
            labels = (
                session.query(ProjectLabel).filter(ProjectLabel.id.in_(label_ids)).all()
            )
            project.labels = labels
        if "lastAppliedTemplateId" in input_data:
            project.lastAppliedTemplateId = input_data["lastAppliedTemplateId"]
        if "leadId" in input_data:
            project.leadId = input_data["leadId"]
        if "memberIds" in input_data:
            # Handle many-to-many relationship with members
            member_ids = input_data["memberIds"]
            members = session.query(User).filter(User.id.in_(member_ids)).all()
            project.members = members
        if "name" in input_data:
            project.name = input_data["name"]
        if "priority" in input_data:
            project.priority = input_data["priority"]
        if "prioritySortOrder" in input_data:
            project.prioritySortOrder = input_data["prioritySortOrder"]
        if "projectUpdateRemindersPausedUntilAt" in input_data:
            project.projectUpdateRemindersPausedUntilAt = input_data[
                "projectUpdateRemindersPausedUntilAt"
            ]
        if "slackIssueComments" in input_data:
            project.slackIssueComments = input_data["slackIssueComments"]
        if "slackIssueStatuses" in input_data:
            project.slackIssueStatuses = input_data["slackIssueStatuses"]
        if "slackNewIssue" in input_data:
            project.slackNewIssue = input_data["slackNewIssue"]
        if "sortOrder" in input_data:
            project.sortOrder = input_data["sortOrder"]
        if "startDate" in input_data:
            project.startDate = input_data["startDate"]
        if "startDateResolution" in input_data:
            project.startDateResolution = input_data["startDateResolution"]
        if "state" in input_data:
            project.state = input_data["state"]
        if "statusId" in input_data:
            project.statusId = input_data["statusId"]
        if "targetDate" in input_data:
            project.targetDate = input_data["targetDate"]
        if "targetDateResolution" in input_data:
            project.targetDateResolution = input_data["targetDateResolution"]
        if "teamIds" in input_data:
            # Handle many-to-many relationship with teams
            team_ids = input_data["teamIds"]
            teams = session.query(Team).filter(Team.id.in_(team_ids)).all()
            project.teams = teams
        if "trashed" in input_data:
            project.trashed = input_data["trashed"]
        if "updateReminderFrequency" in input_data:
            project.updateReminderFrequency = input_data["updateReminderFrequency"]
        if "updateReminderFrequencyInWeeks" in input_data:
            project.updateReminderFrequencyInWeeks = input_data[
                "updateReminderFrequencyInWeeks"
            ]
        if "updateRemindersDay" in input_data:
            project.updateRemindersDay = input_data["updateRemindersDay"]
        if "updateRemindersHour" in input_data:
            project.updateRemindersHour = input_data["updateRemindersHour"]

        # Update the updatedAt timestamp
        project.updatedAt = datetime.now(timezone.utc)

        # Return the updated project (wrapped in payload structure)
        return {"success": True, "project": project}

    except Exception as e:
        raise Exception(f"Failed to update project: {str(e)}")


# ==============================================================================
# ProjectLabel Mutations
# ==============================================================================


@mutation.field("projectLabelCreate")
def resolve_projectLabelCreate(obj, info, **kwargs):
    """
    Creates a new project label.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'input' with ProjectLabelCreateInput data

    Returns:
        ProjectLabel: The created ProjectLabel entity
    """
    session: Session = info.context["session"]
    input_data = kwargs.get("input", {})

    try:
        # Extract input fields
        label_id = input_data.get("id") or str(uuid.uuid4())
        name = input_data.get("name")
        color = input_data.get("color", "#000000")  # Default to black if not provided
        description = input_data.get("description")
        is_group = input_data.get("isGroup", False)
        parent_id = input_data.get("parentId")

        # Validate required fields
        if not name:
            raise Exception("Project label name is required")

        # Determine organization_id from authenticated user
        user_id = info.context.get("user_id")
        if not user_id:
            raise Exception(
                "No authenticated user found. Please provide authentication credentials."
            )

        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise Exception(
                f"Authenticated user with id '{user_id}' not found in database"
            )

        organization_id = user.organizationId
        if not organization_id:
            raise Exception("User does not have an associated organization")

        # Get current timestamp
        now = datetime.now(timezone.utc)

        # Create the ProjectLabel entity
        project_label = ProjectLabel(
            id=label_id,
            name=name,
            color=color,
            description=description,
            isGroup=is_group,
            parentId=parent_id,
            organizationId=organization_id,
            createdAt=now,
            updatedAt=now,
        )

        session.add(project_label)

        return project_label

    except Exception as e:
        raise Exception(f"Failed to create project label: {str(e)}")


@mutation.field("projectLabelDelete")
def resolve_projectLabelDelete(obj, info, **kwargs):
    """
    Deletes a project label.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' - the identifier of the label to delete

    Returns:
        dict: DeletePayload with success status and entityId
    """
    session: Session = info.context["session"]
    label_id = kwargs.get("id")

    try:
        # Validate required field
        if not label_id:
            raise Exception("Project label ID is required")

        # Find the project label
        project_label = session.query(ProjectLabel).filter_by(id=label_id).first()

        if not project_label:
            raise Exception(f"Project label with ID {label_id} not found")

        # Perform soft delete by setting archivedAt timestamp
        now = datetime.now(timezone.utc)
        project_label.archivedAt = now
        project_label.updatedAt = now

        # Get the last sync ID (assuming we track this somewhere or use a timestamp)
        # For now, using the current timestamp as a float
        last_sync_id = now.timestamp()

        # Return DeletePayload
        return {"success": True, "entityId": label_id, "lastSyncId": last_sync_id}

    except Exception as e:
        raise Exception(f"Failed to delete project label: {str(e)}")


@mutation.field("projectLabelUpdate")
def resolve_projectLabelUpdate(obj, info, **kwargs):
    """
    Updates a project label.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' - the label identifier, and 'input' with ProjectLabelUpdateInput data

    Returns:
        ProjectLabel: The updated ProjectLabel entity
    """
    session: Session = info.context["session"]
    label_id = kwargs.get("id")
    input_data = kwargs.get("input", {})

    try:
        # Validate required field
        if not label_id:
            raise Exception("Project label ID is required")

        # Find the project label
        project_label = session.query(ProjectLabel).filter_by(id=label_id).first()

        if not project_label:
            raise Exception(f"Project label with ID {label_id} not found")

        # Update fields if provided in input
        if "color" in input_data:
            project_label.color = input_data["color"]

        if "description" in input_data:
            project_label.description = input_data["description"]

        if "isGroup" in input_data:
            project_label.isGroup = input_data["isGroup"]

        if "name" in input_data:
            project_label.name = input_data["name"]

        if "parentId" in input_data:
            project_label.parentId = input_data["parentId"]

        if "retiredAt" in input_data:
            project_label.retiredAt = input_data["retiredAt"]

        # Update the updatedAt timestamp
        project_label.updatedAt = datetime.now(timezone.utc)

        return project_label

    except Exception as e:
        raise Exception(f"Failed to update project label: {str(e)}")


# ==============================================================================
# ProjectMilestone Mutations
# ==============================================================================


@mutation.field("projectMilestoneCreate")
def resolve_projectMilestoneCreate(obj, info, **kwargs):
    """
    Creates a new project milestone.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'input' with ProjectMilestoneCreateInput data

    Returns:
        ProjectMilestone: The created ProjectMilestone entity
    """
    session: Session = info.context["session"]
    input_data = kwargs.get("input", {})

    try:
        # Validate required fields
        if not input_data.get("name"):
            raise Exception("Project milestone name is required")
        if not input_data.get("projectId"):
            raise Exception("Project ID is required")

        # Verify the project exists
        project = session.query(Project).filter_by(id=input_data["projectId"]).first()
        if not project:
            raise Exception(f"Project with ID {input_data['projectId']} not found")

        # Generate ID if not provided
        milestone_id = input_data.get("id") or str(uuid.uuid4())

        # Get current timestamp
        now = datetime.now(timezone.utc)

        # Create the ProjectMilestone entity
        # For new milestones, status defaults to 'unstarted'
        project_milestone = ProjectMilestone(
            id=milestone_id,
            name=input_data["name"],
            projectId=input_data["projectId"],
            description=input_data.get("description"),
            sortOrder=input_data.get("sortOrder", 0.0),
            targetDate=input_data.get("targetDate"),
            # Set default values for required fields
            createdAt=now,
            updatedAt=now,
            currentProgress={},
            progress=0.0,
            progressHistory={},
            status=ProjectMilestoneStatus.UNSTARTED,
        )

        session.add(project_milestone)

        return project_milestone

    except Exception as e:
        raise Exception(f"Failed to create project milestone: {str(e)}")


@mutation.field("projectMilestoneUpdate")
def resolve_projectMilestoneUpdate(obj, info, **kwargs):
    """
    Updates a project milestone.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (milestone ID) and 'input' (ProjectMilestoneUpdateInput)

    Returns:
        ProjectMilestone: The updated ProjectMilestone entity
    """
    session: Session = info.context["session"]
    milestone_id = kwargs.get("id")
    input_data = kwargs.get("input", {})

    try:
        # Validate that ID is provided
        if not milestone_id:
            raise Exception("Milestone ID is required")

        # Fetch the milestone to update
        milestone = session.query(ProjectMilestone).filter_by(id=milestone_id).first()

        if not milestone:
            raise Exception(f"ProjectMilestone with id {milestone_id} not found")

        # Update fields if provided in input
        if "name" in input_data:
            milestone.name = input_data["name"]

        if "description" in input_data:
            milestone.description = input_data["description"]

        if "descriptionData" in input_data:
            milestone.descriptionData = input_data["descriptionData"]

        if "projectId" in input_data:
            # Verify the new project exists
            project = (
                session.query(Project).filter_by(id=input_data["projectId"]).first()
            )
            if not project:
                raise Exception(f"Project with ID {input_data['projectId']} not found")
            milestone.projectId = input_data["projectId"]

        if "sortOrder" in input_data:
            milestone.sortOrder = input_data["sortOrder"]

        if "targetDate" in input_data:
            milestone.targetDate = input_data["targetDate"]

        # Update the updatedAt timestamp
        milestone.updatedAt = datetime.now(timezone.utc)

        return milestone

    except Exception as e:
        raise Exception(f"Failed to update project milestone: {str(e)}")


@mutation.field("projectMilestoneDelete")
def resolve_projectMilestoneDelete(obj, info, **kwargs):
    """
    Deletes a project milestone.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (milestone ID to delete)

    Returns:
        Dict containing DeletePayload with entityId, success, and lastSyncId
    """

    session: Session = info.context["session"]
    milestone_id = kwargs.get("id")

    try:
        # Validate that ID is provided
        if not milestone_id:
            raise Exception("Milestone ID is required")

        # Fetch the milestone to delete
        milestone = session.query(ProjectMilestone).filter_by(id=milestone_id).first()

        if not milestone:
            raise Exception(f"ProjectMilestone with id {milestone_id} not found")

        # Soft delete by setting archivedAt timestamp
        milestone.archivedAt = datetime.now(timezone.utc)
        milestone.updatedAt = datetime.now(timezone.utc)

        # Generate lastSyncId (using timestamp as sync ID)
        last_sync_id = datetime.now(timezone.utc).timestamp()

        # Return DeletePayload structure
        return {"entityId": milestone_id, "success": True, "lastSyncId": last_sync_id}

    except Exception as e:
        raise Exception(f"Failed to delete project milestone: {str(e)}")


@mutation.field("projectMilestoneMove")
def resolve_projectMilestoneMove(obj, info, **kwargs):
    """
    [Internal] Moves a project milestone to another project, can be called to undo a prior move.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (milestone ID) and 'input' (ProjectMilestoneMoveInput)

    Returns:
        Dict containing ProjectMilestoneMovePayload with:
        - projectMilestone: the moved milestone
        - success: boolean
        - lastSyncId: sync timestamp
        - previousIssueTeamIds: snapshot of moved issues (for undo)
        - previousProjectTeamIds: snapshot of added teams (for undo)
    """

    session: Session = info.context["session"]
    milestone_id = kwargs.get("id")
    input_data = kwargs.get("input", {})

    try:
        # Validate required fields
        if not milestone_id:
            raise Exception("Milestone ID is required")
        if not input_data.get("projectId"):
            raise Exception("Project ID is required in input")

        # Fetch the milestone to move
        milestone = session.query(ProjectMilestone).filter_by(id=milestone_id).first()
        if not milestone:
            raise Exception(f"ProjectMilestone with id {milestone_id} not found")

        # Fetch the target project
        target_project_id = input_data["projectId"]
        target_project = session.query(Project).filter_by(id=target_project_id).first()
        if not target_project:
            raise Exception(f"Target project with id {target_project_id} not found")

        # Track previous state for undo operations
        previous_issue_team_ids = []
        previous_project_team_ids = None

        # Handle undo operations if specified
        undo_issue_team_ids = input_data.get("undoIssueTeamIds", [])
        undo_project_team_ids = input_data.get("undoProjectTeamIds")

        if undo_issue_team_ids:
            # Undo: move issues back to their previous teams
            for undo_mapping in undo_issue_team_ids:
                issue_id = undo_mapping.get("issueId")
                team_id = undo_mapping.get("teamId")

                if issue_id and team_id:
                    issue = session.query(Issue).filter_by(id=issue_id).first()
                    if issue:
                        issue.teamId = team_id
                        issue.updatedAt = datetime.now(timezone.utc)

        if undo_project_team_ids:
            # Undo: remove teams that were added to the project
            project_id = undo_project_team_ids.get("projectId")
            team_ids = undo_project_team_ids.get("teamIds", [])

            if project_id and team_ids:
                project = session.query(Project).filter_by(id=project_id).first()
                if project:
                    # Remove the teams that were previously added
                    teams_to_remove = (
                        session.query(Team).filter(Team.id.in_(team_ids)).all()
                    )
                    for team in teams_to_remove:
                        if team in project.teams:
                            project.teams.remove(team)

        # Get the milestone's issues to handle team constraints
        milestone_issues = (
            session.query(Issue).filter_by(projectMilestoneId=milestone_id).all()
        )

        # Get the target project's team IDs
        target_project_team_ids = {team.id for team in target_project.teams}

        # Check if there's a team mismatch between milestone issues and target project
        issue_team_ids = {issue.teamId for issue in milestone_issues if issue.teamId}
        team_mismatch = not issue_team_ids.issubset(target_project_team_ids)

        if team_mismatch:
            # Handle team mismatch based on input options
            new_issue_team_id = input_data.get("newIssueTeamId")
            add_issue_team_to_project = input_data.get("addIssueTeamToProject", False)

            if new_issue_team_id:
                # Move all milestone issues to the specified team
                for issue in milestone_issues:
                    if issue.teamId:
                        # Store previous team mapping for undo
                        previous_issue_team_ids.append(
                            {"issueId": issue.id, "teamId": issue.teamId}
                        )
                    issue.teamId = new_issue_team_id
                    issue.updatedAt = datetime.now(timezone.utc)

            elif add_issue_team_to_project:
                # Add each issue's team to the target project
                teams_to_add = (
                    session.query(Team).filter(Team.id.in_(issue_team_ids)).all()
                )
                project_team_ids_before = [team.id for team in target_project.teams]

                for team in teams_to_add:
                    if team not in target_project.teams:
                        target_project.teams.append(team)

                # Store snapshot for undo
                if teams_to_add:
                    previous_project_team_ids = {
                        "projectId": target_project_id,
                        "teamIds": project_team_ids_before,
                    }

            else:
                # Neither option provided but there's a mismatch
                raise Exception(
                    "Team mismatch detected between milestone issues and target project. "
                    "Either 'newIssueTeamId' or 'addIssueTeamToProject' must be provided."
                )

        # Move the milestone to the new project
        milestone.projectId = target_project_id
        milestone.updatedAt = datetime.now(timezone.utc)

        # Generate lastSyncId (using timestamp as sync ID)
        last_sync_id = datetime.now(timezone.utc).timestamp()

        # Return ProjectMilestoneMovePayload structure
        return {
            "projectMilestone": milestone,
            "success": True,
            "lastSyncId": last_sync_id,
            "previousIssueTeamIds": previous_issue_team_ids
            if previous_issue_team_ids
            else None,
            "previousProjectTeamIds": previous_project_team_ids,
        }

    except Exception as e:
        raise Exception(f"Failed to move project milestone: {str(e)}")


# ============================================================
# PROJECT RELATION MUTATIONS
# ============================================================


@mutation.field("projectRelationCreate")
def resolve_projectRelationCreate(obj, info, **kwargs):
    """
    Creates a new project relation.

    Arguments:
        input: ProjectRelationCreateInput! - The project relation to create.

    Returns:
        ProjectRelation: The newly created project relation.
    """
    import uuid

    session: Session = info.context["session"]

    try:
        # Extract arguments
        input_data = kwargs.get("input")

        if not input_data:
            raise Exception("Input data is required")

        # Validate required fields
        if not input_data.get("projectId"):
            raise Exception("projectId is required")
        if not input_data.get("relatedProjectId"):
            raise Exception("relatedProjectId is required")
        if not input_data.get("anchorType"):
            raise Exception("anchorType is required")
        if not input_data.get("relatedAnchorType"):
            raise Exception("relatedAnchorType is required")
        if not input_data.get("type"):
            raise Exception("type is required")

        # Generate ID if not provided
        relation_id = input_data.get("id", str(uuid.uuid4()))

        # Set timestamps
        current_time = datetime.now(timezone.utc)

        # Build the project relation entity
        project_relation = ProjectRelation(
            id=relation_id,
            projectId=input_data["projectId"],
            relatedProjectId=input_data["relatedProjectId"],
            anchorType=input_data["anchorType"],
            relatedAnchorType=input_data["relatedAnchorType"],
            type=input_data["type"],
            projectMilestoneId=input_data.get("projectMilestoneId"),
            relatedProjectMilestoneId=input_data.get("relatedProjectMilestoneId"),
            createdAt=current_time,
            updatedAt=current_time,
            archivedAt=None,
        )

        session.add(project_relation)

        return project_relation

    except Exception as e:
        raise Exception(f"Failed to create project relation: {str(e)}")


@mutation.field("projectRelationDelete")
def resolve_projectRelationDelete(obj, info, **kwargs):
    """
    Deletes a project relation.

    Arguments:
        id: String! - The identifier of the project relation to delete.

    Returns:
        DeletePayload: Payload indicating success and the entity ID.
    """

    session: Session = info.context["session"]

    try:
        # Extract arguments
        relation_id = kwargs.get("id")

        if not relation_id:
            raise Exception("id is required")

        # Query for the project relation
        project_relation = (
            session.query(ProjectRelation).filter_by(id=relation_id).first()
        )

        if not project_relation:
            raise Exception(f"Project relation with id {relation_id} not found")

        # Soft delete by setting archivedAt
        current_time = datetime.now(timezone.utc)
        project_relation.archivedAt = current_time
        project_relation.updatedAt = current_time

        # Return DeletePayload
        return {
            "entityId": relation_id,
            "lastSyncId": current_time.timestamp(),
            "success": True,
        }

    except Exception as e:
        raise Exception(f"Failed to delete project relation: {str(e)}")


@mutation.field("projectRelationUpdate")
def resolve_projectRelationUpdate(obj, info, **kwargs):
    """
    Updates a project relation.

    Arguments:
        id: String! - The identifier of the project relation to update.
        input: ProjectRelationUpdateInput! - The properties of the project relation to update.

    Returns:
        ProjectRelation: The updated project relation.
    """

    session: Session = info.context["session"]

    try:
        # Extract arguments
        relation_id = kwargs.get("id")
        input_data = kwargs.get("input")

        if not relation_id:
            raise Exception("id is required")

        if not input_data:
            raise Exception("input is required")

        # Query for the project relation
        project_relation = (
            session.query(ProjectRelation).filter_by(id=relation_id).first()
        )

        if not project_relation:
            raise Exception(f"Project relation with id {relation_id} not found")

        # Update fields if provided in input
        if "anchorType" in input_data:
            project_relation.anchorType = input_data["anchorType"]

        if "projectId" in input_data:
            project_relation.projectId = input_data["projectId"]

        if "projectMilestoneId" in input_data:
            project_relation.projectMilestoneId = input_data["projectMilestoneId"]

        if "relatedAnchorType" in input_data:
            project_relation.relatedAnchorType = input_data["relatedAnchorType"]

        if "relatedProjectId" in input_data:
            project_relation.relatedProjectId = input_data["relatedProjectId"]

        if "relatedProjectMilestoneId" in input_data:
            project_relation.relatedProjectMilestoneId = input_data[
                "relatedProjectMilestoneId"
            ]

        if "type" in input_data:
            project_relation.type = input_data["type"]

        # Update the updatedAt timestamp
        current_time = datetime.now(timezone.utc)
        project_relation.updatedAt = current_time

        # Return the updated project relation
        return project_relation

    except Exception as e:
        raise Exception(f"Failed to update project relation: {str(e)}")


@mutation.field("projectStatusCreate")
def resolve_projectStatusCreate(obj, info, **kwargs):
    """
    Creates a new project status.

    Arguments:
        input: ProjectStatusCreateInput containing:
            - color: String! - The UI color of the status as a HEX string
            - description: String - Description of the status (optional)
            - id: String - The identifier in UUID v4 format (optional, auto-generated if not provided)
            - indefinite: Boolean - Whether or not a project can be in this status indefinitely (default: false)
            - name: String! - The name of the status
            - position: Float! - The position of the status in the workspace's project flow
            - type: ProjectStatusType! - The type of the project status

    Returns:
        ProjectStatusPayload: The create payload with success status and entity.
    """
    session: Session = info.context["session"]

    try:
        # Extract input argument
        input_data = kwargs.get("input")

        if not input_data:
            raise Exception("Input data is required")

        # Validate required fields
        required_fields = ["color", "name", "position", "type"]
        for field in required_fields:
            if field not in input_data:
                raise Exception(f"Required field '{field}' is missing")

        # Generate ID if not provided
        project_status_id = input_data.get("id", str(uuid.uuid4()))

        # Set defaults
        indefinite = input_data.get("indefinite", False)

        # Create timestamps
        now = datetime.now(timezone.utc)

        # Create the new ProjectStatus entity
        project_status = ProjectStatus(
            id=project_status_id,
            color=input_data["color"],
            name=input_data["name"],
            position=input_data["position"],
            type=input_data["type"],
            indefinite=indefinite,
            description=input_data.get("description"),
            createdAt=now,
            updatedAt=now,
            archivedAt=None,
            organizationId=input_data.get(
                "organizationId", "00000000-0000-0000-0000-000000000000"
            ),  # Placeholder
        )

        # Add to session
        session.add(project_status)

        # Generate lastSyncId (using timestamp as sync ID)
        last_sync_id = now.timestamp()

        # Return the payload
        return {
            "success": True,
            "projectStatus": project_status,
            "lastSyncId": last_sync_id,
        }

    except Exception as e:
        raise Exception(f"Failed to create project status: {str(e)}")


@mutation.field("projectStatusArchive")
def resolve_projectStatusArchive(obj, info, **kwargs):
    """
    Archives a project status.

    Arguments:
        id: The identifier of the project status to archive.

    Returns:
        ProjectStatusArchivePayload: The archive payload with success status and entity.
    """
    session: Session = info.context["session"]

    try:
        # Extract arguments
        project_status_id = kwargs.get("id")

        if not project_status_id:
            raise Exception("Project status ID is required")

        # Fetch the project status
        project_status = (
            session.query(ProjectStatus).filter_by(id=project_status_id).first()
        )
        if not project_status:
            raise Exception(f"Project status with ID {project_status_id} not found")

        # Archive the project status by setting archivedAt timestamp
        project_status.archivedAt = datetime.now(timezone.utc)

        # Update the updatedAt timestamp
        project_status.updatedAt = datetime.now(timezone.utc)

        # Generate lastSyncId (using timestamp as sync ID)
        last_sync_id = datetime.now(timezone.utc).timestamp()

        # Return the payload
        return {"success": True, "entity": project_status, "lastSyncId": last_sync_id}

    except Exception as e:
        raise Exception(f"Failed to archive project status: {str(e)}")


@mutation.field("projectStatusUnarchive")
def resolve_projectStatusUnarchive(obj, info, **kwargs):
    """
    Unarchives a project status.

    Arguments:
        id: The identifier of the project status to unarchive.

    Returns:
        ProjectStatusArchivePayload: The unarchive payload with success status and entity.
    """
    session: Session = info.context["session"]

    try:
        # Extract arguments
        project_status_id = kwargs.get("id")

        if not project_status_id:
            raise Exception("Project status ID is required")

        # Fetch the project status
        project_status = (
            session.query(ProjectStatus).filter_by(id=project_status_id).first()
        )
        if not project_status:
            raise Exception(f"Project status with ID {project_status_id} not found")

        # Unarchive the project status by setting archivedAt to None
        project_status.archivedAt = None

        # Update the updatedAt timestamp
        project_status.updatedAt = datetime.now(timezone.utc)

        # Generate lastSyncId (using timestamp as sync ID)
        last_sync_id = datetime.now(timezone.utc).timestamp()

        # Return the payload
        return {"success": True, "entity": project_status, "lastSyncId": last_sync_id}

    except Exception as e:
        raise Exception(f"Failed to unarchive project status: {str(e)}")


@mutation.field("projectStatusUpdate")
def resolve_projectStatusUpdate(obj, info, **kwargs):
    """
    Updates a project status.

    Arguments:
        id: String! - The identifier of the project status to update.
        input: ProjectStatusUpdateInput! - A partial ProjectStatus object to update the ProjectStatus with, containing:
            - color: String - The UI color of the status as a HEX string (optional)
            - description: String - Description of the status (optional)
            - indefinite: Boolean - Whether or not a project can be in this status indefinitely (optional)
            - name: String - The name of the status (optional)
            - position: Float - The position of the status in the workspace's project flow (optional)
            - type: ProjectStatusType - The type of the project status (optional)

    Returns:
        ProjectStatusPayload: The update payload with success status and entity.
    """
    session: Session = info.context["session"]

    try:
        # Extract arguments
        project_status_id = kwargs.get("id")
        input_data = kwargs.get("input")

        if not project_status_id:
            raise Exception("Project status ID is required")

        if not input_data:
            raise Exception("Input data is required")

        # Fetch the project status
        project_status = (
            session.query(ProjectStatus).filter_by(id=project_status_id).first()
        )
        if not project_status:
            raise Exception(f"Project status with ID {project_status_id} not found")

        # Update fields if provided in input
        if "color" in input_data:
            project_status.color = input_data["color"]

        if "description" in input_data:
            project_status.description = input_data["description"]

        if "indefinite" in input_data:
            project_status.indefinite = input_data["indefinite"]

        if "name" in input_data:
            project_status.name = input_data["name"]

        if "position" in input_data:
            project_status.position = input_data["position"]

        if "type" in input_data:
            project_status.type = input_data["type"]

        # Update the updatedAt timestamp
        project_status.updatedAt = datetime.now(timezone.utc)

        # Generate lastSyncId (using timestamp as sync ID)
        last_sync_id = datetime.now(timezone.utc).timestamp()

        # Return the payload
        return {
            "success": True,
            "projectStatus": project_status,
            "lastSyncId": last_sync_id,
        }

    except Exception as e:
        raise Exception(f"Failed to update project status: {str(e)}")


# ================================================================================
# Team Mutations
# ================================================================================


@mutation.field("teamCreate")
def resolve_teamCreate(obj, info, **kwargs):
    """
    Creates a new team. The user who creates the team will automatically be
    added as a member to the newly created team.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'input' (TeamCreateInput!) and optional 'copySettingsFromTeamId' (String)

    Returns:
        Team entity (TeamPayload structure)
    """
    import uuid
    import secrets

    session: Session = info.context["session"]
    input_data = kwargs.get("input", {})
    copy_settings_from_team_id = kwargs.get("copySettingsFromTeamId")

    try:
        # Extract required field
        name = input_data.get("name")
        if not name:
            raise Exception("Team name is required")

        # Get the organization from context (since organizationId is deprecated in input)
        # If organizationId is provided in input, use it; otherwise get from authenticated user
        org_id = input_data.get("organizationId")
        if not org_id:
            # Get organization from authenticated user
            user_id = info.context.get("user_id")
            if not user_id:
                raise Exception(
                    "No authenticated user found. Please provide authentication credentials."
                )

            user = session.query(User).filter(User.id == user_id).first()
            if not user:
                raise Exception(
                    f"Authenticated user with id '{user_id}' not found in database"
                )

            org_id = user.organizationId
            if not org_id:
                raise Exception("User does not have an associated organization")

        # Verify organization exists
        org = session.query(Organization).filter_by(id=org_id).first()
        if not org:
            raise Exception(f"Organization with id {org_id} not found")

        # Generate ID if not provided
        team_id = input_data.get("id", str(uuid.uuid4()))

        # Generate key if not provided (based on name)
        key = input_data.get("key")
        if not key:
            # Generate key from name (uppercase, remove spaces, limit to 5 chars)
            key = name.upper().replace(" ", "")[:5]
            # Ensure uniqueness by appending random chars if needed
            existing_team = session.query(Team).filter_by(key=key).first()
            if existing_team:
                key = f"{key}{secrets.token_hex(2).upper()[:3]}"

        # Generate unique invite hash
        invite_hash = secrets.token_urlsafe(16)

        # Current timestamp
        now = datetime.now(timezone.utc)

        # Get settings from source team if copySettingsFromTeamId is provided
        default_settings = {}
        if copy_settings_from_team_id:
            source_team = (
                session.query(Team).filter_by(id=copy_settings_from_team_id).first()
            )
            if source_team:
                # Copy relevant settings
                default_settings = {
                    "autoArchivePeriod": source_team.autoArchivePeriod,
                    "autoClosePeriod": source_team.autoClosePeriod,
                    "autoCloseStateId": source_team.autoCloseStateId,
                    "color": source_team.color,
                    "cycleCooldownTime": source_team.cycleCooldownTime,
                    "cycleDuration": source_team.cycleDuration,
                    "cycleIssueAutoAssignCompleted": source_team.cycleIssueAutoAssignCompleted,
                    "cycleIssueAutoAssignStarted": source_team.cycleIssueAutoAssignStarted,
                    "cycleLockToActive": source_team.cycleLockToActive,
                    "cycleStartDay": source_team.cycleStartDay,
                    "cyclesEnabled": source_team.cyclesEnabled,
                    "defaultIssueEstimate": source_team.defaultIssueEstimate,
                    "groupIssueHistory": source_team.groupIssueHistory,
                    "icon": source_team.icon,
                    "inheritIssueEstimation": source_team.inheritIssueEstimation,
                    "inheritProductIntelligenceScope": source_team.inheritProductIntelligenceScope,
                    "inheritWorkflowStatuses": source_team.inheritWorkflowStatuses,
                    "issueEstimationAllowZero": source_team.issueEstimationAllowZero,
                    "issueEstimationExtended": source_team.issueEstimationExtended,
                    "issueEstimationType": source_team.issueEstimationType,
                    "markedAsDuplicateWorkflowStateId": source_team.markedAsDuplicateWorkflowStateId,
                    "productIntelligenceScope": source_team.productIntelligenceScope,
                    "requirePriorityToLeaveTriage": source_team.requirePriorityToLeaveTriage,
                    "setIssueSortOrderOnStateChange": source_team.setIssueSortOrderOnStateChange,
                    "timezone": source_team.timezone,
                    "triageEnabled": source_team.triageEnabled,
                    "upcomingCycleCount": source_team.upcomingCycleCount,
                }

        # Create the new team with input data, using default settings as fallback
        new_team = Team(
            id=team_id,
            name=name,
            key=key,
            organizationId=org_id,
            inviteHash=invite_hash,
            createdAt=now,
            updatedAt=now,
            # Optional fields from input or defaults
            autoArchivePeriod=input_data.get(
                "autoArchivePeriod", default_settings.get("autoArchivePeriod", 0.0)
            ),
            autoClosePeriod=input_data.get(
                "autoClosePeriod", default_settings.get("autoClosePeriod")
            ),
            autoCloseStateId=input_data.get(
                "autoCloseStateId", default_settings.get("autoCloseStateId")
            ),
            color=input_data.get("color", default_settings.get("color")),
            cycleCooldownTime=input_data.get(
                "cycleCooldownTime", default_settings.get("cycleCooldownTime", 0.0)
            ),
            cycleDuration=input_data.get(
                "cycleDuration", default_settings.get("cycleDuration", 1.0)
            ),
            cycleIssueAutoAssignCompleted=input_data.get(
                "cycleIssueAutoAssignCompleted",
                default_settings.get("cycleIssueAutoAssignCompleted", False),
            ),
            cycleIssueAutoAssignStarted=input_data.get(
                "cycleIssueAutoAssignStarted",
                default_settings.get("cycleIssueAutoAssignStarted", False),
            ),
            cycleLockToActive=input_data.get(
                "cycleLockToActive", default_settings.get("cycleLockToActive", False)
            ),
            cycleStartDay=input_data.get(
                "cycleStartDay", default_settings.get("cycleStartDay", 1.0)
            ),
            cyclesEnabled=input_data.get(
                "cyclesEnabled", default_settings.get("cyclesEnabled", False)
            ),
            defaultIssueEstimate=input_data.get(
                "defaultIssueEstimate",
                default_settings.get("defaultIssueEstimate", 0.0),
            ),
            defaultProjectTemplateId=input_data.get(
                "defaultProjectTemplateId",
                default_settings.get("defaultProjectTemplateId"),
            ),
            defaultTemplateForMembersId=input_data.get(
                "defaultTemplateForMembersId",
                default_settings.get("defaultTemplateForMembersId"),
            ),
            defaultTemplateForNonMembersId=input_data.get(
                "defaultTemplateForNonMembersId",
                default_settings.get("defaultTemplateForNonMembersId"),
            ),
            description=input_data.get(
                "description", default_settings.get("description")
            ),
            groupIssueHistory=input_data.get(
                "groupIssueHistory", default_settings.get("groupIssueHistory", False)
            ),
            icon=input_data.get("icon", default_settings.get("icon")),
            inheritIssueEstimation=input_data.get(
                "inheritIssueEstimation",
                default_settings.get("inheritIssueEstimation", False),
            ),
            inheritProductIntelligenceScope=input_data.get(
                "inheritProductIntelligenceScope",
                default_settings.get("inheritProductIntelligenceScope"),
            ),
            inheritWorkflowStatuses=input_data.get(
                "inheritWorkflowStatuses",
                default_settings.get("inheritWorkflowStatuses", False),
            ),
            issueEstimationAllowZero=input_data.get(
                "issueEstimationAllowZero",
                default_settings.get("issueEstimationAllowZero", False),
            ),
            issueEstimationExtended=input_data.get(
                "issueEstimationExtended",
                default_settings.get("issueEstimationExtended", False),
            ),
            issueEstimationType=input_data.get(
                "issueEstimationType",
                default_settings.get("issueEstimationType", "notUsed"),
            ),
            markedAsDuplicateWorkflowStateId=input_data.get(
                "markedAsDuplicateWorkflowStateId",
                default_settings.get("markedAsDuplicateWorkflowStateId"),
            ),
            parentId=input_data.get("parentId"),
            private=input_data.get("private", default_settings.get("private", False)),
            productIntelligenceScope=input_data.get(
                "productIntelligenceScope",
                default_settings.get("productIntelligenceScope"),
            ),
            requirePriorityToLeaveTriage=input_data.get(
                "requirePriorityToLeaveTriage",
                default_settings.get("requirePriorityToLeaveTriage", False),
            ),
            setIssueSortOrderOnStateChange=input_data.get(
                "setIssueSortOrderOnStateChange",
                default_settings.get("setIssueSortOrderOnStateChange", "none"),
            ),
            timezone=input_data.get(
                "timezone", default_settings.get("timezone", "America/Los_Angeles")
            ),
            triageEnabled=input_data.get(
                "triageEnabled", default_settings.get("triageEnabled", False)
            ),
            upcomingCycleCount=input_data.get(
                "upcomingCycleCount", default_settings.get("upcomingCycleCount", 3.0)
            ),
            # Required fields with defaults
            aiThreadSummariesEnabled=False,
            autoCloseChildIssues=False,
            autoCloseParentIssues=False,
            currentProgress={},
            cycleCalenderUrl="",  # This would be generated based on team
            displayName=name,  # Initially same as name
            issueCount=0,
            issueOrderingNoPriorityFirst=False,
            issueSortOrderDefaultToBottom=False,
            joinByDefault=False,
            progressHistory={},
            scimManaged=False,
            slackIssueComments=False,
            slackIssueStatuses=False,
            slackNewIssue=False,
        )

        # Verify parent team exists if parentId is provided
        if new_team.parentId:
            parent_team = session.query(Team).filter_by(id=new_team.parentId).first()
            if not parent_team:
                raise Exception(f"Parent team with id {new_team.parentId} not found")

        # Add the team to the session
        session.add(new_team)

        # Flush to get the ID before creating membership
        session.flush()

        # Add the creating user as team owner
        creating_user_id = info.context.get("user_id")
        if creating_user_id:
            # Verify the user exists in the database
            user = session.query(User).filter_by(id=creating_user_id).first()
            if not user:
                raise Exception(
                    f"Cannot create team membership: User with id '{creating_user_id}' not found in database"
                )

            membership = TeamMembership(
                id=str(uuid.uuid4()),
                userId=creating_user_id,
                teamId=team_id,
                createdAt=now,
                updatedAt=now,
                owner=True,
                sortOrder=0.0,
            )
            session.add(membership)

        # Create default workflow states for the team
        # Linear default states: Triage, Backlog, Todo, In Progress, In Review, Done, Canceled, Duplicate
        default_states = [
            {
                "name": "Triage",
                "color": "#95a2b3",
                "type": "triage",
                "position": 0.0,
            },
            {
                "name": "Backlog",
                "color": "#95a2b3",
                "type": "backlog",
                "position": 1.0,
            },
            {
                "name": "Todo",
                "color": "#e2e2e2",
                "type": "unstarted",
                "position": 2.0,
            },
            {
                "name": "In Progress",
                "color": "#f2c94c",
                "type": "started",
                "position": 3.0,
            },
            {
                "name": "In Review",
                "color": "#eb5757",
                "type": "started",
                "position": 4.0,
            },
            {
                "name": "Done",
                "color": "#5e6ad2",
                "type": "completed",
                "position": 5.0,
            },
            {
                "name": "Canceled",
                "color": "#95a2b3",
                "type": "canceled",
                "position": 6.0,
            },
            {
                "name": "Duplicate",
                "color": "#95a2b3",
                "type": "canceled",
                "position": 7.0,
            },
        ]

        backlog_state_id = None
        for state_config in default_states:
            state_id = str(uuid.uuid4())
            workflow_state = WorkflowState(
                id=state_id,
                name=state_config["name"],
                color=state_config["color"],
                type=state_config["type"],
                position=state_config["position"],
                teamId=team_id,
                createdAt=now,
                updatedAt=now,
            )
            session.add(workflow_state)

            # Track the Backlog state ID (position 1) to set as default
            if state_config["position"] == 1.0:
                backlog_state_id = state_id

        # Set the default issue state to Backlog
        if backlog_state_id:
            new_team.defaultIssueStateId = backlog_state_id

        # Flush and refresh to load relationships
        session.flush()
        session.refresh(new_team)

        # Return TeamPayload structure
        return {"success": True, "team": new_team, "lastSyncId": float(now.timestamp())}

    except Exception as e:
        # Ensure the DB session is clean so request teardown doesn't fail
        try:
            session.rollback()
        except Exception:
            pass
        raise Exception(f"Failed to create team: {str(e)}")


@mutation.field("teamUpdate")
def resolve_teamUpdate(obj, info, **kwargs):
    """
    Updates a team.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (String!), 'input' (TeamUpdateInput!), and optional 'mapping' (InheritanceEntityMapping)

    Returns:
        Team entity (TeamPayload structure)
    """

    session: Session = info.context["session"]
    team_id = kwargs.get("id")
    input_data = kwargs.get("input", {})
    mapping = kwargs.get("mapping")  # Optional inheritance entity mapping

    try:
        # Validate required arguments
        if not team_id:
            raise Exception("Team ID is required")

        # Query for the team to update
        team = session.query(Team).filter_by(id=team_id).first()

        if not team:
            raise Exception(f"Team with id {team_id} not found")

        # Update fields from input (only if provided)
        if "aiThreadSummariesEnabled" in input_data:
            team.aiThreadSummariesEnabled = input_data["aiThreadSummariesEnabled"]

        if "autoArchivePeriod" in input_data:
            team.autoArchivePeriod = input_data["autoArchivePeriod"]

        if "autoCloseChildIssues" in input_data:
            team.autoCloseChildIssues = input_data["autoCloseChildIssues"]

        if "autoCloseParentIssues" in input_data:
            team.autoCloseParentIssues = input_data["autoCloseParentIssues"]

        if "autoClosePeriod" in input_data:
            team.autoClosePeriod = input_data["autoClosePeriod"]

        if "autoCloseStateId" in input_data:
            team.autoCloseStateId = input_data["autoCloseStateId"]
            # Verify the workflow state exists if provided
            if input_data["autoCloseStateId"]:
                state = (
                    session.query(WorkflowState)
                    .filter_by(id=input_data["autoCloseStateId"])
                    .first()
                )
                if not state:
                    raise Exception(
                        f"Workflow state with id {input_data['autoCloseStateId']} not found"
                    )

        if "color" in input_data:
            team.color = input_data["color"]

        if "cycleCooldownTime" in input_data:
            team.cycleCooldownTime = input_data["cycleCooldownTime"]

        if "cycleDuration" in input_data:
            team.cycleDuration = input_data["cycleDuration"]

        if "cycleEnabledStartDate" in input_data:
            # This field doesn't exist in the ORM - it might be used to calculate other fields
            # For now, we'll skip it or handle it in business logic
            pass

        if "cycleIssueAutoAssignCompleted" in input_data:
            team.cycleIssueAutoAssignCompleted = input_data[
                "cycleIssueAutoAssignCompleted"
            ]

        if "cycleIssueAutoAssignStarted" in input_data:
            team.cycleIssueAutoAssignStarted = input_data["cycleIssueAutoAssignStarted"]

        if "cycleLockToActive" in input_data:
            team.cycleLockToActive = input_data["cycleLockToActive"]

        if "cycleStartDay" in input_data:
            team.cycleStartDay = input_data["cycleStartDay"]

        if "cyclesEnabled" in input_data:
            team.cyclesEnabled = input_data["cyclesEnabled"]

        if "defaultIssueEstimate" in input_data:
            team.defaultIssueEstimate = input_data["defaultIssueEstimate"]

        if "defaultIssueStateId" in input_data:
            team.defaultIssueStateId = input_data["defaultIssueStateId"]
            # Verify the workflow state exists if provided
            if input_data["defaultIssueStateId"]:
                state = (
                    session.query(WorkflowState)
                    .filter_by(id=input_data["defaultIssueStateId"])
                    .first()
                )
                if not state:
                    raise Exception(
                        f"Workflow state with id {input_data['defaultIssueStateId']} not found"
                    )

        if "defaultProjectTemplateId" in input_data:
            team.defaultProjectTemplateId = input_data["defaultProjectTemplateId"]
            # Verify the template exists if provided
            if input_data["defaultProjectTemplateId"]:
                template = (
                    session.query(Template)
                    .filter_by(id=input_data["defaultProjectTemplateId"])
                    .first()
                )
                if not template:
                    raise Exception(
                        f"Template with id {input_data['defaultProjectTemplateId']} not found"
                    )

        if "defaultTemplateForMembersId" in input_data:
            team.defaultTemplateForMembersId = input_data["defaultTemplateForMembersId"]
            # Verify the template exists if provided
            if input_data["defaultTemplateForMembersId"]:
                template = (
                    session.query(Template)
                    .filter_by(id=input_data["defaultTemplateForMembersId"])
                    .first()
                )
                if not template:
                    raise Exception(
                        f"Template with id {input_data['defaultTemplateForMembersId']} not found"
                    )

        if "defaultTemplateForNonMembersId" in input_data:
            team.defaultTemplateForNonMembersId = input_data[
                "defaultTemplateForNonMembersId"
            ]
            # Verify the template exists if provided
            if input_data["defaultTemplateForNonMembersId"]:
                template = (
                    session.query(Template)
                    .filter_by(id=input_data["defaultTemplateForNonMembersId"])
                    .first()
                )
                if not template:
                    raise Exception(
                        f"Template with id {input_data['defaultTemplateForNonMembersId']} not found"
                    )

        if "description" in input_data:
            team.description = input_data["description"]

        if "groupIssueHistory" in input_data:
            team.groupIssueHistory = input_data["groupIssueHistory"]

        if "icon" in input_data:
            team.icon = input_data["icon"]

        if "inheritIssueEstimation" in input_data:
            team.inheritIssueEstimation = input_data["inheritIssueEstimation"]

        if "inheritProductIntelligenceScope" in input_data:
            team.inheritProductIntelligenceScope = input_data[
                "inheritProductIntelligenceScope"
            ]

        if "inheritWorkflowStatuses" in input_data:
            team.inheritWorkflowStatuses = input_data["inheritWorkflowStatuses"]

        if "issueEstimationAllowZero" in input_data:
            team.issueEstimationAllowZero = input_data["issueEstimationAllowZero"]

        if "issueEstimationExtended" in input_data:
            team.issueEstimationExtended = input_data["issueEstimationExtended"]

        if "issueEstimationType" in input_data:
            team.issueEstimationType = input_data["issueEstimationType"]

        if "issueOrderingNoPriorityFirst" in input_data:
            team.issueOrderingNoPriorityFirst = input_data[
                "issueOrderingNoPriorityFirst"
            ]

        if "joinByDefault" in input_data:
            team.joinByDefault = input_data["joinByDefault"]

        if "key" in input_data:
            # Verify key uniqueness
            existing_team = (
                session.query(Team)
                .filter_by(key=input_data["key"])
                .filter(Team.id != team_id)
                .first()
            )
            if existing_team:
                raise Exception(f"Team with key {input_data['key']} already exists")
            team.key = input_data["key"]

        if "markedAsDuplicateWorkflowStateId" in input_data:
            team.markedAsDuplicateWorkflowStateId = input_data[
                "markedAsDuplicateWorkflowStateId"
            ]
            # Verify the workflow state exists if provided
            if input_data["markedAsDuplicateWorkflowStateId"]:
                state = (
                    session.query(WorkflowState)
                    .filter_by(id=input_data["markedAsDuplicateWorkflowStateId"])
                    .first()
                )
                if not state:
                    raise Exception(
                        f"Workflow state with id {input_data['markedAsDuplicateWorkflowStateId']} not found"
                    )

        if "name" in input_data:
            team.name = input_data["name"]
            # Update displayName if name changes (typically displayName includes parent team name)
            # For now, we'll just set it to the name
            team.displayName = input_data["name"]

        if "parentId" in input_data:
            team.parentId = input_data["parentId"]
            # Verify parent team exists if provided
            if input_data["parentId"]:
                parent_team = (
                    session.query(Team).filter_by(id=input_data["parentId"]).first()
                )
                if not parent_team:
                    raise Exception(
                        f"Parent team with id {input_data['parentId']} not found"
                    )

        if "private" in input_data:
            team.private = input_data["private"]

        if "productIntelligenceScope" in input_data:
            team.productIntelligenceScope = input_data["productIntelligenceScope"]

        if "requirePriorityToLeaveTriage" in input_data:
            team.requirePriorityToLeaveTriage = input_data[
                "requirePriorityToLeaveTriage"
            ]

        if "scimManaged" in input_data:
            team.scimManaged = input_data["scimManaged"]

        if "setIssueSortOrderOnStateChange" in input_data:
            team.setIssueSortOrderOnStateChange = input_data[
                "setIssueSortOrderOnStateChange"
            ]

        if "slackIssueComments" in input_data:
            team.slackIssueComments = input_data["slackIssueComments"]

        if "slackIssueStatuses" in input_data:
            team.slackIssueStatuses = input_data["slackIssueStatuses"]

        if "slackNewIssue" in input_data:
            team.slackNewIssue = input_data["slackNewIssue"]

        if "timezone" in input_data:
            team.timezone = input_data["timezone"]

        if "triageEnabled" in input_data:
            team.triageEnabled = input_data["triageEnabled"]

        if "upcomingCycleCount" in input_data:
            team.upcomingCycleCount = input_data["upcomingCycleCount"]

        # Handle inheritance entity mapping if provided
        # This is an internal field used when updating team hierarchy
        # The mapping parameter contains mappings for issueLabels and workflowStates
        # that need to be updated when inheriting from parent team
        # For now, we'll store it in metadata or handle it in business logic
        if mapping:
            # TODO: Handle inheritance entity mapping
            # This would involve updating related IssueLabel and WorkflowState entities
            # based on the mapping provided
            pass

        # Update the updatedAt timestamp
        team.updatedAt = datetime.now(timezone.utc)

        return team

    except Exception as e:
        raise Exception(f"Failed to update team: {str(e)}")


@mutation.field("teamCyclesDelete")
def resolve_teamCyclesDelete(obj, info, id: str):
    """
    Deletes team's cycles data.

    Args:
        id: The identifier of the team, which cycles will be deleted

    Returns:
        Team: The team whose cycles were deleted
    """
    session: Session = info.context["session"]

    try:
        # Query for the team
        team = session.query(Team).filter_by(id=id).first()

        if not team:
            raise Exception(f"Team with id {id} not found")

        # Query for all cycles associated with this team
        cycles = session.query(Cycle).filter_by(teamId=id).all()

        # Delete all cycles
        for cycle in cycles:
            session.delete(cycle)

        # Clear the activeCycleId reference if it exists
        if team.activeCycleId:
            team.activeCycleId = None

        # Update the team's updatedAt timestamp
        team.updatedAt = datetime.now(timezone.utc)

        return team

    except Exception as e:
        raise Exception(f"Failed to delete team cycles: {str(e)}")


@mutation.field("teamDelete")
def resolve_teamDelete(obj, info, id: str):
    """
    Deletes a team.

    Args:
        id: The identifier of the team to delete

    Returns:
        Dict containing DeletePayload with entityId, success, and lastSyncId
    """
    session: Session = info.context["session"]

    try:
        # Query for the team to delete
        team = session.query(Team).filter_by(id=id).first()

        if not team:
            raise Exception(f"Team with id {id} not found")

        # Soft delete by setting archivedAt timestamp
        team.archivedAt = datetime.now(timezone.utc)
        team.updatedAt = datetime.now(timezone.utc)

        # Return DeletePayload structure
        return {
            "entityId": id,
            "success": True,
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
        }

    except Exception as e:
        raise Exception(f"Failed to delete team: {str(e)}")


@mutation.field("teamUnarchive")
def resolve_teamUnarchive(obj, info, id: str):
    """
    Unarchives a team and cancels deletion.

    Args:
        id: The identifier of the team to unarchive

    Returns:
        Dict containing TeamArchivePayload with entity, success, and lastSyncId
    """
    session: Session = info.context["session"]

    try:
        # Query for the team to unarchive
        team = session.query(Team).filter_by(id=id).first()

        if not team:
            raise Exception(f"Team with id {id} not found")

        # Unarchive by clearing the archivedAt timestamp
        team.archivedAt = None
        team.updatedAt = datetime.now(timezone.utc)

        # Return TeamArchivePayload structure
        return {
            "entity": team,
            "success": True,
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
        }

    except Exception as e:
        raise Exception(f"Failed to unarchive team: {str(e)}")


@mutation.field("teamKeyDelete")
def resolve_teamKeyDelete(obj, info, id: str):
    """
    Deletes a previously used team key.

    Note: This mutation assumes there is a team_keys table that tracks
    historical team keys. Since the TeamKey ORM model doesn't exist in the
    current schema, this is a placeholder implementation that can be adapted
    when the table structure is defined.

    Args:
        id: The identifier of the team key to delete

    Returns:
        Dict containing DeletePayload with entityId, success, and lastSyncId
    """
    session: Session = info.context["session"]

    try:
        # Note: TeamKey table doesn't exist in current ORM schema
        # This is a placeholder implementation
        # In a real implementation, you would:
        # 1. Query for the team key: team_key = session.query(TeamKey).filter_by(id=id).first()
        # 2. Validate the key exists
        # 3. Delete or soft-delete the key record

        # For now, we'll return a basic success response
        # This should be updated when the TeamKey table is added to the schema

        # Assuming the operation would succeed if the table existed:
        return {
            "entityId": id,
            "success": True,
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
        }

    except Exception as e:
        raise Exception(f"Failed to delete team key: {str(e)}")


# ============================================================
# TeamMembership mutations
# ============================================================


@mutation.field("teamMembershipCreate")
def resolve_teamMembershipCreate(obj, info, **kwargs):
    """
    Creates a new team membership.

    Args:
        obj: The parent object (unused for mutations)
        info: GraphQL resolve info containing context
        **kwargs: Mutation arguments including 'input'

    Returns:
        The created TeamMembership entity
    """
    session: Session = info.context["session"]

    try:
        # Extract input data
        input_data = kwargs.get("input", {})

        # Validate required fields
        if not input_data.get("teamId"):
            raise Exception("Field 'teamId' is required")
        if not input_data.get("userId"):
            raise Exception("Field 'userId' is required")

        # Generate ID if not provided
        membership_id = input_data.get("id", str(uuid.uuid4()))

        # Get current timestamp
        now = datetime.now(timezone.utc)

        # Build team membership data
        membership_data = {
            "id": membership_id,
            "teamId": input_data["teamId"],
            "userId": input_data["userId"],
            "owner": input_data.get("owner", False),  # Default to False if not provided
            "sortOrder": input_data.get(
                "sortOrder", 0.0
            ),  # Default to 0.0 if not provided
            "createdAt": now,
            "updatedAt": now,
        }

        # Create the team membership entity
        team_membership = TeamMembership(**membership_data)

        session.add(team_membership)

        # Return the proper TeamMembershipPayload structure
        return {"success": True, "lastSyncId": 0.0, "teamMembership": team_membership}

    except Exception as e:
        raise Exception(f"Failed to create team membership: {str(e)}")


@mutation.field("teamMembershipDelete")
def resolve_teamMembershipDelete(obj, info, **kwargs):
    """
    Deletes a team membership.

    Args:
        obj: The parent object (unused for mutations)
        info: GraphQL resolve info containing context
        **kwargs: Mutation arguments including 'id' and optional 'alsoLeaveParentTeams'

    Returns:
        DeletePayload with success status and entityId
    """
    session: Session = info.context["session"]

    try:
        # Extract arguments
        membership_id = kwargs.get("id")
        also_leave_parent_teams = kwargs.get("alsoLeaveParentTeams", False)

        # Validate required fields
        if not membership_id:
            raise Exception("Field 'id' is required")

        # Query for the team membership
        team_membership = (
            session.query(TeamMembership).filter_by(id=membership_id).first()
        )

        if not team_membership:
            raise Exception(f"Team membership with id '{membership_id}' not found")

        # Store the entity ID for the response
        entity_id = team_membership.id

        # Get last sync ID (using current timestamp as a simple implementation)
        # In a real system, this would come from a sync tracking mechanism
        last_sync_id = datetime.now(timezone.utc).timestamp()

        # If alsoLeaveParentTeams is True, we would need to handle parent team memberships
        # For now, this is a placeholder for that logic
        if also_leave_parent_teams:
            # TODO: Implement logic to leave parent teams
            # This would involve querying for parent teams and deleting those memberships
            pass

        # Soft delete: set archivedAt timestamp
        team_membership.archivedAt = datetime.now(timezone.utc)
        team_membership.updatedAt = datetime.now(timezone.utc)

        # Return DeletePayload structure
        return {"success": True, "entityId": entity_id, "lastSyncId": last_sync_id}

    except Exception as e:
        raise Exception(f"Failed to delete team membership: {str(e)}")


@mutation.field("teamMembershipUpdate")
def resolve_teamMembershipUpdate(obj, info, **kwargs):
    """
    Updates a team membership.

    Args:
        obj: The parent object (unused for mutations)
        info: GraphQL resolve info containing context
        **kwargs: Mutation arguments including 'id' and 'input'

    Returns:
        The updated TeamMembership entity
    """
    session: Session = info.context["session"]

    try:
        # Extract arguments
        membership_id = kwargs.get("id")
        input_data = kwargs.get("input", {})

        # Validate required fields
        if not membership_id:
            raise Exception("Field 'id' is required")

        # Query for the team membership
        team_membership = (
            session.query(TeamMembership).filter_by(id=membership_id).first()
        )

        if not team_membership:
            raise Exception(f"Team membership with id '{membership_id}' not found")

        # Update fields if provided in input
        if "owner" in input_data:
            team_membership.owner = input_data["owner"]

        if "sortOrder" in input_data:
            team_membership.sortOrder = input_data["sortOrder"]

        # Update the updatedAt timestamp
        team_membership.updatedAt = datetime.now(timezone.utc)

        # Return the proper TeamMembershipPayload structure
        return {"success": True, "lastSyncId": 0.0, "teamMembership": team_membership}

    except Exception as e:
        raise Exception(f"Failed to update team membership: {str(e)}")


def apply_workflow_state_filter(query, filter_dict):
    """
    Apply WorkflowStateFilter criteria to a SQLAlchemy query.

    Args:
        query: SQLAlchemy query object
        filter_dict: Dictionary containing filter criteria

    Returns:
        Modified query with filters applied
    """
    if not filter_dict:
        return query

    # Handle compound filters
    if "and" in filter_dict:
        for sub_filter in filter_dict["and"]:
            query = apply_workflow_state_filter(query, sub_filter)

    if "or" in filter_dict:
        # Build a list of conditions for OR
        # Each sub_filter is a branch, and conditions within a branch are ANDed together
        or_conditions = []
        for sub_filter in filter_dict["or"]:
            # Collect conditions for this specific OR branch
            branch_conditions = []

            # String comparators
            if "name" in sub_filter:
                cond = build_string_condition(WorkflowState.name, sub_filter["name"])
                if cond is not None:
                    branch_conditions.append(cond)

            if "description" in sub_filter:
                cond = build_string_condition(
                    WorkflowState.description, sub_filter["description"]
                )
                if cond is not None:
                    branch_conditions.append(cond)

            if "type" in sub_filter:
                cond = build_string_condition(WorkflowState.type, sub_filter["type"])
                if cond is not None:
                    branch_conditions.append(cond)

            # Date comparators
            if "createdAt" in sub_filter:
                cond = build_date_condition(
                    WorkflowState.createdAt, sub_filter["createdAt"]
                )
                if cond is not None:
                    branch_conditions.append(cond)

            if "updatedAt" in sub_filter:
                cond = build_date_condition(
                    WorkflowState.updatedAt, sub_filter["updatedAt"]
                )
                if cond is not None:
                    branch_conditions.append(cond)

            # ID comparator
            if "id" in sub_filter:
                cond = build_id_condition(WorkflowState.id, sub_filter["id"])
                if cond is not None:
                    branch_conditions.append(cond)

            # Number comparator
            if "position" in sub_filter:
                cond = build_number_condition(
                    WorkflowState.position, sub_filter["position"]
                )
                if cond is not None:
                    branch_conditions.append(cond)

            # Nested compound filters within OR
            if "and" in sub_filter or "or" in sub_filter:
                raise Exception(
                    "Nested compound filters (AND/OR) within OR filters are not currently supported for workflow states. "
                    "Please restructure your query to avoid nesting."
                )

            # Relationship filters within OR
            if "team" in sub_filter or "issues" in sub_filter:
                raise Exception(
                    "Relationship filters (team, issues) within OR filters are not currently supported for workflow states. "
                    "Please filter relationships at the top level and use OR only for direct field comparisons."
                )

            # Combine conditions within this branch with AND
            if branch_conditions:
                if len(branch_conditions) == 1:
                    or_conditions.append(branch_conditions[0])
                else:
                    or_conditions.append(and_(*branch_conditions))

        # Apply all OR conditions at once
        if or_conditions:
            query = query.filter(or_(*or_conditions))

    # String comparators
    if "name" in filter_dict:
        query = apply_string_comparator(query, WorkflowState.name, filter_dict["name"])

    if "description" in filter_dict:
        query = apply_nullable_string_comparator(
            query, WorkflowState.description, filter_dict["description"]
        )

    if "type" in filter_dict:
        query = apply_string_comparator(query, WorkflowState.type, filter_dict["type"])

    # Date comparators
    if "createdAt" in filter_dict:
        query = apply_date_comparator(
            query, WorkflowState.createdAt, filter_dict["createdAt"]
        )

    if "updatedAt" in filter_dict:
        query = apply_date_comparator(
            query, WorkflowState.updatedAt, filter_dict["updatedAt"]
        )

    # ID comparator
    if "id" in filter_dict:
        query = apply_id_comparator(query, WorkflowState.id, filter_dict["id"])

    # Number comparator
    if "position" in filter_dict:
        query = apply_number_comparator(
            query, WorkflowState.position, filter_dict["position"]
        )

    # Nested relationship filters
    if "team" in filter_dict:
        team_filter = filter_dict["team"]
        if team_filter and isinstance(team_filter, dict):
            # Join with Team table if not already joined
            if not any(
                desc.get("entity") is Team
                for desc in query.column_descriptions
                if isinstance(desc, dict) and "entity" in desc
            ):
                query = query.join(Team, WorkflowState.teamId == Team.id)
            query = apply_team_filter(query, team_filter)

    if "issues" in filter_dict:
        issues_filter = filter_dict["issues"]
        if issues_filter and isinstance(issues_filter, dict):
            # For collection filters, we need to check if ANY issue matches
            # This requires EXISTS subquery
            from sqlalchemy import exists

            # Create correlated subquery
            issue_exists = exists().where(Issue.stateId == WorkflowState.id)

            # We need to build filter conditions directly
            # Since apply_issue_filter needs a query object, we'll simplify for now
            # and only support basic issue collection filters
            raise Exception(
                "Issue collection filters on workflow states are not currently supported. "
                "Please filter issues directly using the issues query."
            )

    return query


@query.field("workflowState")
def resolve_workflowState(obj, info, id: str):
    """
    Query one specific workflow state by its id.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        id: The workflow state id to look up

    Returns:
        WorkflowState: The workflow state with the specified id

    Raises:
        Exception: If the workflow state is not found
    """
    session: Session = info.context["session"]

    # Query for the workflow state by id
    workflow_state = session.query(WorkflowState).filter(WorkflowState.id == id).first()

    if not workflow_state:
        raise Exception(f"WorkflowState with id '{id}' not found")

    return workflow_state


@query.field("workflowStates")
def resolve_workflowStates(
    obj,
    info,
    after: Optional[str] = None,
    before: Optional[str] = None,
    filter: Optional[dict] = None,
    first: Optional[int] = None,
    includeArchived: bool = False,
    last: Optional[int] = None,
    orderBy: Optional[str] = None,
):
    """
    Query all issue workflow states with filtering, sorting, and pagination.

    Args:
        obj: Parent object (None for root queries)
        info: GraphQL resolve info containing context
        after: Cursor for forward pagination
        before: Cursor for backward pagination
        filter: WorkflowStateFilter to apply to results
        first: Number of items to return (forward pagination, defaults to 50)
        includeArchived: Whether to include archived workflow states (default: false)
        last: Number of items to return (backward pagination, defaults to 50)
        orderBy: Field to order by (createdAt or updatedAt, default: createdAt)

    Returns:
        WorkflowStateConnection: Paginated list of workflow states
    """

    session: Session = info.context["session"]

    # Validate pagination parameters
    validate_pagination_params(after, before, first, last)

    # Determine the order field
    order_field = "createdAt"
    if orderBy == "updatedAt":
        order_field = "updatedAt"

    # Build base query
    base_query = session.query(WorkflowState)

    # Apply archived filter
    if not includeArchived:
        base_query = base_query.filter(WorkflowState.archivedAt.is_(None))

    # Apply additional filters if provided
    if filter:
        base_query = apply_workflow_state_filter(base_query, filter)

    # Apply cursor-based pagination
    if after:
        cursor_data = decode_cursor(after)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for forward pagination
        order_column = getattr(WorkflowState, order_field)
        base_query = base_query.filter(
            or_(
                order_column > cursor_field_value,
                and_(order_column == cursor_field_value, WorkflowState.id > cursor_id),
            )
        )

    if before:
        cursor_data = decode_cursor(before)
        cursor_field_value = cursor_data["field"]
        cursor_id = cursor_data["id"]

        # Convert cursor field value to datetime if needed
        if order_field in ["createdAt", "updatedAt"]:
            cursor_field_value = datetime.fromisoformat(cursor_field_value)

        # Apply cursor filter for backward pagination
        order_column = getattr(WorkflowState, order_field)
        base_query = base_query.filter(
            or_(
                order_column < cursor_field_value,
                and_(order_column == cursor_field_value, WorkflowState.id < cursor_id),
            )
        )

    # Apply ordering
    order_column = getattr(WorkflowState, order_field)
    if last or before:
        # For backward pagination, reverse the order
        base_query = base_query.order_by(order_column.desc(), WorkflowState.id.desc())
    else:
        base_query = base_query.order_by(order_column.asc(), WorkflowState.id.asc())

    # Determine limit
    limit = first if first else (last if last else 50)

    # Fetch limit + 1 to detect if there are more pages
    items = base_query.limit(limit + 1).all()

    # Use the centralized pagination helper
    return apply_pagination(items, after, before, first, last, order_field)


@mutation.field("workflowStateArchive")
def resolve_workflowStateArchive(obj, info, **kwargs):
    """
    Archives a workflow state. Only states with issues that have all been archived can be archived.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (workflow state ID to archive)

    Returns:
        Dict containing WorkflowStateArchivePayload with entity, success, and lastSyncId
    """
    session: Session = info.context["session"]
    state_id = kwargs.get("id")

    try:
        # Fetch the workflow state to archive
        workflow_state = session.query(WorkflowState).filter_by(id=state_id).first()

        if not workflow_state:
            raise Exception(f"WorkflowState with id {state_id} not found")

        # Check if all issues in this state have been archived
        # Get all issues associated with this workflow state
        unarchived_issues = (
            session.query(Issue)
            .filter(Issue.stateId == state_id)
            .filter(Issue.archivedAt.is_(None))
            .count()
        )

        if unarchived_issues > 0:
            raise Exception(
                f"Cannot archive workflow state: {unarchived_issues} unarchived issue(s) still in this state"
            )

        # Soft archive by setting archivedAt timestamp
        workflow_state.archivedAt = datetime.now(timezone.utc)
        workflow_state.updatedAt = datetime.now(timezone.utc)

        # Return WorkflowStateArchivePayload structure
        return {
            "entity": workflow_state,
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
            "success": True,
        }

    except Exception as e:
        raise Exception(f"Failed to archive workflow state: {e}") from e


@mutation.field("workflowStateCreate")
def resolve_workflowStateCreate(obj, info, **kwargs):
    """
    Creates a new state, adding it to the workflow of a team.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'input' (WorkflowStateCreateInput)

    Returns:
        Dict containing WorkflowStatePayload with entity, success, and lastSyncId
    """
    session: Session = info.context["session"]
    input_data = kwargs.get("input", {})

    try:
        # Extract required fields
        color = input_data.get("color")
        name = input_data.get("name")
        team_id = input_data.get("teamId")
        type_value = input_data.get("type")

        # Validate required fields
        if not color:
            raise Exception("Field 'color' is required")
        if not name:
            raise Exception("Field 'name' is required")
        if not team_id:
            raise Exception("Field 'teamId' is required")
        if not type_value:
            raise Exception("Field 'type' is required")

        # Verify the team exists
        team = session.query(Team).filter_by(id=team_id).first()
        if not team:
            raise Exception(f"Team with id {team_id} not found")

        # Generate ID if not provided
        workflow_state_id = input_data.get("id") or str(uuid.uuid4())

        # Extract optional fields
        description = input_data.get("description")
        position = input_data.get("position")

        # If position is not provided, set it to the next available position
        if position is None:
            max_position = (
                session.query(WorkflowState)
                .filter(WorkflowState.teamId == team_id)
                .order_by(WorkflowState.position.desc())
                .first()
            )
            position = (max_position.position + 1.0) if max_position else 0.0

        # Create the new workflow state
        now = datetime.now(timezone.utc)
        workflow_state = WorkflowState(
            id=workflow_state_id,
            color=color,
            name=name,
            teamId=team_id,
            type=type_value,
            description=description,
            position=position,
            createdAt=now,
            updatedAt=now,
        )

        session.add(workflow_state)

        # Return WorkflowStatePayload structure
        return {
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
            "success": True,
            "workflowState": workflow_state,
        }

    except Exception as e:
        raise Exception(f"Failed to create workflow state: {str(e)}")


@mutation.field("workflowStateUpdate")
def resolve_workflowStateUpdate(obj, info, **kwargs):
    """
    Updates a state.

    Args:
        obj: The root object (unused)
        info: GraphQL resolve info containing context
        **kwargs: Contains 'id' (workflow state ID) and 'input' (WorkflowStateUpdateInput)

    Returns:
        Dict containing WorkflowStatePayload with entity, success, and lastSyncId
    """
    session: Session = info.context["session"]
    state_id = kwargs.get("id")
    input_data = kwargs.get("input", {})

    try:
        # Fetch the workflow state to update
        workflow_state = session.query(WorkflowState).filter_by(id=state_id).first()

        if not workflow_state:
            raise Exception(f"WorkflowState with id {state_id} not found")

        # Update fields if provided in input
        if "color" in input_data:
            workflow_state.color = input_data["color"]

        if "description" in input_data:
            workflow_state.description = input_data["description"]

        if "name" in input_data:
            workflow_state.name = input_data["name"]

        if "position" in input_data:
            workflow_state.position = input_data["position"]

        # Update the updatedAt timestamp
        workflow_state.updatedAt = datetime.now(timezone.utc)

        # Return WorkflowStatePayload structure
        return {
            "lastSyncId": 0.0,  # In a real implementation, this would come from a sync tracking system
            "success": True,
            "workflowState": workflow_state,
        }

    except Exception as e:
        raise Exception(f"Failed to update workflow state: {str(e)}")
