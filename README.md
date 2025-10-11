# Diff the Universe

Diff the Universe lets you evaluate AI agents against controllable clones of real-world services (Linear, Slack, Gmail, …). The platform provisions isolated database schemas for each run, routes agent traffic into service facsimiles, snapshots state before/after the agent acts, and computes deterministic diffs so you can assert the outcome programmatically.


## Currently supported services:
- Linear
- Slack


## Quick start

```bash
cp env.example .env        # fill in database URL & secret key
uv sync                    # install backend dependencies
docker compose up -d       # start Postgres + fake services
uv run alembic upgrade head
uv run backend/src/app.py  # or use make backend-dev
```

Then hit the REST API with an API key (seed one manually for now).

## How it works

1. `POST /api/platform/initEnv` clones a template schema into a dedicated environment.
2. `POST /api/platform/startRun` snapshots the environment before the agent acts.
3. The agent talks to fake service endpoints under `/api/env/{envId}/services/...`.
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

