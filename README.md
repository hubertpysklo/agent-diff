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
# Get your API key from logs:
docker-compose logs backend | grep "Dev API Key"
```

### 3. Flow
```python
from agent_diff import AgentDiff

client = AgentDiff(api_key="your-dev-key", base_url="http://localhost:8000")

# Initialise isolated environment from template
env = client.init_env(templateService="slack", templateName="slack_default", impersonateUserId="U01AGENBOT9")

# Take before snapshot
run = client.start_run(envId=env.environmentId)

# Your agent does stuff using the environment URL.
# You can either use a sidecar proxy (package coming soon) or swap the URLs directly in MCPs
# e.g. GET to [https://slack.com/api/]conversations.list -->
# --> [http://localhost:8000/api/env/c49bc3c27a4d468ea12a572c6b0b5bd0/services/slack/]conversations.list 

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
- **[slack_default](examples/slack/seeds/slack_default.json)** - Seeded with 3 users, 2 channels, 3 messages

### Test Suites (DSL)
- **[slack_bench.json](examples/slack/testsuites/slack_bench.json)** - 11 test cases covering message sending, channel ops, reactions, threading
- **[Evaluation DSL](docs/evaluation-dsl.md)** - Check DSL docs on how it works.

## Services

- **Slack** (Core API methods)
- **Linear** (Not well tested)
- Gmail, GitHub, Jira (TBD). 

If you have requests for specific services + any feedback, email me at hubert@uni.minerva.edu

## Documentation

- **[Getting Started Guide](docs/getting-started.md)** - Detailed setup and configuration
- **[SDK README](sdk/agent_diff_pkg/README.md)** - Complete API reference
- **[Evaluation DSL](docs/evaluation-dsl.md)** - Write test assertions
- **[API Reference](docs/api-reference.md)** - REST API documentation


## Contributing

**Want to add a service?**
1. Copy `backend/src/services/slack/` structure
2. Implement your service's APIs
3. Add seed data to `examples/yourservice/seeds/`
4. Write tests in `backend/tests/integration/`

**Want to add a testsuite?**
1. Take a look at [Evaluation DSL](docs/evaluation-dsl.md)
2. Copy examples/slack/testsuites/slack_bench.json and follow the pattern.


