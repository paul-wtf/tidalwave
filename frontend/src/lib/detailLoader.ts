import { ApiError } from '$lib/api/client';
import { loadMe } from '$lib/stores/auth';

export type DetailState = 'ok' | 'notFound' | 'error';

export function loadDetail<T>(
  shared: boolean,
  fetchAll: () => Promise<T>,
  apply: (result: T) => void,
  setState: (state: DetailState) => void
): () => void {
  let stale = false;
  (async () => {
    try {
      const result = await fetchAll();
      if (stale) return;
      apply(result);
      setState('ok');
    } catch (e) {
      if (stale) return;
      if (e instanceof ApiError && e.status === 404) setState('notFound');
      else if (!shared && e instanceof ApiError && e.status === 401) await loadMe();
      else setState('error');
    }
  })();
  return () => { stale = true; };
}
