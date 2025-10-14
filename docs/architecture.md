# Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Platform API                         │
│  /api/platform/{initEnv, startRun, endRun, results}        │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
┌──────────────┐  ┌─────────────┐  ┌──────────────┐
│  Isolation   │  │ Evaluation  │  │   Service    │
│    Engine    │  │   Engine    │  │    APIs      │
└──────┬───────┘  └──────┬──────┘  └───────┬──────┘
       │                 │                 │
       │   ┌─────────────┴─────────────┐   │
       │   │         Differ            │   │
       │   │  (Snapshot + Diff Logic)  │   │
       │   └───────────────────────────┘   │
       │                                   │
       └───────────────┬───────────────────┘
                       │
               ┌───────▼────────┐
               │   PostgreSQL   │
               │  - platform DB │
               │  - state_*     │
               │    schemas     │
               └────────────────┘
```

## Core Components

### 1. Isolation Engine

**Purpose**: Creates and manages isolated test environments.

**Location**: `backend/src/platform/isolationEngine/`

**Key Classes**:

- **`CoreIsolationEngine`**: Main coordinator
  - Creates environments
  - Manages environment lifecycle
  - Tracks active environments in `RunTimeEnvironment` table

- **`EnvironmentHandler`**: Schema operations
  - Creates PostgreSQL schemas (`state_abc123`)
  - Copies table structure from templates
  - Seeds initial data
  - Drops schemas on cleanup

- **`SessionManager`**: Database session routing
  - Provides sessions scoped to specific schemas
  - Uses SQLAlchemy's `schema_translate_map` for dynamic routing
  - One connection pool serves all schemas

- **`TokenHandler`**: JWT token management
  - Issues tokens with `environment_id`, `user_id`, `impersonate_user_id`
  - Validates tokens on every request
  - Tokens bind agents to their isolated environment

**Flow**:

```python
1. User calls initEnv(template="slack_default")
2. CoreIsolationEngine.create_environment():
   - Generates unique environment_id
   - EnvironmentHandler creates schema "state_abc123"
   - Copies table structure from "slack_default"
   - Seeds data from examples/slack/seeds/slack_default.json
   - TokenHandler issues JWT with environment_id
   - Stores in RunTimeEnvironment table with TTL
3. Returns: {environment_id, schema_name, token, expires_at}
```

### 2. Evaluation Engine

**Purpose**: Captures state changes and validates them against expectations.

**Location**: `backend/src/platform/evaluationEngine/`

**Key Classes**:

- **`Differ`**: Snapshot and diff logic
  - `create_snapshot(suffix)`: Creates `{table}_snapshot_{suffix}` tables
  - `get_inserts/updates/deletes()`: SQL queries to compute diffs
  - Uses dynamic primary key detection (works with any schema)
  - Handles composite PKs correctly

- **`DSLCompiler`**: Compiles JSON specs
  - Validates against `dsl_schema.json`
  - Normalizes shorthand syntax (`"value"` → `{"eq": "value"}`)
  - Returns executable spec for AssertionEngine

- **`AssertionEngine`**: Evaluates assertions
  - Takes diff + compiled spec
  - Matches rows using predicates (eq, contains, gt, etc.)
  - Checks counts (exact or min/max ranges)
  - Validates expected changes in strict/non-strict mode
  - Returns: `{passed, failures, score}`

- **`TestManager`**: Orchestrates test lifecycle
  - Creates environment
  - Takes before snapshot
  - Runs agent
  - Takes after snapshot
  - Computes diff
  - Evaluates assertions

**Flow**:

```python
1. User calls startRun(env_id, test_spec)
2. TestManager:
   - Differ.create_snapshot("before")
   - Stores run metadata in database
   - Returns run_id
3. Agent performs actions via service APIs
4. User calls endRun(run_id)
5. TestManager:
   - Differ.create_snapshot("after")
   - Differ.get_diff("before", "after")
   - DSLCompiler.compile(test_spec)
   - AssertionEngine.evaluate(diff, compiled_spec)
   - Differ.store_diff() - saves to platform DB
   - Returns: {passed, score, diff, failures}
