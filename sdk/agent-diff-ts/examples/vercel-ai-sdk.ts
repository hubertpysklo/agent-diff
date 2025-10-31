/**
 * Vercel AI SDK integration example
 * Requires: npm install ai @ai-sdk/openai zod
 */

import { generateText } from 'ai';
import { openai } from '@ai-sdk/openai';
import {
  AgentDiff,
  TypeScriptExecutorProxy,
  BashExecutorProxy,
  createVercelAITool,
} from '@agent-diff/sdk';

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

  const tsTools = createVercelAITool(tsExecutor);
  const bashTool = createVercelAITool(bashExecutor);

  // Run agent with tools
  console.log('\nRunning agent...');
  const result = await generateText({
    model: openai('gpt-4'),
    tools: {
      execute_typescript: tsTools,
      execute_bash: bashTool,
    },
    prompt: `Post a message "Hello from AI agent!" to the Slack channel with ID C01ABCD1234.
            Use the Slack API at https://slack.com/api/chat.postMessage.
            Then list all channels using https://slack.com/api/conversations.list.`,
    maxSteps: 5,
  });

  console.log('\nAgent response:', result.text);
  console.log('Steps taken:', result.steps?.length);

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
