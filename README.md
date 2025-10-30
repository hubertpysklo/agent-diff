# Agent Diff


## What This Is

**A self-hosted interactive enviroments for testing AI agents & training LLMs against 3rd party services like Linear or Slack.** You run it locally (or deploy it), your agents call fake APIs, you get deterministic diffs. No external service, no rate limits, full control over test data and environments.

Use it for:
- RL training loops (reset state between episodes)
- Integration tests (verify agent does what it should)
- Regression tests (catch when changes break behaviour)
- Training data generation (prompt → actions → diff → outcome)


## Quick Start

### 1. Install SDK
```bash
uv add agent-diff
```

### 2. Set up backend
```bash
git clone https://github.com/hubertpysklo/agent-diff.git
cd agent-diff
cp env.example .env
cd ops
docker-compose up --build

# Backend runs on http://localhost:8000
```

### 3. Flow
```python
from agent_diff import AgentDiff

# For self-hosting (no API key)
client = AgentDiff(base_url="http://localhost:8000")

# For service (with API key)
client = AgentDiff(
    api_key="your-api-key",
    base_url="https://api.yourdomain.com"
)

# Initialise isolated environment from template
env = client.init_env(templateService="slack", templateName="slack_default", impersonateUserId="U01AGENBOT9")

# Take before snapshot
run = client.start_run(envId=env.environmentId)


# Your agent does stuff using the environment URL 
# You can either use a sidecar proxy (package coming soon) or swap the URLs directly in MCPs
# e.g. proxt GET for /api/env/{envId}/services/slack/conversations.list
# from https://slack.com/api/conversations.list 
# to http://localhost:8000/api/env/c49bc3c27a4d468ea12a572c6b0b5bd0/services/slack/conversations.list 

# Compute diff and get results
diff = client.diff_run(runId=run.runId)

# Inspect changes
print(diff.diff['inserts'])   # New records
print(diff.diff['updates'])   # Modified records
print(diff.diff['deletes'])   # Deleted records

# Clean up
client.delete_env(envId=env.environmentId)
```

Every environment gets its own PostgreSQL schema. URLs bind requests to schemas. Snapshots diff exactly what changed in this specific isolated environment.

## Templates & Test Suites

### Sample Templates
- **[slack_base](examples/slack/seeds/)** - Empty Slack workspace (no seed data)
- **[slack_default](examples/slack/seeds/slack_default.json)** - Seeded with sample users and messages 

### Test Suites (DSL)
- **[slack_bench.json](examples/slack/testsuites/slack_bench.json)** - test cases covering message sending, channel ops, reactions, threading
- **[Evaluation DSL](docs/evaluation-dsl.md)** - Check DSL docs on how it works.

## Services

- **Slack** – core Web API coverage for conversations, chat, reactions, users, etc. Full list here [`backend/src/services/slack/READEME.MD`](backend/src/services/slack/READEME.md). A few examples:

  ```python
  "chat.postMessage"  # post messages in seeded channels/DMs
  "conversations.open"  # spin up IM/MPIM threads
  "reactions.add"  # add emoji reactions to seeded messages
  ```

- **Linear** – GraphQL schema and resolvers for issues/projects (still WIP). See [`backend/src/services/linear/READEME.MD`](backend/src/services/linear/READEME.MD). Sample operations:

  ```python
  "issues"            # query issues (list/pagination)
  "issueCreate"       # mutation to create an issue
  "projectUpdate"     # mutation to update project metadata
  ```

- Gmail, GitHub, Jira (TBD).

If you have requests for specific services + any feedback, mail me at hubert@uni.minerva.edu

## Documentation

- **[Getting Started Guide](docs/getting-started.md)** - Detailed setup and configuration
- **[SDK README](sdk/agent_diff_pkg/README.md)** - Complete API reference
- **[Evaluation DSL](docs/evaluation-dsl.md)** - Write test assertions
- **[API Reference](docs/api-reference.md)** - REST API documentation

