/**
 * LangChain integration example
 * Requires: npm install langchain @langchain/openai zod
 */

import { ChatOpenAI } from '@langchain/openai';
import { createAgent } from 'langchain';
import {
  AgentDiff,
  TypeScriptExecutorProxy,
  BashExecutorProxy,
  createLangChainTool,
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

  const tsTool = createLangChainTool(tsExecutor);
  const bashTool = createLangChainTool(bashExecutor);

  // Create agent
  const agent = createAgent({
    model: new ChatOpenAI({ model: 'gpt-4' }),
    tools: [tsTool, bashTool],
  });

  // Run agent
  console.log('\nRunning agent...');
  const result = await agent.invoke({
    messages: [
      {
        role: 'user',
        content: `Use the Slack API to:
        1. List all channels (https://slack.com/api/conversations.list)
        2. Post "Hello from LangChain agent!" to channel C01ABCD1234 (https://slack.com/api/chat.postMessage)

        Use execute_typescript or execute_bash tools.`,
      },
    ],
  });

  console.log('\nAgent response:', result.messages[result.messages.length - 1]?.content);

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