```

### 3. Services Layer

**Purpose**: Fake service APIs (Slack, Linear, etc.) that agents interact with.

**Location**: `backend/src/services/{slack,linear}/`

**Structure** (per service):

```
services/slack/
├── api/            # API endpoints (GraphQL/REST)
├── core/           # Business logic
├── database/       # Schema definitions + operations
└── seed_utils/     # Template seeding
```

**Key Patterns**:

- **Schema Isolation**: All queries use `schema_translate_map`
  ```python
  # JWT token contains environment_id
  # SessionManager provides scoped session
  # SQLAlchemy routes to correct schema automatically
  ```

- **1:1 API Compatibility**: Replicate real API behavior
  - Same HTTP methods, paths, request/response formats
  - Same error codes and messages
  - Same business logic (e.g., Slack channel name validation)

- **No Hardcoded IDs**: Use template IDs
  - Templates define stable IDs (e.g., `U01AGENBOT9`)
  - Tests reference these IDs
  - Every environment gets identical starting state

### 4. Platform API

**Purpose**: Orchestrates environment creation, test runs, and result retrieval.

**Location**: `backend/src/platform/api/`

**Key Files**:

- **`main.py`**: Starlette app factory
  - Wires up engines (Isolation, Evaluation)
  - Registers routes
  - Configures middleware (CORS, auth)

- **`platform_graphql.py`**: Platform GraphQL API
  - Separate from service APIs
  - Used for platform operations only

- **`auth.py`**: Authentication middleware
  - Validates API keys (platform endpoints)
  - Validates JWT tokens (service endpoints)
  - Decodes environment_id from token

**Request Flow**:

```
Agent Request → auth.py validates JWT
             → Decodes environment_id from token
             → SessionManager provides schema-scoped session
             → Service API executes in isolated schema
             → Response
```

## Data Flow


### Environment Creation

```
User → POST /api/platform/initEnv
  ↓
CoreIsolationEngine.create_environment()
  ↓
EnvironmentHandler.create_schema()
  - CREATE SCHEMA state_abc123
  - Copy table structure from slack_default
  - Seed data from JSON
  ↓
TokenHandler.issue_token()
  - JWT with {environment_id, user_id, impersonate_user_id}
  ↓
Store in RunTimeEnvironment table
  - environment_id, schema_name, created_by, expires_at
  ↓
Return {environment_id, token, schema_name, expires_at}
```

### Test Execution

```
User → POST /api/platform/startRun
  ↓
Differ.create_snapshot("before")
  - CREATE TABLE messages_snapshot_before AS SELECT * FROM messages
  - CREATE TABLE channels_snapshot_before AS SELECT * FROM channels
  - ... (all tables)
  ↓
Store run metadata
  ↓
Return run_id
  ↓
Agent → POST /api/env/{env_id}/services/slack/chat.postMessage
  ↓
auth.py validates token → extracts environment_id
  ↓
SessionManager routes to state_abc123 schema
  ↓
Slack API writes to state_abc123.messages
  ↓
Return response to agent
  ↓
User → POST /api/platform/endRun
  ↓
Differ.create_snapshot("after")
  ↓
Differ.get_diff("before", "after")
  - SQL: SELECT * FROM after LEFT JOIN before WHERE before.id IS NULL (inserts)
  - SQL: SELECT * FROM after JOIN before WHERE cols differ (updates)
  - SQL: SELECT * FROM before LEFT JOIN after WHERE after.id IS NULL (deletes)
  ↓
DSLCompiler.compile(test_spec)
  ↓
AssertionEngine.evaluate(diff, compiled_spec)
  - Match rows by where clauses
  - Check counts
  - Validate expected_changes
  ↓
Return {passed, score, diff, failures}
```

