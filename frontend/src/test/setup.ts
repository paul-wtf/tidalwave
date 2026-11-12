import '@testing-library/jest-dom/vitest';

// jsdom only wires up localStorage on some Node versions (it's absent under
// Node 26 with jsdom 24). Stores read it at module load, so polyfill a minimal
// in-memory Storage when missing — harmless where jsdom already provides one.
if (typeof globalThis.localStorage === 'undefined') {
  const store = new Map<string, string>();
  globalThis.localStorage = {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
    key: (i: number) => [...store.keys()][i] ?? null,
    get length() { return store.size; }
  } as Storage;
}

// LayerChart (via @layerstack/svelte-stores) calls window.matchMedia at module
// load time.  jsdom doesn't implement it, so we stub it so imports don't crash.
if (typeof window !== 'undefined' && !window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    // Tests prefer reduced motion, so no component waits on animation frames
    // unless a test stubs matchMedia to allow motion.
    value: (query: string) => ({
      matches: query.includes('prefers-reduced-motion'),
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false
    })
  });
}

// LayerCake (used by LayerChart) uses ResizeObserver to measure chart containers.
// jsdom doesn't implement it, so we stub it.
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}
