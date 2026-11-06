import { vi } from 'vitest';

export function mockApi(routes: Record<string, unknown>): { calls: string[]; requests: { method: string; url: string }[]; bodies: Record<string, string> } {
  const calls: string[] = [];
  const requests: { method: string; url: string }[] = [];
  const bodies: Record<string, string> = {};
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push(url);
      const method = init?.method ?? 'GET';
      requests.push({ method, url });
      if (typeof init?.body === 'string') bodies[`${method} ${url}`] = init.body;
      const plain = url.split('?')[0];
      const path = `${method} ${plain}` in routes ? `${method} ${plain}` : plain;
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
  return { calls, requests, bodies };
}
