# Agent Diff Python SDK

Python SDK for testing AI agents against isolated replicas of production services.

## Installation

```bash
uv add agent-diff
```

## Quick Start

```python
from agent_diff import AgentDiff
from agent_diff import PythonExecutorProxy, create_openai_tool

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

# 2. Create executor with automatic API interception

python_executor = PythonExecutorProxy(env.environmentId, base_url=client.base_url)
python_tool = create_openai_tool(python_executor)

# 3. Take before snapshot
run = client.start_run(envId=env.environmentId)

# 4. Run your agent (API calls are automatically intercepted)
from agents import Agent

agent = Agent(model="gpt-4o", tools=[python_tool])
response = agent.run("Send a message to #general saying 'Hello!'")

# 5. Compute the diff
diff = client.diff_run(runId=run.runId)

# Inspect changes
diff.diff['inserts']   # New records
diff.diff['updates']   # Modified records
diff.diff['deletes']   # Deleted records

# 6. Cleanup
client.delete_env(envId=env.environmentId)
```

## Code Execution Proxies

Agent Diff provides **code execution proxies** that automatically intercept API calls and route them to isolated test environments. This enables agents with code execution capabilities to interact with service replicas without any code changes.

### How It Works

When your agent executes Python or Bash code:
1. The executor wraps your code with interception logic
2. API calls to `https://api.slack.com` → `http://localhost:8000/api/env/{env_id}/services/slack/api`
3. API calls to `https://api.linear.app` → `http://localhost:8000/api/env/{env_id}/services/linear`
4. Your agent sees real API responses from the isolated environment

### Available Executors

#### PythonExecutorProxy

Intercepts Python `requests` and `urllib` libraries:

```python
from agent_diff import PythonExecutorProxy, create_openai_tool

python_executor = PythonExecutorProxy(env.environmentId, base_url=client.base_url)
python_tool = create_openai_tool(python_executor)

# Works with OpenAI Agents SDK, LangChain, smolagents
agent = Agent(model="gpt-5", tools=[python_tool])
agent.run("Send a Slack message to #general")
```

#### BashExecutorProxy

Intercepts `curl` commands:

```python
from agent_diff import BashExecutorProxy, create_openai_tool

bash_executor = BashExecutorProxy(env.environmentId, base_url=client.base_url)
bash_tool = create_openai_tool(bash_executor)

agent = Agent(model="gpt-5", tools=[bash_tool])
agent.run("Use curl to post a message to Slack")
```

### Framework Support

Create tools for popular agent frameworks:

```python
from agent_diff import create_openai_tool, create_langchain_tool, create_smolagents_tool

# OpenAI Agents SDK
openai_tool = create_openai_tool(python_executor)

# LangChain
langchain_tool = create_langchain_tool(python_executor)

# HuggingFace smolagents
smolagents_tool = create_smolagents_tool(python_executor)
```

### Direct Execution

For custom frameworks or direct usage:

```python
python_executor = PythonExecutorProxy(env.environmentId, base_url=client.base_url)

result = python_executor.execute("""
import requests
response = requests.post('https://api.slack.com/api/chat.postMessage', json={
    'channel': '#general',
    'text': 'Hello from Agent Diff!'
})
print(response.json())
""")

if result["status"] == "success":
    print(result["stdout"])
else:
    print(result["stderr"])
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

    env = client.init_env(testId=test_id)
    run = client.start_run(envId=env.environmentId, testId=test_id)

    # Create executor with automatic API interception
    python_executor = PythonExecutorProxy(env.environmentId, base_url=client.base_url)
    python_tool = create_openai_tool(python_executor)

    # Run your agent with the tool
    agent = Agent(model="gpt-5", tools=[python_tool])
    response = agent.run(prompt)

    evaluation_result = client.evaluate_run(run.runId)  # Returns score, runId, status and Score (0/1)

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
