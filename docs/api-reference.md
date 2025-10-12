# API Reference

## Base URL

```
http://localhost:8000
```

## Authentication

All platform and service endpoints require authentication via API key:

```bash
-H "X-API-Key: ak_{key_id}_{secret}"
```

**Note:** API keys must be manually seeded in the database currently.

---

## Platform API

Platform endpoints for managing test environments and runs.

### Health Check

```http
GET /api/platform/health
```

Returns platform health status.

**Response:**
```json
{
  "status": "healthy",
  "service": "diff-the-universe"
}
```

---

### List Test Suites

```http
GET /api/platform/testSuites
```

Returns all test suites.

**Note:** Test suites are currently read-only via API. Must be created directly in database.

**Response:**
```json
[
  {
    "id": "suite-123",
    "name": "Slack Agent Tests",
    "tests": [...]
  }
]
```

---

### Get Test Suite

```http
GET /api/platform/testSuites/{suiteId}
```

Returns a specific test suite with its tests.

**Response:**
```json
{
  "id": "suite-123",
  "name": "Slack Agent Tests",
  "tests": [
    {
      "id": "test-456",
      "name": "Post message to channel",
      "prompt": "Post 'Hello' to #general",
      "expectedOutput": {...}
    }
  ]
}
```

---

### Initialize Environment

```http
POST /api/platform/initEnv
```

Creates an isolated test environment with its own database schema.

**Request Body:**
```json
{
  "testId": "test-123",
  "ttlSeconds": 1800,
  "templateSchema": "slack_template",
  "impersonateUserId": "U123",
  "impersonateEmail": "agent@example.com"
}
```

**Parameters:**
- `testId` (string, required) - ID of the test definition
- `ttlSeconds` (number, optional) - Time-to-live in seconds (default: 1800)
- `templateSchema` (string, optional) - Template schema to clone from
- `impersonateUserId` (string, optional) - User ID to impersonate in services
- `impersonateEmail` (string, optional) - Email to impersonate in services

**Response:**
```json
{
  "environmentId": "abc123",
  "environmentUrl": "/api/env/abc123",
  "expiresAt": "2025-10-12T20:00:00Z",
  "schemaName": "state_abc123"
}
```

---

### Start Test Run

```http
POST /api/platform/startRun
```

Takes a "before" snapshot of the environment state.

**Request Body:**
```json
{
  "testId": "test-123",
  "testSuiteId": "suite-456",
  "envId": "abc123"
}
```

**Response:**
```json
{
  "runId": "run-789",
  "status": "running",
  "beforeSnapshot": "before_abc123_1234567890"
}
```

---

### End Test Run

```http
POST /api/platform/endRun
```

Takes an "after" snapshot, computes diff, evaluates assertions.

**Request Body:**
```json
{
  "runId": "run-789",
  "envId": "abc123"
}
```

**Response:**
```json
{
  "runId": "run-789",
  "status": "completed",
  "result": "pass",
  "score": 1.0,
  "diff": {
    "inserts": [...],
    "updates": [...],
    "deletes": [...]
  }
}
```

---

### Get Test Results

```http
GET /api/platform/results/{runId}
```

Retrieves results for a completed test run.

**Response:**
```json
{
  "runId": "run-789",
  "status": "completed",
  "result": "pass",
  "score": 1.0,
  "failures": [],
  "diff": {...}
}
```

---

### Delete Environment

```http
DELETE /api/platform/env/{envId}
```

Cleans up an environment and its database schema.

**Response:**
```json
{
  "environmentId": "abc123",
  "status": "deleted"
}
```

---

## Service APIs

Service endpoints mimic real service APIs but are isolated per environment.

### Slack API

Base path: `/api/env/{envId}/services/slack`

Implements Slack Web API methods:

#### Post Message

```http
POST /api/env/{envId}/services/slack/chat.postMessage
```

**Request Body:**
```json
{
  "channel": "C123456",
  "text": "Hello from agent!",
  "thread_ts": "1234567890.123456"
}
```

#### List Conversations

```http
GET /api/env/{envId}/services/slack/conversations.list
```

**Query Parameters:**
- `types` - Comma-separated list (e.g., "public_channel,private_channel")
- `limit` - Number of results to return

#### Get User Info

```http
GET /api/env/{envId}/services/slack/users.info?user=U123456
```

See [Slack Web API documentation](https://api.slack.com/web) for full method details.

---

### Linear API

Base path: `/api/env/{envId}/services/linear`

**Status:** In progress

Will implement Linear's GraphQL API at `/api/env/{envId}/services/linear/graphql`.

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "ok": false,
  "error": "error_code",
  "detail": "Human-readable error message"
}
```

Common error codes:
- `not_authed` - Missing or invalid API key
- `invalid_environment_path` - Malformed environment ID
- `environment_not_found` - Environment doesn't exist or expired
- `internal_error` - Server error

