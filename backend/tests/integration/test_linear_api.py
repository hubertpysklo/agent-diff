"""Integration tests for Linear GraphQL API."""

import pytest
from httpx import AsyncClient

# Constants from linear_default seed data
USER_AGENT = "U01AGENT"
USER_JOHN = "U02JOHN"
USER_SARAH = "U03SARAH"
TEAM_ENG = "TEAM01ENG"
TEAM_PROD = "TEAM02PROD"
ORG_ID = "ORG01"
ISSUE_ENG_001 = "ISS_ENG_001"
STATE_BACKLOG = "WS_ENG_BACKLOG"
STATE_TODO = "WS_ENG_TODO"
STATE_IN_PROGRESS = "WS_ENG_IN_PROGRESS"
STATE_IN_REVIEW = "WS_ENG_IN_REVIEW"
STATE_DONE = "WS_ENG_DONE"


@pytest.mark.asyncio
class TestQueryViewer:
    async def test_get_viewer_info(self, linear_client: AsyncClient):
        """Test viewer query returns current user info."""
        query = """
          query {
            viewer {
              id
              name
              email
              active
            }
          }
        """
        response = await linear_client.post("/graphql", json={"query": query})
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert data["data"]["viewer"]["id"] == USER_AGENT
        assert data["data"]["viewer"]["name"] == "AI Agent"
        assert data["data"]["viewer"]["email"] == "agent@example.com"
        assert data["data"]["viewer"]["active"] is True


