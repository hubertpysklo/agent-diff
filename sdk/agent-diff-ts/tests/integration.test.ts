/**
 * Integration tests for Agent Diff SDK
 * Requires backend running at http://localhost:8000
 */

import { AgentDiff, TypeScriptExecutorProxy, BashExecutorProxy } from '../src';

const TEST_TIMEOUT = 30000;

describe('Agent Diff Integration Tests', () => {
  let client: AgentDiff;

  beforeAll(() => {
    client = new AgentDiff();
  });

  describe('Environment Management', () => {
    let envId: string;

    it('should initialize environment', async () => {
      const env = await client.initEnv({
        templateService: 'slack',
        templateName: 'slack_default',
        impersonateUserId: 'U01AGENBOT9',
      });

      expect(env.environmentId).toBeDefined();
      expect(env.environmentUrl).toBeDefined();
      expect(env.expiresAt).toBeInstanceOf(Date);

      envId = env.environmentId;
    }, TEST_TIMEOUT);

    it('should delete environment', async () => {
      const result = await client.deleteEnv(envId);

      expect(result.environmentId).toBe(envId);
      expect(result.status).toBe('deleted');
    }, TEST_TIMEOUT);
  });

  describe('Template Management', () => {
    it('should list templates', async () => {
      const templates = await client.listTemplates();

      expect(Array.isArray(templates.templates)).toBe(true);
      expect(templates.templates.length).toBeGreaterThan(0);
      expect(templates.templates[0].id).toBeDefined();
    }, TEST_TIMEOUT);

    it('should get template by ID', async () => {
      const templates = await client.listTemplates();
      const templateId = templates.templates[0].id;

      const template = await client.getTemplate(templateId);

      expect(template.id).toBe(templateId);
      expect(template.service).toBeDefined();
      expect(template.name).toBeDefined();
    }, TEST_TIMEOUT);
  });

  describe('Test Suite Management', () => {
    let suiteId: string;
    let testId: string;

    it('should create test suite', async () => {
      const suite = await client.createTestSuite({
        name: 'SDK Integration Test Suite',
        description: 'Created by TypeScript SDK integration tests',
      });

      expect(suite.id).toBeDefined();
      suiteId = suite.id;
    }, TEST_TIMEOUT);

    it('should list test suites', async () => {
      const suites = await client.listTestSuites();

      expect(Array.isArray(suites.testSuites)).toBe(true);
      expect(suites.testSuites.length).toBeGreaterThan(0);
    }, TEST_TIMEOUT);

    it('should create test in suite', async () => {
      const templates = await client.listTemplates();
      const templateId = templates.templates[0].id;

      const result = await client.createTests(suiteId, {
        tests: [
          {
            name: 'Test message creation',
            prompt: 'Post a test message',
            type: 'actionEval',
            expected_output: {
              assertions: [
                {
                  diff_type: 'added',
                  entity: 'messages',
                  where: {
                    message_text: {
                      contains: 'test',
                    },
                  },
                  expected_count: 1,
                },
              ],
            },
            environmentTemplate: templateId,
            impersonateUserId: 'U01AGENBOT9',
          },
        ],
      });

      expect(result.tests).toHaveLength(1);
      expect(result.tests[0].id).toBeDefined();
      expect(result.tests[0].createdAt).toBeInstanceOf(Date);
      testId = result.tests[0].id;
    }, TEST_TIMEOUT);

    it('should get test suite without expand', async () => {
      const suite = await client.getTestSuite(suiteId);

      expect('tests' in suite).toBe(true);
      if ('tests' in suite) {
        expect(Array.isArray(suite.tests)).toBe(true);
        expect(suite.tests.length).toBeGreaterThan(0);
        expect(suite.tests[0].id).toBeDefined();
      }
    }, TEST_TIMEOUT);

    it('should get test suite with expand', async () => {
      const suite = await client.getTestSuite(suiteId, { expand: true });

      expect('id' in suite).toBe(true);
      if ('id' in suite) {
        expect(suite.id).toBe(suiteId);
        expect(suite.createdAt).toBeInstanceOf(Date);
        expect(Array.isArray(suite.tests)).toBe(true);
      }
    }, TEST_TIMEOUT);

    it('should get test by ID', async () => {
      const test = await client.getTest(testId);

      expect(test.id).toBe(testId);
      expect(test.createdAt).toBeInstanceOf(Date);
      expect(test.updatedAt).toBeInstanceOf(Date);
    }, TEST_TIMEOUT);
  });

  describe('Run Management', () => {
    let envId: string;
    let runId: string;

    beforeAll(async () => {
      const env = await client.initEnv({
        templateService: 'slack',
        templateName: 'slack_default',
        impersonateUserId: 'U01AGENBOT9',
      });
      envId = env.environmentId;
    }, TEST_TIMEOUT);

    afterAll(async () => {
      if (envId) {
        await client.deleteEnv(envId);
      }
    }, TEST_TIMEOUT);

    it('should start run', async () => {
      const run = await client.startRun({ envId });

      expect(run.runId).toBeDefined();
      expect(run.status).toBe('running');
      expect(run.beforeSnapshot).toBeDefined();
      runId = run.runId;
    }, TEST_TIMEOUT);

    it('should get diff for run', async () => {
      const diff = await client.diffRun({ runId });

      expect(diff.beforeSnapshot).toBeDefined();
      expect(diff.afterSnapshot).toBeDefined();
      expect(diff.diff).toBeDefined();
    }, TEST_TIMEOUT);
  });

  describe('Code Executors', () => {
    let envId: string;
    let token: string;

    beforeAll(async () => {
      const env = await client.initEnv({
        templateService: 'slack',
        templateName: 'slack_default',
        impersonateUserId: 'U01AGENBOT9',
      });
      envId = env.environmentId;
      token = env.token;
    }, TEST_TIMEOUT);

    afterAll(async () => {
      if (envId) {
        await client.deleteEnv(envId);
      }
    }, TEST_TIMEOUT);

    it('should execute TypeScript code', async () => {
      const executor = new TypeScriptExecutorProxy(
        envId,
        client.getBaseUrl(),
        token
      );

      const result = await executor.execute(`
        const response = await fetch('https://slack.com/api/conversations.list', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        console.log(JSON.stringify(data, null, 2));
      `);

      expect(result.status).toBe('success');
      expect(result.stdout).toBeDefined();
      expect(result.stdout).toContain('channels');
    }, TEST_TIMEOUT);

    it('should execute Bash code', async () => {
      const executor = new BashExecutorProxy(
        envId,
        client.getBaseUrl(),
        token
      );

      const result = await executor.execute(`
        curl -X POST https://slack.com/api/conversations.list \\
          -H "Content-Type: application/json"
      `);

      expect(result.status).toBe('success');
      expect(result.stdout).toBeDefined();
      expect(result.stdout).toContain('channels');
    }, TEST_TIMEOUT);

    it('should handle TypeScript executor errors', async () => {
      const executor = new TypeScriptExecutorProxy(
        envId,
        client.getBaseUrl(),
        token
      );

      const result = await executor.execute(`
        throw new Error('Test error');
      `);

      expect(result.status).toBe('error');
      expect(result.error).toContain('Test error');
    }, TEST_TIMEOUT);

    it('should handle Bash executor errors', async () => {
      const executor = new BashExecutorProxy(
        envId,
        client.getBaseUrl(),
        token
      );

      const result = await executor.execute(`
        exit 42
      `);

      expect(result.status).toBe('error');
      expect(result.exitCode).toBe(42);
    }, TEST_TIMEOUT);
  });

  describe('Full Workflow', () => {
    it('should execute complete test workflow', async () => {
      // 1. Create environment
      const env = await client.initEnv({
        templateService: 'slack',
        templateName: 'slack_default',
        impersonateUserId: 'U01AGENBOT9',
      });
      expect(env.environmentId).toBeDefined();

      // 2. Start run (before snapshot)
      const run = await client.startRun({ envId: env.environmentId });
      expect(run.runId).toBeDefined();

      // 3. Execute code that makes changes
      const executor = new TypeScriptExecutorProxy(
        env.environmentId,
        client.getBaseUrl(),
        env.token
      );

      const result = await executor.execute(`
        const response = await fetch('https://slack.com/api/chat.postMessage', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            channel: 'C01GENERAL99',
            text: 'Integration test message'
          })
        });
        const data = await response.json();
        console.log('Message sent:', data.ok);
      `);
      expect(result.status).toBe('success');

      // 4. Get diff
      const diff = await client.diffRun({ runId: run.runId });
      expect(diff.beforeSnapshot).toBeDefined();
      expect(diff.afterSnapshot).toBeDefined();
      expect(diff.diff).toBeDefined();

      // 5. Cleanup
      await client.deleteEnv(env.environmentId);
    }, TEST_TIMEOUT);
  });
});
