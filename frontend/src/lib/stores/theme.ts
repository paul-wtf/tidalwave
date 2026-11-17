import { writable } from 'svelte/store';
import { browser } from '$app/env';

export type Theme = 'mocha' | 'latte';
const KEY = 'tw-theme';

function initial(): Theme {
  if (!browser) return 'mocha';
  const saved = localStorage.getItem(KEY);
  return saved === 'latte' || saved === 'mocha' ? saved : 'mocha';
}

export const theme = writable<Theme>(initial());

theme.subscribe((value) => {
  if (!browser) return;
  localStorage.setItem(KEY, value);
  document.documentElement.dataset.theme = value;
});

export function toggleTheme(): void {
  theme.update((t) => (t === 'mocha' ? 'latte' : 'mocha'));
}
