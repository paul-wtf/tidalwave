import { readable, writable } from 'svelte/store';

// Must match the max-width of the two-row header in Header.svelte and tokens.css.
export const COMPACT_HEADER = '(max-width: 999px)';

export const compactHeader = readable(false, (set) => {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
  const query = window.matchMedia(COMPACT_HEADER);
  set(query.matches);
  const update = (e: MediaQueryListEvent) => set(e.matches);
  query.addEventListener?.('change', update);
  return () => query.removeEventListener?.('change', update);
});

export const shareOpen = writable(false);
