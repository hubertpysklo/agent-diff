/**
 * Basic usage example - environment lifecycle and code execution
 */

import {
  AgentDiff,
  TypeScriptExecutorProxy,
  BashExecutorProxy,
} from '@agent-diff/sdk';

async function main() {
  // Initialize client (defaults to http://localhost:8000)
  const client = new AgentDiff();

  // 1. Initialize isolated environment from template
  console.log('Initializing environment...');
  const env = await client.initEnv({
    templateService: 'slack',
    templateName: 'slack_default',
    impersonateUserId: 'U01AGENBOT9', // Seeded user ID from template
  });

  console.log(`Environment created: ${env.environmentId}`);
  console.log(`Service URL: ${env.environmentUrl}`);
  console.log(`Expires at: ${env.expiresAt}`);

  // 2. Take before snapshot
  console.log('\nTaking before snapshot...');
  const run = await client.startRun({ envId: env.environmentId });
  console.log(`Run started: ${run.runId}`);

  // 3. Execute TypeScript code with network interception
  console.log('\nExecuting TypeScript code...');
  const tsExecutor = new TypeScriptExecutorProxy(
    env.environmentId,
    client['baseUrl']
  );

  const tsResult = await tsExecutor.execute(`
    const response = await fetch('https://slack.com/api/conversations.list', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await response.json();
    console.log('Channels:', data.channels?.map(c => c.name).join(', '));
  `);

  console.log('TypeScript result:', tsResult.stdout);

  // 4. Execute Bash code with curl interception
  console.log('\nExecuting Bash code...');
  const bashExecutor = new BashExecutorProxy(
    env.environmentId,
    client['baseUrl']
  );

  const bashResult = await bashExecutor.execute(`
    curl -X POST https://slack.com/api/chat.postMessage \\
      -H "Content-Type: application/json" \\
      -d '{"channel": "C01ABCD1234", "text": "Hello from Agent Diff!"}'
  `);

  console.log('Bash result:', bashResult.stdout);

  // 5. Get diff of changes
  console.log('\nComputing diff...');
  const diff = await client.diffRun({
    runId: run.runId,
  });

  console.log('Before snapshot:', diff.beforeSnapshot);
  console.log('After snapshot:', diff.afterSnapshot);
  console.log('Diff:', JSON.stringify(diff.diff, null, 2));

  // 6. Cleanup
  console.log('\nCleaning up...');
  await client.deleteEnv(env.environmentId);
  console.log('Environment deleted');
}

main().catch(console.error);
