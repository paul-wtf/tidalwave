import { vi } from 'vitest';

export function stubDeferredFetch(
  respond: (url: URL) => unknown | undefined,
  isSlow: (url: URL) => boolean
): { release: () => void } {
  const gates: (() => void)[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input), 'http://localhost');
      if (isSlow(url)) await new Promise<void>((r) => gates.push(r));
      const body = respond(url);
      return new Response(JSON.stringify(body ?? { detail: 'Not Found' }), {
        status: body === undefined ? 404 : 200,
        headers: { 'content-type': 'application/json' }
      });
    })
  );
  return { release: () => gates.splice(0).forEach((g) => g()) };
}
