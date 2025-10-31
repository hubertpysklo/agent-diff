/**
 * OpenAI Agents SDK integration example
 * Requires: npm install @openai/agents zod
 */

import { Agent } from '@openai/agents';
import {
  AgentDiff,
  TypeScriptExecutorProxy,
  BashExecutorProxy,
  createOpenAIAgentsTool,
} from 'agent-diff';

async function main() {
  // Initialize Agent Diff client
  const client = new AgentDiff();

  // Create isolated environment
  const env = await client.initEnv({
    templateService: 'slack',
    templateName: 'slack_default',
    impersonateUserId: 'U01AGENBOT9',
  });

  console.log(`Environment: ${env.environmentId}`);

  // Take before snapshot
  const run = await client.startRun({ envId: env.environmentId });

  // Create code executor tools
  const tsExecutor = new TypeScriptExecutorProxy(env.environmentId);
  const bashExecutor = new BashExecutorProxy(env.environmentId);

  const tsTool = createOpenAIAgentsTool(tsExecutor);
  const bashTool = createOpenAIAgentsTool(bashExecutor);

  // Create agent
  const agent = new Agent({
    name: 'Slack Assistant',
    instructions: `You are a helpful assistant that can interact with Slack API.
    Use execute_typescript or execute_bash tools to make API calls to:
    - https://slack.com/api/conversations.list
    - https://slack.com/api/chat.postMessage
    Authentication is handled automatically.`,
    tools: [tsTool, bashTool],
  });

  // Run agent
  console.log('\nRunning agent...');
  const result = await agent.run(
    'List all Slack channels and post "Hello from OpenAI Agents SDK!" to the general channel (C01ABCD1234)'
  );

  console.log('\nAgent response:', result.text);

  // Get diff
  const diff = await client.diffRun({
    runId: run.runId,
  });

  console.log('\nChanges made:');
  console.log('- Diff:', JSON.stringify(diff.diff, null, 2));

  // Cleanup
  await client.deleteEnv(env.environmentId);
}

main().catch(console.error);
