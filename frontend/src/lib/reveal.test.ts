import { afterEach, describe, expect, it, vi } from 'vitest';
import { reveal } from './reveal';

type Callback = (entries: { isIntersecting: boolean }[]) => void;
let observers: { callback: Callback; disconnected: boolean }[] = [];

function allowMotion(reduce: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: reduce && query.includes('prefers-reduced-motion'), media: query
  }));
  observers = [];
  vi.stubGlobal('IntersectionObserver', class {
    entry: { callback: Callback; disconnected: boolean };
    constructor(callback: Callback) {
      this.entry = { callback, disconnected: false };
      observers.push(this.entry);
    }
    observe() {}
    disconnect() { this.entry.disconnected = true; }
  });
}

afterEach(() => vi.unstubAllGlobals());

describe('reveal', () => {
  it('hides a section until it scrolls into view, then shows it for good', () => {
    allowMotion(false);
    const node = document.createElement('section');
    reveal(node);
    expect(node.classList.contains('reveal')).toBe(true);
    expect(node.classList.contains('shown')).toBe(false);
    observers[0].callback([{ isIntersecting: true }]);
    expect(node.classList.contains('shown')).toBe(true);
    expect(observers[0].disconnected).toBe(true);
  });

  it('leaves sections alone under reduced motion', () => {
    allowMotion(true);
    const node = document.createElement('section');
    reveal(node);
    expect(node.className).toBe('');
    expect(observers).toEqual([]);
  });

  it('leaves sections alone without IntersectionObserver', () => {
    vi.stubGlobal('matchMedia', () => ({ matches: false }));
    vi.stubGlobal('IntersectionObserver', undefined);
    const node = document.createElement('section');
    reveal(node);
    expect(node.className).toBe('');
  });
});
