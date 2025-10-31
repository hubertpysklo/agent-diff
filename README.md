# Agent Diff


## What This Is

**A self-hosted interactive enviroments for testing AI agents & training LLMs against 3rd party services like Linear or Slack.** You run it locally (or deploy it), your agents call fake APIs, you get deterministic diffs. No external service, no rate limits, full control over test data and environments.

Use it for:
- RL training loops (reset state between episodes)
- Integration tests (verify agent does what it should)
- Regression tests (catch when changes break behaviour)
- Training data generation (prompt → actions → diff → outcome)

## Services

- **Slack** – core Web API coverage for conversations, chat, reactions, users, etc. Full list here [`backend/src/services/slack/READEME.md`](backend/src/services/slack/READEME.md). A few examples:

  ```python
  "chat.postMessage"  # post messages in seeded channels/DMs
  "conversations.open"  # spin up IM/MPIM threads
  "reactions.add"  # add emoji reactions to seeded messages
  ```

- **Linear** – GraphQL schema and resolvers for issues/projects (still WIP). See [`backend/src/services/linear/READEME.md`](backend/src/services/linear/READEME.md). Sample operations:

  ```python
  "issues"            # query issues (list/pagination)
  "issueCreate"       # mutation to create an issue
  "projectUpdate"     # mutation to update project metadata
  ```

- Gmail, GitHub, Jira (TBD).

If you have requests for specific services + any feedback, mail me at hubert@uni.minerva.edu


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

# Self-hosted (defaults to http://localhost:8000)
client = AgentDiff()

# With authentication 
client = AgentDiff(
    api_key="your-api-key",
    base_url="https://your-instance.com"
)

# Initialise isolated environment from a template. See: examples/slack/seeds
env = client.init_env(templateService="slack", templateName="slack_default", impersonateUserId="U01AGENBOT9") #impersonateUserId - seeded user (agent) in seed

# e.g. env.environmentUrl = http://localhost:8000/api/env/{environmentId}/services/slack

# Take before snapshot
run = client.start_run(envId=env.environmentId)


# Your agent does stuff using the environment URL 
 
# You can swap the URLs directly in MCPs or use the code executor tool for python or bash with proxy that will route the requests automatically
# e.g. proxt GET 
# from [https://slack.com/api/conversations.list]
# to [http://localhost:8000/api/env/{environmentId}/services/slack]/conversations.list 

# Using CodeExecutorProxy (With OpenAI Agents SDK Tool example, LangChain is also available)
from agent_diff import PythonExecutorProxy, create_openai_tool
from agents import Agent, Runner

# Pass base_url from client or use default
python_executor = PythonExecutorProxy(env.environmentId, base_url=client.base_url)
bash_executor = BashExecutorProxy(env.environmentId, base_url=client.base_url)
python_tool = create_openai_tool(python_executor) 
bash_tool = create_openai_tool(bash_executor)


agent = Agent(
        name="Slack Assistant",
        instructions="You can execute bash with Curl or Python with requests to interact with APIs. ",
        tools=[python_tool, bash_tool]
    )

response = await Runner.run(agent, "Post 'Hello' to Slack channel #general") 
# The agent writes normal code like:
# requests.post('https://api.slack.com/api/chat.postMessage', ...)
# But it will be proxied to the temporary sandbox enviroment  

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
- **[slack_default](examples/slack/seeds/slack_bench_default.json)** - Seeded with sample users and messages for Slack Bench.

### Test Suites (DSL)
- **[slack_bench.json](examples/slack/testsuites/slack_bench.json)** - test cases covering message sending, channel ops, reactions, threading
- **[Evaluation DSL](docs/evaluation-dsl.md)** - Check DSL docs on how it works.


## Evaluations 

To run evaluations:

```python
suite = client.get_test_suite("slack-bench")
# Returns: {"tests": [{"id": "...", "prompt": "Send hello to #general"}, ...]}
# You can edit the file and add your own tests

evaluation_results = []

for test in suite['tests']:
    prompt = test['prompt']
    test_id = test['id']

    #In test suite you define which env seed template is used for each test
    env = client.init_env(testId = test_id)

    # This function will take a snapshot before run
    run = client.start_run(envId = env.environmentId, testId = test_id) 

    from agent_diff import PythonExecutorProxy, create_openai_tool
    from agents import Agent, Runner

    bash_executor = BashExecutorProxy(env.environmentId, base_url=client.base_url)
    bash_tool = create_openai_tool(bash_executor)

    agent = Agent(
        name="Slack Assistant",
        instructions="You can execute Bash code with Curl to interact with APIs. Use the execute_code tool.",
        tools=[bash_tool]
    )

    response = await Runner.run(agent, prompt)

    #This function will take a 2nd snapshot, run diff and assert results against expedted state defined in test suite
    evaluation_result = client.evaluate_run(run.runId) 

    #returns score runId, status and score (0/1)
    evaluation_results.append(evaluation_result) 

    client.delete_env(envId=env.environmentId)
```

## Training & Fine-tuning

Agent Diff is perfect for generating training data for LLMs with tool calling capabilities:

### With Hugging Face (smolagents)

```python
from agent_diff import AgentDiff, PythonExecutorProxy, BashExecutorProxy, create_smolagents_tool
from smolagents import CodeAgent, InferenceClientModel
from 

# Setup and evaluation
client = AgentDiff()

# Load test suite with prompts
test_suite = client.get_test_suite("slack-bench")

training_data = []

for test in test_suite['tests']:
    # Initialize environment for each test
    env = client.init_env(testId=test['id'])
    run = client.start_run(envId=env.environmentId, testId=test['id'])

    # Create HF agent with Python and/ or Bash tools
    python_executor = PythonExecutorProxy(env.environmentId, base_url=client.base_url)
    bash_executor = BashExecutorProxy(env.environmentId, base_url=client.base_url)
    python_tool = create_smolagents_tool(python_executor)
    bash_tool = create_smolagents_tool(bash_executor)

    model = InferenceClientModel("meta-llama/Meta-Llama-3-70B-Instruct")
    agent = CodeAgent(tools=[python_tool, bash_tool], model=model)

    # Execute task with prompt from test suite
    prompt = test['prompt']
    response = agent.run(prompt)
    trace = agent.get_last_run_trace()  # Full execution history

    # Evaluate against expected outcomes
    eval_result = client.evaluate_run(run.runId)

    training_data.append({
            "prompt": prompt,
            "completion": json.dumps(trace),  # Full trace for learning reasoning
            "label": eval_result.score == 1,  # True=passed, False=failed assertions
        })

    client.delete_env(envId=env.environmentId)


# Use with HuggingFace TRL trainers (KTOTrainer, DPOTrainer, etc.)
dataset = Dataset.from_list(training_data)
dataset.save_to_disk("agent_training_data")
```

## Documentation

- **[Getting Started Guide](docs/getting-started.md)** - Detailed setup and configuration
- **[SDK](sdk/agent_diff_pkg/README.md)** - Complete API reference
- **[Evaluation DSL](docs/evaluation-dsl.md)** - Write test assertions
- **[API Reference](docs/api-reference.md)** - REST API documentation

