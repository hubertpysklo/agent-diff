# Agent Diff


## What This Is

**A self-hosted interactive enviroments for testing AI agents & training LLMs against 3rd party services like Linear or Slack.** You run it locally (or deploy it), your agents call fake APIs, you get deterministic diffs. No external service, no API keys to manage, full control over test data.

Use it for:
- RL training loops (reset state between episodes)
- Integration tests (verify agent does what it should)
- Regression tests (catch when changes break behavior)
- Training data generation (prompt → actions → diff → outcome)


## Flow

```python
from agent_diff import AgentDiff

client = AgentDiff(api_key="your-key", base_url="http://localhost:8000")

# 1. Initialize isolated environment from template
env = client.init_env(templateService="slack", templateName="slack_default", impersonateUserId="U01AGENBOT9")

# 2. Take before snapshot
run = client.start_run(envId=env.environmentId)

# 3. Your agent does stuff using the environment URL
# e.g., POST to env.url + "/services/slack/chat.postMessage"

# 4. Compute diff and get results
diff = client.diff_run(envId=env.environmentId, runId=run.runId)

# Inspect changes
diff.diff['inserts']   # New records
diff.diff['updates']   # Modified records
diff.diff['deletes']   # Deleted records

# 5. Clean up
client.delete_env(envId=env.environmentId)
```

Every environment gets its own PostgreSQL schema. URLs bind requests to schemas. Snapshots diff exactly what changed in this specific isolated environment.

## Templates & Test Suites

### Sample Templates
- **[slack_base](examples/slack/seeds/)** - Empty Slack workspace (no seed data)
- **[slack_default](examples/slack/seeds/slack_default.json)** - Seeded with 3 users, 2 channels, 3 messages

### Test Suites (DSL)
- **[slack_bench.json](examples/slack/testsuites/slack_bench.json)** - 11 test cases covering message sending, channel ops, reactions, threading
- **[Evaluation DSL](docs/evaluation-dsl.md)** - Check DSL docs on how it works.

## Services

- **Slack** (fully implemented - all core APIs)
- **Linear** (Coming by end of october)
- Gmail, GitHub, Jira (TBD). 

If you have requests for specfic services + any feedback mail me at hubert@uni.minerva.edu

## Quick Start

### Install SDK
```bash
uv add install agent-diff
```

### Set up self-hosted backend
```bash
git clone https://github.com/hubertpysklo/agent-diff.git
cd agent-diff
cp env.example .env
cd ops
docker-compose up --build

# Backend runs on http://localhost:8000
# The DEV API key is in logs:
docker-compose logs backend | grep "Dev API Key"
```

### Use the SDK
```python
from agent_diff import AgentDiff

client = AgentDiff(
    api_key="your-dev-key",
    base_url="http://localhost:8000"
)

# See flow above or docs/getting-started.md for full examples
```

See **[docs/getting-started.md](docs/getting-started.md)** for detailed setup and **[SDK README](sdk/agent_diff_pkg/README.md)** for API documentation.


## Contributing

**Want to add a service?**
1. Copy `backend/src/services/slack/` structure
2. Implement your service's APIs
3. Add seed data to `examples/yourservice/seeds/`
4. Write tests in `backend/tests/integration/`

**Want to add a testsuite?**
1. Take a look at [Evaluation DSL](docs/evaluation-dsl.md)
2. Copy examples/slack/testsuites/slack_bench.json and follow the pattern.


