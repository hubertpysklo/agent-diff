/**
 * OpenAI Agents SDK integration
 * Creates tools compatible with OpenAI Agents SDK's tool() helper
 */

import { z } from 'zod';
import type { BaseExecutorProxy } from '../executors/base';
import { TypeScriptExecutorProxy } from '../executors/typescript';
import { BashExecutorProxy } from '../executors/bash';

/**
 * Format execution result for display
 */
function formatResult(result: { status: string; stdout: string; stderr: string; error?: string }): string {
  if (result.status === 'success') {
    return result.stdout || 'Code executed successfully (no output)';
  }
  return `Error: ${result.error || result.stderr}`;
}

/**
 * Create an OpenAI Agents SDK tool from an executor
 * Requires: npm install @openai/agents zod
 */
export function createOpenAIAgentsTool(executor: BaseExecutorProxy) {
  let tool: unknown;
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    tool = require('@openai/agents').tool;
  } catch {
    throw new Error(
      'OpenAI Agents SDK not installed. Install with: npm install @openai/agents'
    );
  }

  const toolFn = tool as (config: {
    name: string;
    description: string;
    parameters: z.ZodType;
    execute: (args: { code: string }, context?: unknown) => Promise<string>;
    strict?: boolean;
  }) => unknown;

  if (executor instanceof TypeScriptExecutorProxy) {
    return toolFn({
      name: 'execute_typescript',
      description:
        'Execute TypeScript code and return the output. Standard libraries like fetch are available for HTTP calls.',
      parameters: z.object({
        code: z.string().describe('TypeScript code to execute'),
      }),
      async execute({ code }: { code: string }) {
        const result = await executor.execute(code);
        return formatResult(result);
      },
      strict: true,
    });
  }

  if (executor instanceof BashExecutorProxy) {
    return toolFn({
      name: 'execute_bash',
      description:
        'Execute Bash commands and return the output. Standard utilities like curl are available.',
      parameters: z.object({
        code: z.string().describe('Bash commands to execute'),
      }),
      async execute({ code }: { code: string }) {
        const result = await executor.execute(code);
        return formatResult(result);
      },
      strict: true,
    });
  }

  throw new TypeError(`Unsupported executor type: ${executor.constructor.name}`);
}
