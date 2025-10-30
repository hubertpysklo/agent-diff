# Agent Diff Python SDK

Python SDK for testing AI agents against isolated replicas of production services.

## Installation

```bash
uv add agent-diff
# or
pip install agent-diff
```

## Quick Start

```python
from agent_diff import AgentDiff

# Self-hosted (defaults to http://localhost:8000)
client = AgentDiff()

# With authentication 
client = AgentDiff(
    api_key="your-api-key",
    base_url="https://your-instance.com"
)

# 1. Create an isolated environment
env = client.init_env(
    templateService="slack",
    templateName="slack_default",
    impersonateUserId="U123456",
    ttlSeconds=1800
)


# 2. Take before snapshot of the environment 
run = client.start_run(envId=env.environmentId)

# 3. Agents does it's thing to replica
# (Use env.environmentUrl to call the service API)

# 4. Compute the diff
diff = client.diff_run(runId=run.runId)

# Inspect changes
diff.diff['inserts']   # New records
diff.diff['updates']   # Modified records
diff.diff['deletes']   # Deleted records

# 5. Cleanup
client.delete_env(envId=env.environmentId)
```

## Environments

Create isolated, ephemeral replicas of services:

```python
env = client.init_env(
    templateService="slack",
    templateName="slack_default",
    impersonateUserId="U123",
    ttlSeconds=3600
)

# Access environment details
env.environmentId
env.environmentUrl
env.expiresAt

# Delete when done
client.delete_env(env.environmentId)
```

## Test Suites

To run evaluations:

```python
suite = client.get_test_suite("slack-bench")
# Returns: {"tests": [{"id": "...", "prompt": "Send hello to #general"}, ...]}


evaluation_results = []

for test in suite['tests']:
    prompt = test['prompt']
    test_id = test['id']

    env = client.init_env(testId = test_id)
    run = client.start_run(envId = env.environmentId, testId = test_id)

    #your LLM/ Agent function - you need to proxy the request on your own for endpoint recived in env.environmentUrl
    ...
    response = await Runner.run(triage_agent, prompt)
    ... 

    evaluation_result = client.evaluate_run(run.runId) #returns score runId, status and Score (0/1)

    evaluation_results.append(evaluation_result) 

    client.delete_env(envId=env.environmentId)
```

## Templates

List and create environment templates:

```python
# List available templates
templates = client.list_templates()

# Create custom template - you can populate the replica and turn it into a template with custom data
custom = client.create_template_from_environment(
    environmentId=env.environmentId,
    service="slack",
    name="my_template",
    description="Custom template",
    visibility="private"  # "private" means only you can view the template
)
```

## License

MIT License - see LICENSE file for details.