@pytest.mark.asyncio
class TestQueryIssues:
    async def test_list_issues_default(self, linear_client: AsyncClient):
        """Test listing issues without filters."""
        query = """
          query {
            issues {
              nodes {
                id
                identifier
                title
                team {
                  id
                  name
                  key
                }
              }
            }
          }
        """
        response = await linear_client.post("/graphql", json={"query": query})
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        issues = data["data"]["issues"]["nodes"]
        assert len(issues) >= 1
        # Check seeded issue
        issue = next((i for i in issues if i["id"] == ISSUE_ENG_001), None)
        assert issue is not None
        assert issue["identifier"] == "ENG-1"
        assert "authentication" in issue["title"].lower()
        assert issue["team"]["id"] == TEAM_ENG
        assert issue["team"]["key"] == "ENG"

    async def test_list_issues_with_team_filter(self, linear_client: AsyncClient):
        """Test filtering issues by team."""
        query = """
          query($filter: IssueFilter) {
            issues(filter: $filter) {
              nodes {
                id
                team {
                  id
                }
              }
            }
          }
        """
        variables = {"filter": {"team": {"id": {"eq": TEAM_ENG}}}}
        response = await linear_client.post(
            "/graphql", json={"query": query, "variables": variables}
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        issues = data["data"]["issues"]["nodes"]
        # All issues should belong to Engineering team
        for issue in issues:
            assert issue["team"]["id"] == TEAM_ENG

    async def test_list_issues_pagination(self, linear_client: AsyncClient):
        """Test cursor-based pagination for issues."""
        query = """
          query($first: Int) {
            issues(first: $first) {
              edges {
                cursor
                node {
                  id
                }
              }
              pageInfo {
                hasNextPage
                endCursor
              }
            }
          }
        """
        variables = {"first": 1}
        response = await linear_client.post(
            "/graphql", json={"query": query, "variables": variables}
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        edges = data["data"]["issues"]["edges"]
        assert len(edges) == 1
        assert "cursor" in edges[0]
        assert "node" in edges[0]
        assert "pageInfo" in data["data"]["issues"]


@pytest.mark.asyncio
class TestQueryTeams:
    async def test_list_teams(self, linear_client: AsyncClient):
        """Test listing all teams."""
        query = """
          query {
            teams {
              nodes {
                id
                name
                key
              }
            }
          }
        """
        response = await linear_client.post("/graphql", json={"query": query})
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        teams = data["data"]["teams"]["nodes"]
        assert len(teams) >= 2
        # Check seeded teams
        team_ids = [t["id"] for t in teams]
        assert TEAM_ENG in team_ids
        assert TEAM_PROD in team_ids

        eng_team = next((t for t in teams if t["id"] == TEAM_ENG), None)
        assert eng_team is not None
        assert eng_team["name"] == "Engineering"
        assert eng_team["key"] == "ENG"

    async def test_get_team_by_id(self, linear_client: AsyncClient):
        """Test querying specific team by ID."""
        query = """
          query($id: String!) {
            team(id: $id) {
              id
              name
              key
              description
              icon
              color
            }
          }
        """
        variables = {"id": TEAM_ENG}
        response = await linear_client.post(
            "/graphql", json={"query": query, "variables": variables}
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        team = data["data"]["team"]
        assert team["id"] == TEAM_ENG
        assert team["name"] == "Engineering"
        assert team["key"] == "ENG"
        assert team["description"] == "Engineering team"
        assert team["icon"] == "🚀"
        assert team["color"] == "#3B82F6"


@pytest.mark.asyncio
class TestQueryWorkflowStates:
    async def test_get_workflow_states_for_team(self, linear_client: AsyncClient):
        """Test querying workflow states for a team."""
        query = """
          query($filter: WorkflowStateFilter) {
            workflowStates(filter: $filter) {
              nodes {
                id
                name
                type
                position
                team {
                  id
                }
              }
            }
          }
        """
        variables = {"filter": {"team": {"id": {"eq": TEAM_ENG}}}}
        response = await linear_client.post(
            "/graphql", json={"query": query, "variables": variables}
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        states = data["data"]["workflowStates"]["nodes"]
        # Should have 8 workflow states for Engineering team
        assert len(states) == 8

        # Verify all states belong to Engineering team
        for state in states:
            assert state["team"]["id"] == TEAM_ENG

        # Check that specific states exist
        state_names = [s["name"] for s in states]
        assert "Triage" in state_names
        assert "Backlog" in state_names
        assert "Todo" in state_names
        assert "In Progress" in state_names
        assert "In Review" in state_names
        assert "Done" in state_names
        assert "Canceled" in state_names
        assert "Duplicate" in state_names

        # Verify positions are sequential
        positions = sorted([s["position"] for s in states])
        assert positions == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]


@pytest.mark.asyncio
class TestIssueCreate:
    async def test_create_issue_basic(self, linear_client: AsyncClient):
        """Test creating a basic issue with required fields."""
        query = """
          mutation($input: IssueCreateInput!) {
            issueCreate(input: $input) {
              success
              issue {
                id
                title
                team {
                  id
                }
                state {
                  id
                  name
                }
                priority
                priorityLabel
              }
            }
          }
        """
        variables = {
            "input": {
                "teamId": TEAM_ENG,
                "title": "Test issue from integration test",
            }
        }
        response = await linear_client.post(
            "/graphql", json={"query": query, "variables": variables}
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        result = data["data"]["issueCreate"]
        assert result["success"] is True
        issue = result["issue"]
        assert issue["title"] == "Test issue from integration test"
        assert issue["team"]["id"] == TEAM_ENG
        # Should default to Backlog state
        assert issue["state"]["id"] == STATE_BACKLOG
        assert issue["state"]["name"] == "Backlog"
        # Should default to priority 0 (No priority)
        assert issue["priority"] == 0.0
        assert issue["priorityLabel"] == "No priority"

    async def test_create_issue_with_assignee(self, linear_client: AsyncClient):
        """Test creating issue with assignee."""
        query = """
          mutation($input: IssueCreateInput!) {
            issueCreate(input: $input) {
              success
              issue {
                id
                title
                assignee {
                  id
                  name
                }
              }
            }
          }
        """
        variables = {
            "input": {
                "teamId": TEAM_ENG,
                "title": "Issue assigned to John",
                "assigneeId": USER_JOHN,
            }
        }
        response = await linear_client.post(
            "/graphql", json={"query": query, "variables": variables}
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        result = data["data"]["issueCreate"]
        assert result["success"] is True
        issue = result["issue"]
        assert issue["assignee"]["id"] == USER_JOHN
        assert issue["assignee"]["name"] == "John Doe"

    async def test_create_issue_invalid_team(self, linear_client: AsyncClient):
        """Test creating issue with invalid teamId fails."""
        query = """
          mutation($input: IssueCreateInput!) {
            issueCreate(input: $input) {
              success
              issue {
                id
              }
            }
          }
        """
        variables = {
            "input": {
                "teamId": "INVALID_TEAM_ID",
                "title": "This should fail",
            }
        }
        response = await linear_client.post(
            "/graphql", json={"query": query, "variables": variables}
        )
        # GraphQL should return 200 but with errors
        assert response.status_code == 200
        data = response.json()
        # Should have errors
        assert "errors" in data


@pytest.mark.asyncio
class TestIssueUpdate:
    async def test_update_issue_state(self, linear_client: AsyncClient):
        """Test updating issue state."""
        query = """
          mutation($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
              success
              issue {
                id
                state {
                  id
                  name
                }
              }
            }
          }
        """
        variables = {
            "id": ISSUE_ENG_001,
            "input": {"stateId": STATE_IN_PROGRESS},
        }
        response = await linear_client.post(
            "/graphql", json={"query": query, "variables": variables}
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        result = data["data"]["issueUpdate"]
        assert result["success"] is True
        issue = result["issue"]
        assert issue["state"]["id"] == STATE_IN_PROGRESS
        assert issue["state"]["name"] == "In Progress"


# ==========================================
# TIER 2 TESTS: Common Operations
# ==========================================


@pytest.mark.asyncio
class TestSearchIssues:
    async def test_search_issues_by_text(self, linear_client: AsyncClient):
        """Test full-text search across issues."""
        query = """
          query($term: String!) {
            searchIssues(term: $term) {
              nodes {
                id
                identifier
                title
              }
            }
          }
        """
        variables = {"term": "authentication"}
        response = await linear_client.post(
            "/graphql", json={"query": query, "variables": variables}
        )
        assert response.status_code == 200
        data = response.json()
        issues = data["data"]["searchIssues"]["nodes"]
        # Should find at least the "Fix authentication bug in login flow" issue
        assert len(issues) >= 1
        assert any("authentication" in issue["title"].lower() for issue in issues)

    async def test_search_issues_no_results(self, linear_client: AsyncClient):
        """Test search with no matching results."""
        query = """
          query($term: String!) {
            searchIssues(term: $term) {
              nodes {
                id
                title
              }
            }
          }
        """
        variables = {"term": "NONEXISTENT_SEARCH_TERM_12345"}
        response = await linear_client.post(
            "/graphql", json={"query": query, "variables": variables}
        )
        assert response.status_code == 200
        data = response.json()
        issues = data["data"]["searchIssues"]["nodes"]
        assert len(issues) == 0


@pytest.mark.asyncio
class TestCommentCreate:
    async def test_create_comment_basic(self, linear_client: AsyncClient):
        """Test creating a comment on an issue."""
        query = """
          mutation($input: CommentCreateInput!) {
            commentCreate(input: $input) {
              success
              comment {
                id
                body
                issue {
                  id
                }
                user {
                  id
                  name
                }
              }
            }
          }
        """
        variables = {
            "input": {
                "issueId": ISSUE_ENG_001,
                "body": "This is a test comment from integration test",
            }
        }
        response = await linear_client.post(
            "/graphql", json={"query": query, "variables": variables}
        )
        assert response.status_code == 200
        data = response.json()
        result = data["data"]["commentCreate"]
        assert result["success"] is True
        comment = result["comment"]
        assert comment["body"] == "This is a test comment from integration test"
        assert comment["issue"]["id"] == ISSUE_ENG_001
        assert comment["user"]["id"] == "U01AGENT"

    async def test_create_comment_invalid_issue(self, linear_client: AsyncClient):
        """Test creating a comment with invalid issueId fails."""
        query = """
          mutation($input: CommentCreateInput!) {
            commentCreate(input: $input) {
              success
              comment {
                id
              }
            }
          }
        """
        variables = {
            "input": {
                "issueId": "INVALID_ISSUE_ID",
                "body": "This should fail",
            }
        }
        response = await linear_client.post(
            "/graphql", json={"query": query, "variables": variables}
        )
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data


@pytest.mark.asyncio
class TestTeamCreate:
    async def test_create_team_basic(self, linear_client: AsyncClient):
        """Test creating a new team."""
        query = """
          mutation($input: TeamCreateInput!) {
            teamCreate(input: $input) {
              success
              team {
                id
                name
                key
              }
            }
          }
        """
        variables = {
            "input": {
                "name": "Product Team",
                "key": "PROD",
            }
        }
        response = await linear_client.post(
            "/graphql", json={"query": query, "variables": variables}
        )
        assert response.status_code == 200
        data = response.json()
        result = data["data"]["teamCreate"]
        assert result["success"] is True
        team = result["team"]
        assert team["name"] == "Product Team"
        assert team["key"] == "PROD"

    async def test_create_team_duplicate_key(self, linear_client: AsyncClient):
        """Test creating team with duplicate key fails."""
        query = """
          mutation($input: TeamCreateInput!) {
            teamCreate(input: $input) {
              success
              team {
                id
              }
            }
          }
        """
        variables = {
            "input": {
                "name": "Another Engineering Team",
                "key": "ENG",  # This key already exists
            }
        }
        response = await linear_client.post(
            "/graphql", json={"query": query, "variables": variables}
        )
        assert response.status_code == 200
        data = response.json()
        assert "errors" in data


@pytest.mark.asyncio
class TestIssueBatchCreate:
    async def test_batch_create_issues(self, linear_client: AsyncClient):
        """Test creating multiple issues at once."""
        query = """
          mutation($input: IssueBatchCreateInput!) {
            issueBatchCreate(input: $input) {
              success
              issues {
                id
                title
                team {
                  id
                  key
                }
              }
            }
          }
        """
        variables = {
            "input": {
                "issues": [
                    {"teamId": TEAM_ENG, "title": "Batch issue 1"},
                    {"teamId": TEAM_ENG, "title": "Batch issue 2"},
                    {"teamId": TEAM_ENG, "title": "Batch issue 3"},
                ]
            }
        }
        response = await linear_client.post(
            "/graphql", json={"query": query, "variables": variables}
        )
        assert response.status_code == 200
        data = response.json()
        result = data["data"]["issueBatchCreate"]
        assert result["success"] is True
        issues = result["issues"]
        assert len(issues) == 3
        assert all(issue["team"]["key"] == "ENG" for issue in issues)
        assert issues[0]["title"] == "Batch issue 1"

    async def test_batch_create_mixed_teams(self, linear_client: AsyncClient):
        """Test batch creating issues with different titles in same team."""
        query = """
          mutation($input: IssueBatchCreateInput!) {
            issueBatchCreate(input: $input) {
              success
              issues {
                id
                title
                team {
                  key
                }
              }
            }
          }
        """
        variables = {
            "input": {
                "issues": [
                    {"teamId": TEAM_ENG, "title": "First engineering issue"},
                    {"teamId": TEAM_ENG, "title": "Second engineering issue"},
                ]
            }
        }
        response = await linear_client.post(
            "/graphql", json={"query": query, "variables": variables}
        )
        assert response.status_code == 200
        data = response.json()
        result = data["data"]["issueBatchCreate"]
        assert result["success"] is True
        issues = result["issues"]
        assert len(issues) == 2
        assert issues[0]["team"]["key"] == "ENG"
        assert issues[1]["team"]["key"] == "ENG"
        assert issues[0]["title"] == "First engineering issue"
        assert issues[1]["title"] == "Second engineering issue"


# ==========================================
# TIER 2 TESTS: Label Operations
# ==========================================


@pytest.mark.asyncio
class TestIssueLabelCreate:
    async def test_create_label_basic(self, linear_client: AsyncClient):
        """Test creating a new issue label."""
        query = """
          mutation($input: IssueLabelCreateInput!) {
            issueLabelCreate(input: $input) {
              success
              issueLabel {
                id
                name
                color
                team {
                  id
                  key
                }
              }
            }
          }
        """
        variables = {
            "input": {
                "name": "Bug",
                "color": "#e5484d",
                "teamId": TEAM_ENG,
            }
        }
        response = await linear_client.post(
            "/graphql", json={"query": query, "variables": variables}
        )
        assert response.status_code == 200
        data = response.json()
        result = data["data"]["issueLabelCreate"]
        assert result["success"] is True
        label = result["issueLabel"]
        assert label["name"] == "Bug"
        assert label["color"] == "#e5484d"
        assert label["team"]["key"] == "ENG"

    async def test_create_label_without_team(self, linear_client: AsyncClient):
        """Test creating an organization-wide label (no team)."""
        query = """
          mutation($input: IssueLabelCreateInput!) {
            issueLabelCreate(input: $input) {
              success
              issueLabel {
                id
                name
                color
              }
            }
          }
        """
        variables = {
            "input": {
                "name": "Priority",
                "color": "#f76808",
            }
        }
        response = await linear_client.post(
            "/graphql", json={"query": query, "variables": variables}
        )
        assert response.status_code == 200
        data = response.json()
        result = data["data"]["issueLabelCreate"]
        assert result["success"] is True
        label = result["issueLabel"]
        assert label["name"] == "Priority"
        assert label["color"] == "#f76808"


@pytest.mark.asyncio
class TestIssueLabels:
    async def test_add_label_to_issue(self, linear_client: AsyncClient):
        """Test adding a label to an issue."""
        # First, create a label
        create_label_query = """
          mutation($input: IssueLabelCreateInput!) {
            issueLabelCreate(input: $input) {
              success
              issueLabel {
                id
                name
              }
            }
          }
        """
        create_variables = {
            "input": {
                "name": "Frontend",
                "color": "#3b82f6",
                "teamId": TEAM_ENG,
            }
        }
        create_response = await linear_client.post(
            "/graphql", json={"query": create_label_query, "variables": create_variables}
        )
        assert create_response.status_code == 200
        create_data = create_response.json()
        label_id = create_data["data"]["issueLabelCreate"]["issueLabel"]["id"]

        # Now add the label to an issue
        add_label_query = """
          mutation($id: String!, $labelId: String!) {
            issueAddLabel(id: $id, labelId: $labelId) {
              success
              issue {
                id
                labels {
                  nodes {
                    id
                    name
                  }
                }
              }
            }
          }
        """
        add_variables = {
            "id": ISSUE_ENG_001,
            "labelId": label_id,
        }
        add_response = await linear_client.post(
            "/graphql", json={"query": add_label_query, "variables": add_variables}
        )
        assert add_response.status_code == 200
        add_data = add_response.json()
        result = add_data["data"]["issueAddLabel"]
        assert result["success"] is True
        labels = result["issue"]["labels"]["nodes"]
        assert len(labels) >= 1
        assert any(label["id"] == label_id for label in labels)
        assert any(label["name"] == "Frontend" for label in labels)

    async def test_remove_label_from_issue(self, linear_client: AsyncClient):
        """Test removing a label from an issue."""
        # First, create a label and add it to an issue
        create_label_query = """
          mutation($input: IssueLabelCreateInput!) {
            issueLabelCreate(input: $input) {
              issueLabel {
                id
              }
            }
          }
        """
        create_response = await linear_client.post(
            "/graphql",
            json={
                "query": create_label_query,
                "variables": {
                    "input": {
                        "name": "Backend",
                        "color": "#10b981",
                        "teamId": TEAM_ENG,
                    }
                },
            },
        )
        label_id = create_response.json()["data"]["issueLabelCreate"]["issueLabel"]["id"]

        # Add the label
        await linear_client.post(
            "/graphql",
            json={
                "query": """
                  mutation($id: String!, $labelId: String!) {
                    issueAddLabel(id: $id, labelId: $labelId) {
                      success
                    }
                  }
                """,
                "variables": {"id": ISSUE_ENG_001, "labelId": label_id},
            },
        )

        # Now remove the label
        remove_query = """
          mutation($id: String!, $labelId: String!) {
            issueRemoveLabel(id: $id, labelId: $labelId) {
              success
              issue {
                id
                labels {
                  nodes {
                    id
                    name
                  }
                }
              }
            }
          }
        """
        remove_variables = {
            "id": ISSUE_ENG_001,
            "labelId": label_id,
        }
        remove_response = await linear_client.post(
            "/graphql", json={"query": remove_query, "variables": remove_variables}
        )
        assert remove_response.status_code == 200
        remove_data = remove_response.json()
        result = remove_data["data"]["issueRemoveLabel"]
        assert result["success"] is True
        labels = result["issue"]["labels"]["nodes"]
        # Label should be removed
        assert not any(label["id"] == label_id for label in labels)


@pytest.mark.asyncio
class TestIssueLabelUpdate:
    async def test_update_label(self, linear_client: AsyncClient):
        """Test updating a label's properties."""
        # First create a label
        create_query = """
          mutation($input: IssueLabelCreateInput!) {
            issueLabelCreate(input: $input) {
              issueLabel {
                id
              }
            }
          }
        """
        create_response = await linear_client.post(
            "/graphql",
            json={
                "query": create_query,
                "variables": {
                    "input": {
                        "name": "Old Name",
                        "color": "#000000",
                        "teamId": TEAM_ENG,
                    }
                },
            },
        )
        label_id = create_response.json()["data"]["issueLabelCreate"]["issueLabel"]["id"]

        # Update the label
        update_query = """
          mutation($id: String!, $input: IssueLabelUpdateInput!) {
            issueLabelUpdate(id: $id, input: $input) {
              success
              issueLabel {
                id
                name
                color
              }
            }
          }
        """
        update_variables = {
            "id": label_id,
            "input": {
                "name": "New Name",
                "color": "#ffffff",
            },
        }
        update_response = await linear_client.post(
            "/graphql", json={"query": update_query, "variables": update_variables}
        )
        assert update_response.status_code == 200
        update_data = update_response.json()
        result = update_data["data"]["issueLabelUpdate"]
        assert result["success"] is True
        label = result["issueLabel"]
        assert label["name"] == "New Name"
        assert label["color"] == "#ffffff"


@pytest.mark.asyncio
class TestIssueLabelDelete:
    async def test_delete_label(self, linear_client: AsyncClient):
        """Test deleting a label."""
        # First create a label
        create_query = """
          mutation($input: IssueLabelCreateInput!) {
            issueLabelCreate(input: $input) {
              issueLabel {
                id
              }
            }
          }
        """
        create_response = await linear_client.post(
            "/graphql",
            json={
                "query": create_query,
                "variables": {
                    "input": {
                        "name": "Temporary",
                        "color": "#888888",
                        "teamId": TEAM_ENG,
                    }
                },
            },
        )
        label_id = create_response.json()["data"]["issueLabelCreate"]["issueLabel"]["id"]

        # Delete the label
        delete_query = """
          mutation($id: String!) {
            issueLabelDelete(id: $id) {
              success
            }
          }
        """
        delete_variables = {"id": label_id}
        delete_response = await linear_client.post(
            "/graphql", json={"query": delete_query, "variables": delete_variables}
        )
        assert delete_response.status_code == 200
        delete_data = delete_response.json()
        result = delete_data["data"]["issueLabelDelete"]
        assert result["success"] is True
