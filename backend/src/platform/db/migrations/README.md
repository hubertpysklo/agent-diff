# Platform migrations

Alembic migrations live here. They cover:

- Platform metadata (users, organizations, API keys, environments, diffs)
- Service schemas (Slack, Linear, Gmail, …)

## Commands

```bash
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "add whatever"
```

Make sure `DATABASE_URL` is set in your environment before running.

