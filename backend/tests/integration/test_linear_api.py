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
