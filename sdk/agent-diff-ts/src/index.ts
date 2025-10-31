/**
 * Agent Diff TypeScript SDK
 * Test AI agents against replicas of services like Slack and Linear
 */

// Main client
export { AgentDiff } from './client';
export type { AgentDiffOptions } from './client';

// Types
export type {
  Service,
  Visibility,
  TestType,
  InitEnvRequest,
  InitEnvResponse,
  DeleteEnvResponse,
  TemplateEnvironmentSummary,
  TemplateEnvironmentListResponse,
  TemplateEnvironmentDetail,
  CreateTemplateFromEnvRequest,
  CreateTemplateFromEnvResponse,
  TestSuiteSummary,
  TestSuiteListResponse,
  Test,
  TestSuiteDetail,
  CreateTestSuiteRequest,
  CreateTestSuiteResponse,
  TestItem,
  CreateTestsRequest,
  CreateTestsResponse,
  StartRunRequest,
  StartRunResponse,
  EndRunRequest,
  EndRunResponse,
  DiffRunRequest,
  DiffRunResponse,
  DiffResult,
  EvaluationResult,
  TestResultResponse,
  ExecutionResult,
} from './types';

// Executors
export {
  BaseExecutorProxy,
  TypeScriptExecutorProxy,
  BashExecutorProxy,
} from './executors';

// Framework integrations
export {
  createVercelAITool,
  createLangChainTool,
  createOpenAIAgentsTool,
} from './integrations';
