/**
 * Vercel AI SDK integration
 * Creates tools compatible with the AI SDK's tool() helper
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
 * Create a Vercel AI SDK tool from an executor
 * Requires: npm install ai zod
 */
export function createVercelAITool(executor: BaseExecutorProxy) {
  let tool: unknown;
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    tool = require('ai').tool;
  } catch {
    throw new Error(
      'Vercel AI SDK not installed. Install with: npm install ai'
    );
  }

  const toolFn = tool as (config: {
    description: string;
    inputSchema: z.ZodType;
    execute: (args: { code: string }) => Promise<string>;
  }) => unknown;

  if (executor instanceof TypeScriptExecutorProxy) {
    return toolFn({
      description:
        'Execute TypeScript code and return the output. Standard libraries like fetch are available for HTTP calls.',
      inputSchema: z.object({
        code: z.string().describe('TypeScript code to execute'),
      }),
      execute: async ({ code }: { code: string }) => {
        const result = await executor.execute(code);
        return formatResult(result);
      },
    });
  }

  if (executor instanceof BashExecutorProxy) {
    return toolFn({
      description:
        'Execute Bash commands and return the output. Standard utilities like curl are available.',
      inputSchema: z.object({
        code: z.string().describe('Bash commands to execute'),
      }),
      execute: async ({ code }: { code: string }) => {
        const result = await executor.execute(code);
        return formatResult(result);
      },
    });
  }

  throw new TypeError(`Unsupported executor type: ${executor.constructor.name}`);
}
