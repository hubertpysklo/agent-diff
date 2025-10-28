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

client = AgentDiff(
    api_key="your-api-key",
    base_url="https://api.yourdomain.com"
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
client.delete_env(env.environmentId)
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

## Templates

List and create environment templates:

```python
# List available templates
templates = client.list_templates()

# Create custom template - you can populate the replica and turn it into a template with custom data data
custom = client.create_template_from_environment(
    environmentId=env.environmentId,
    service="slack",
    name="my_template",
    description="Custom template",
    ownerScope="user" # user means only you can view the template 
)
```

## License

MIT License - see LICENSE file for details.
