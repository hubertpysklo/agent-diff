# Diff the Universe

Diff the Universe lets you evaluate AI agents against controllable clones of real-world services (Linear, Slack, Gmail, …). The platform provisions isolated database schemas for each run, routes agent traffic into service facsimiles, snapshots state before/after the agent acts, and computes deterministic diffs so you can assert the outcome programmatically.


## Currently supported services:
- Slack (fully implemented)
- Linear (in progress)


## Quick start

```bash
# Set up environment variables
cp env.example .env
# Edit .env to set SECRET_KEY if needed

# Start everything with Docker
cd ops
docker-compose up --build

# Backend runs on http://localhost:8000
# PostgreSQL runs on localhost:5432
```

The backend automatically runs migrations and seeds a development user on startup. Check the logs for your API key:

```bash
docker-compose logs backend | grep "Dev API Key"
# Dev API Key: ak_xxxxx...
```

Test the health endpoint:

```bash
curl http://localhost:8000/api/platform/health
# Returns: {"status":"healthy","service":"diff-the-universe"}
```

## Using the Platform

All API requests require authentication via API key:

```bash
# Using X-API-Key header
curl -H "X-API-Key: ak_xxxxx..." http://localhost:8000/api/platform/...

# Or using Authorization header
curl -H "Authorization: ak_xxxxx..." http://localhost:8000/api/platform/...
```

Here's how agents interact with the platform:

1. Create an isolated test environment
2. Agent performs actions (posts Slack messages, creates Linear issues, etc.)
3. Platform captures what changed and validates against expected outcomes

All agent requests go to `/api/env/{environmentId}/services/slack/...` and are automatically isolated to that environment's database.

Full API documentation: [`docs/api-reference.md`](docs/api-reference.md)

## How it works

1. `POST /api/platform/initEnv` clones a template schema into a dedicated environment.
2. `POST /api/platform/startRun` snapshots the environment before the agent acts.
3. The agent talks to fake service endpoints under `/api/env/{envId}/services/slack/...`.
4. `POST /api/platform/endRun` snapshots again, computes the diff, runs assertions, and stores the result.
5. `GET /api/platform/results/{runId}` returns pass/fail, score, diff, and failure messages.

Detailed sequence: [`docs/platform-rest-flow.md`](docs/platform-rest-flow.md)

### Evaluation DSL example

```json
{
  "strict": true,
  "assertions": [
    {
      "diff_type": "added",
      "entity": "messages",
      "where": {
        "channelId": {"eq": 123},
        "body": {"contains": "hello"}
      },
      "expected_count": 1
    },
    {
      "diff_type": "changed",
      "entity": "issues",
      "where": {"id": {"eq": 42}},
      "expected_changes": {
        "status": {"to": {"eq": "Done"}}
      }
    }
  ]
}
```

Full DSL docs: [`docs/evaluation-dsl.md`](docs/evaluation-dsl.md)

## Repository layout

- `docs/` – platform workflows, evaluation DSL, release checklist
- `scripts/` – local dev helpers (seed DB, reset schema, etc.)
- `examples/` – sample evaluation suites (coming soon)
- `backend/` – Starlette app, isolation engine, evaluation engine, service mocks

