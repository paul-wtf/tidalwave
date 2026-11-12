import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { prefersReducedMotion, tween } from './motion';

const motion = (reduce: boolean) =>
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: reduce && query.includes('prefers-reduced-motion'), media: query
  }));

describe('tween', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['requestAnimationFrame', 'cancelAnimationFrame', 'performance'] });
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('reports the user preference', () => {
    motion(true);
    expect(prefersReducedMotion()).toBe(true);
    motion(false);
    expect(prefersReducedMotion()).toBe(false);
  });

  it('jumps to the target without a frame under reduced motion', () => {
    motion(true);
    const seen: number[] = [];
    tween(0, 100, (v) => seen.push(v), 500);
    expect(seen).toEqual([100]);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('eases from start to target and ends exactly on it', () => {
    motion(false);
    const seen: number[] = [];
    tween(0, 100, (v) => seen.push(v), 500);
    expect(seen).toEqual([]);
    vi.advanceTimersByTime(250);
    const midway = seen[seen.length - 1];
    expect(midway).toBeGreaterThan(50);
    expect(midway).toBeLessThan(100);
    expect([...seen].sort((a, b) => a - b)).toEqual(seen);
    vi.advanceTimersByTime(300);
    expect(seen[seen.length - 1]).toBe(100);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('stops when cancelled', () => {
    motion(false);
    const seen: number[] = [];
    const cancel = tween(0, 100, (v) => seen.push(v), 500);
    vi.advanceTimersByTime(100);
    const frames = seen.length;
    cancel();
    vi.advanceTimersByTime(1000);
    expect(seen).toHaveLength(frames);
  });

  it('does nothing when start and target are equal', () => {
    motion(false);
    const seen: number[] = [];
    tween(7, 7, (v) => seen.push(v), 500);
    expect(seen).toEqual([7]);
    expect(vi.getTimerCount()).toBe(0);
  });
});
