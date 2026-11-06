import { vi } from 'vitest';

export function mockApi(routes: Record<string, unknown>): { calls: string[] } {
  const calls: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      calls.push(url);
      const path = url.split('?')[0];
      if (!(path in routes)) {
        return new Response(JSON.stringify({ detail: 'Not Found' }), {
          status: 404,
          headers: { 'content-type': 'application/json' }
        });
      }
      return new Response(JSON.stringify(routes[path]), {
        status: 200,
        headers: { 'content-type': 'application/json' }
      });
    })
  );
  return { calls };
}
