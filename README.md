# Diff the Universe

Evaluate AI agents by testing them against fake versions of real services.


### Quickstart
- Prereqs: Python 3.13, Docker, Postgres
- Setup:
```bash
cp env.example .env
docker compose up -d
uv run uvicorn backend.src.platform.api.main:app --reload
```
- Key env vars:
  - DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/db
  - SECRET_KEY=dev-secret               # JWT for env tokens
  - PLATFORM_API_KEY=dev-api-key        # Platform GraphQL auth

### What’s inside
- Isolation Engine
  - Schema-per-run; create schema → mirror structure → seed data
  - SessionManager: meta sessions, schema sessions, token sessions
- Platform API
  - /platform/graphql: API key auth, meta DB ops (create env, etc.)
  - /linear/graphql: JWT auth, env-routed mock Linear API
- Evaluation Engine
  - Snapshot schema → SQL joins on PK → inserts/deletes/updates (per-field deltas)
  - Assertion DSL: expected inserts/updates, forbidden, invariants

### How it works (high-level)
1. Create isolated env from a template schema
2. Issue JWT with environment_id; agent calls mock APIs using Authorization: Bearer <jwt>
3. For evals, take baseline and final snapshots; compute table deltas via SQL
4. Run assertions against normalized deltas (no LLM judging needed)

### Minimal usage

- Start platform (as above)
- Create an environment (platform resolver will do):
  - Validate API key (X-API-Key)
  - Call core to create schema state_<id>, mirror structure from template, seed
  - Insert RunTimeEnvironment(status=ready), return environment_id
  - Issue JWT: sub=user_id, environment_id=<id>
- Call mock service with token:
```
Authorization: Bearer <jwt>
POST /linear/graphql
```

- Run a diff (Python) using the evaluation engine:
```python
from backend.src.platform.evalutionEngine.differ import Differ
from backend.src.platform.isolationEngine.session import SessionManager
from sqlalchemy import create_engine

engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
sessions = SessionManager(engine, token_handler=None)   # token not needed for diffs
differ = Differ(schema="state_ABC123", session_manager=sessions)

differ.create_snapshot(suffix="before")
# ... run agent ...
differ.create_snapshot(suffix="after")

ins = differ.get_inserts("before", "after")
del_ = differ.get_deletes("before", "after")
upd = differ.get_updates("before", "after", ignore_cols=["createdAt","updatedAt","archivedAt"])
```

### Architecture
- Platform GraphQL (meta): validates API keys, manages env lifecycle, may trigger evals
- Service GraphQL (env): schema-translated sessions, mock APIs for agents
- Proxy (optional): captures request logs; auto-steps on mutating calls
- Postgres: meta schema (“meta.*”) + per-run schemas (“state_*”)

### Design choices
- Pure SQL for snapshot/diff (set-based, fast at 10k–100k rows)
- Schema-qualified names, one connection per transaction
- Inspector-based reflection for PKs and tables
- JWT for env routing; API-key for platform

### Development
```bash
uv run ruff check .
uv run ruff format .
uv run pytest   # when tests are added
```

### Repo map
- backend/src/platform/isolationEngine/
  - environment.py: create/mirror/seed/register env
  - session.py: meta/env/token sessions
  - auth.py: JWT
- backend/src/platform/evalutionEngine/
  - differ.py: snapshot schema + SQL diff
  - (assertions.py, core.py): assertion DSL and orchestration (WIP)
- backend/src/platform/api/
  - main.py, platform_graphql.py, auth.py
- backend/src/services/linear/
  - db/db_schema.py, api/graphql_linear.py

### License
TBD (open-core vs closed).
