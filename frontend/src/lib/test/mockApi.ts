import { vi } from 'vitest';

export function mockApi(routes: Record<string, unknown>): { calls: string[]; requests: { method: string; url: string }[] } {
  const calls: string[] = [];
  const requests: { method: string; url: string }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push(url);
      requests.push({ method: init?.method ?? 'GET', url });
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
  return { calls, requests };
}
