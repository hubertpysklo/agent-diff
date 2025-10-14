# Diff Universe

> **AI agents are bad at using APIs and MCPs**

 When I interned at a YC comapny last summer, I was running tests on our new agent implementation and it sent an email to a company investor, signed as CEO. **We could not run evals on 3rd party services for production**


## What This Is

**A self-hosted platform for testing AI agents & training LLMs against 3rd party services like Linear or Slack.** You run it locally (or deploy it), your agents call fake APIs, you get deterministic diffs. No external service, no API keys to manage, full control over test data.

Use it for:
- RL training loops (reset state between episodes)
- Integration tests (verify agent does what it should)
- Regression tests (catch when changes break behavior)
- Training data generation (prompt → actions → diff → outcome)


## Flow

```
1. Create isolated environment  → POST /api/platform/initEnv
2. Snapshot initial state       → POST /api/platform/startRun
3. Agent does stuff             → POST /api/env/{envId}/services/slack/chat.postMessage
4. Snapshot final state + diff  → POST /api/platform/endRun
5. Get results                  → GET /api/platform/results/{runId}
```

Every environment gets its own PostgreSQL schema. URLs bind requests to schemas. Snapshots diff exactly what changed in this specfic isolated enviroment.

## Services

- **Slack** (fully implemented - all core APIs)
- **Linear** (Coming by end of october)
- Gmail, GitHub, Jira (TBD). 

If you have requests for specfic services + any feedback mail me at hubert@uni.minerva.edu

## Quick Start

```bash
git clone https://github.com/yourusername/diff-the-universe.git
cd diff-the-universe
cp env.example .env
cd ops
docker-compose up --build

# Backend runs on http://localhost:8000
# The DEV API key is in logs:
docker-compose logs backend | grep "Dev API Key"
```

See **[docs/getting-started.md](docs/getting-started.md)** for setup.


### Slack-Bench (in DSL)
Sample test scenarios for Slack agents:
- **[slack_bench.json](examples/slack/testsuites/slack_bench.json)** - 11 test cases covering message sending, channel ops, reactions, threading
- **[slack_default.json](examples/slack/seeds/slack_default.json)** - Seed data (3 users, 2 channels, 3 messages)

- **[Evaluation DSL](docs/evaluation-dsl.md)** - Check DSL docs on how it works.


## Contributing

**Want to add a service?**
1. Copy `backend/src/services/slack/` structure
2. Implement your service's APIs
3. Add seed data to `examples/yourservice/seeds/`
4. Write tests in `backend/tests/integration/`

**Want to add a testsuite?**
1. Take a look at [Evaluation DSL](docs/evaluation-dsl.md)
2. Copy examples/slack/testsuites/slack_bench.json and follow the pattern.


