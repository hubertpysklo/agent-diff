/**
 * Type definitions for Agent Diff SDK
 * Mirrors Python SDK models from backend/src/platform/api/models.py
 */

export type Service = 'slack' | 'linear';
export type Visibility = 'public' | 'private';
export type TestType = 'actionEval' | 'retriEval' | 'compositeEval';

// Environment Management

export interface InitEnvRequest {
  templateService?: Service;
  templateName?: string;
  templateId?: string;
  testId?: string;
  ttlSeconds?: number;
  impersonateUserId?: string;
  impersonateEmail?: string;
}

export interface InitEnvResponse {
  environmentId: string;
  templateSchema: string;
  environmentUrl: string;
  expiresAt: Date;
  schemaName: string;
  service: Service;
  token?: string;
}

export interface DeleteEnvResponse {
  environmentId: string;
  status: string;
}

// Template Management

export interface TemplateEnvironmentSummary {
  id: string;
  service: Service;
  description?: string;
  name: string;
}

export interface TemplateEnvironmentListResponse {
  templates: TemplateEnvironmentSummary[];
}

export interface TemplateEnvironmentDetail {
  id: string;
  service: Service;
  description?: string;
  name: string;
  version: string;
  schemaName: string;
}

export interface CreateTemplateFromEnvRequest {
  environmentId: string;
  service: Service;
  name: string;
  description?: string;
  visibility?: Visibility;
  version?: string;
}

export interface CreateTemplateFromEnvResponse {
  id: string;
  name: string;
  description: string;
  service: Service;
}

// Test Suite Management

export interface TestSuiteSummary {
  id: string;
  name: string;
  description: string;
}

export interface TestSuiteListResponse {
  testSuites: TestSuiteSummary[];
}

export interface Test {
  id: string;
  name: string;
  prompt: string;
  type: TestType;
  expected_output: Record<string, unknown>;
  createdAt: Date;
  updatedAt: Date;
}

export interface TestSuiteDetail {
  id: string;
  name: string;
  description: string;
  owner: string;
  visibility: Visibility;
  createdAt: Date;
  updatedAt: Date;
  tests: Test[];
}

export interface CreateTestSuiteRequest {
  name: string;
  description: string;
  visibility?: Visibility;
  tests?: TestItem[];
}

export interface CreateTestSuiteResponse {
  id: string;
  name: string;
  description: string;
  visibility: Visibility;
}

export interface TestItem {
  name: string;
  prompt: string;
  type: TestType;
  expected_output: Record<string, unknown> | string;
  environmentTemplate: string;
  impersonateUserId?: string;
}

export interface CreateTestsRequest {
  tests: TestItem[];
  defaultEnvironmentTemplate?: string;
}

export interface CreateTestsResponse {
  tests: Test[];
}

// Run Management

export interface StartRunRequest {
  envId?: string;
  testId?: string;
}

export interface StartRunResponse {
  runId: string;
  status: string;
  beforeSnapshot: string;
}

export interface EndRunRequest {
  runId: string;
}

export interface EndRunResponse {
  runId: string;
  status: string;
  passed: boolean;
  score: unknown;
}

export interface DiffRunRequest {
  runId?: string;
  envId?: string;
  beforeSuffix?: string;
}

export interface DiffRunResponse {
  beforeSnapshot: string;
  afterSnapshot: string;
  diff: unknown;
}

// Diff and Evaluation

export interface DiffResult {
  inserts: Array<Record<string, unknown>>;
  updates: Array<Record<string, unknown>>;
  deletes: Array<Record<string, unknown>>;
}

export interface EvaluationResult {
  passed: boolean;
  details: Record<string, unknown>;
}

export interface TestResultResponse {
  runId: string;
  status: string;
  passed: boolean;
  score: unknown;
  failures: string[];
  diff: unknown;
  createdAt: Date;
}

// Code Execution

export interface ExecutionResult {
  status: 'success' | 'error';
  stdout: string;
  stderr: string;
  exitCode?: number;
  error?: string;
}
