/**
 * TypeScript executor with in-process fetch interception
 */

import { BaseExecutorProxy } from './base';
import type { ExecutionResult } from '../types';

export class TypeScriptExecutorProxy extends BaseExecutorProxy {
  async execute(code: string): Promise<ExecutionResult> {
    const originalFetch = globalThis.fetch;

    try {
      globalThis.fetch = this.createPatchedFetch(originalFetch);

      const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor as FunctionConstructor;
      const fn = new AsyncFunction('fetch', code);

      const logs: string[] = [];
      const originalLog = console.log;
      console.log = (...args: unknown[]) => logs.push(args.map(a => String(a)).join(' '));

      try {
        await fn(globalThis.fetch);
        return {
          status: 'success',
          stdout: logs.join('\n'),
          stderr: '',
          exitCode: 0,
        };
      } finally {
        console.log = originalLog;
      }
    } catch (error) {
      return {
        status: 'error',
        stdout: '',
        stderr: error instanceof Error ? error.message : String(error),
        exitCode: 1,
        error: error instanceof Error ? error.message : String(error),
      };
    } finally {
      globalThis.fetch = originalFetch;
    }
  }

  private createPatchedFetch(originalFetch: typeof fetch): typeof fetch {
    const mappings = this.urlMappings;
    const token = this.token;

    return async (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
      let url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : (input as Request).url;
      const options: RequestInit = init || {};

      for (const [oldUrl, newUrl] of mappings) {
        if (url.includes(oldUrl)) {
          url = url.replace(oldUrl, newUrl);

          if (token) {
            options.headers = {
              ...(options.headers || {}),
              'Authorization': `Bearer ${token}`,
            };
          }
          break;
        }
      }

      return originalFetch(url, options);
    };
  }
}
