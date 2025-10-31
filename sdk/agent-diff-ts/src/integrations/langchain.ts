/**
 * LangChain integration
 * Creates tools compatible with LangChain's tool() helper
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
 * Create a LangChain tool from an executor
 * Requires: npm install langchain zod
 */
export function createLangChainTool(executor: BaseExecutorProxy) {
  let tool: unknown;
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    tool = require('langchain').tool;
  } catch {
    throw new Error(
      'LangChain not installed. Install with: npm install langchain'
    );
  }

  const toolFn = tool as (
    execute: (args: { code: string }, config?: unknown) => Promise<string>,
    options: {
      name: string;
      description: string;
      schema: z.ZodType;
    }
  ) => unknown;

  if (executor instanceof TypeScriptExecutorProxy) {
    return toolFn(
      async ({ code }: { code: string }) => {
        const result = await executor.execute(code);
        return formatResult(result);
      },
      {
        name: 'execute_typescript',
        description:
          'Execute TypeScript code and return the output. Standard libraries like fetch are available for HTTP calls.',
        schema: z.object({
          code: z.string().describe('TypeScript code to execute'),
        }),
      }
    );
  }

  if (executor instanceof BashExecutorProxy) {
    return toolFn(
      async ({ code }: { code: string }) => {
        const result = await executor.execute(code);
        return formatResult(result);
      },
      {
        name: 'execute_bash',
        description:
          'Execute Bash commands and return the output. Standard utilities like curl are available.',
        schema: z.object({
          code: z.string().describe('Bash commands to execute'),
        }),
      }
    );
  }

  throw new TypeError(`Unsupported executor type: ${executor.constructor.name}`);
}
