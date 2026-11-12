import { vi } from 'vitest';
import { COMPACT_HEADER } from '$lib/stores/header';

export function compactHeaderOn() {
  vi.spyOn(window, 'matchMedia').mockImplementation((query: string) => ({
    matches: query === COMPACT_HEADER || query.includes('prefers-reduced-motion'),
    media: query, onchange: null,
    addListener: () => {}, removeListener: () => {},
    addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false
  }) as MediaQueryList);
}
