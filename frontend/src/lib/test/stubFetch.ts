import { vi } from 'vitest';

export type Handler = (method: string, url: string, body?: string) => Response | undefined;

export function stubFetch(handler: Handler): string[] {
  const seen: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const method = init?.method ?? 'GET';
    const url = String(input);
    seen.push(`${method} ${url}`);
    return handler(method, url, typeof init?.body === 'string' ? init.body : undefined)
      ?? new Response(null, { status: 204 });
  }));
  return seen;
}
