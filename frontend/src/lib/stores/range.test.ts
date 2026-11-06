import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';
import { toParams, bucketFor, rangeLabel, range, rangeQuery } from './range';
import { auth } from './auth';

const BERLIN = 'Europe/Berlin';

describe('toParams', () => {
  it('this_month resolves the local month start', () => {
    expect(toParams({ kind: 'calendar', key: 'this_month' }, BERLIN, new Date('2026-11-06T12:00:00Z')))
      .toEqual({ start: '2026-11-01', calendar: 'month' });
  });

  it('last_week starts on Monday and ends the following Monday', () => {
    expect(toParams({ kind: 'calendar', key: 'last_week' }, BERLIN, new Date('2026-11-06T12:00:00Z')))
      .toEqual({ start: '2026-10-26', end: '2026-11-02', calendar: 'week' });
  });

  it('this_week on a Sunday still starts on the preceding Monday', () => {
    expect(toParams({ kind: 'calendar', key: 'this_week' }, 'UTC', new Date('2026-11-08T12:00:00Z')))
      .toEqual({ start: '2026-11-02', calendar: 'week' });
  });

  it('this_year uses the local date, not the UTC date', () => {
    expect(toParams({ kind: 'calendar', key: 'this_year' }, BERLIN, new Date('2026-12-31T23:30:00Z')))
      .toEqual({ start: '2027-01-01', calendar: 'year' });
  });

  it('this_year west of UTC uses the local date', () => {
    expect(toParams({ kind: 'calendar', key: 'this_year' }, 'America/Los_Angeles', new Date('2027-01-01T03:00:00Z')))
      .toEqual({ start: '2026-01-01', calendar: 'year' });
  });

  it('last_month across a year boundary', () => {
    expect(toParams({ kind: 'calendar', key: 'last_month' }, 'UTC', new Date('2026-01-15T12:00:00Z')))
      .toEqual({ start: '2025-12-01', end: '2026-01-01', calendar: 'month' });
  });

  it('last_year', () => {
    expect(toParams({ kind: 'calendar', key: 'last_year' }, 'UTC', new Date('2026-06-15T12:00:00Z')))
      .toEqual({ start: '2025-01-01', end: '2026-01-01', calendar: 'year' });
  });

  it('custom makes the end exclusive', () => {
    expect(toParams({ kind: 'custom', from: '2026-10-01', to: '2026-10-31' }, BERLIN, new Date()))
      .toEqual({ start: '2026-10-01', end: '2026-11-01' });
  });

  it('rolling sends only since; all sends nothing', () => {
    const now = new Date('2026-11-06T12:00:00Z');
    expect(toParams({ kind: 'rolling', key: '7d' }, 'UTC', now))
      .toEqual({ since: '2026-10-30T12:00:00.000Z' });
    expect(toParams({ kind: 'rolling', key: 'all' }, 'UTC', now)).toEqual({});
  });
});

describe('bucketFor', () => {
  const now = new Date('2026-11-06T12:00:00Z');
  it('uses days up to 92 days and months beyond', () => {
    expect(bucketFor({ kind: 'rolling', key: '30d' }, 'UTC', now)).toBe('day');
    expect(bucketFor({ kind: 'rolling', key: '365d' }, 'UTC', now)).toBe('month');
    expect(bucketFor({ kind: 'rolling', key: 'all' }, 'UTC', now)).toBe('month');
    expect(bucketFor({ kind: 'calendar', key: 'this_month' }, 'UTC', now)).toBe('day');
    expect(bucketFor({ kind: 'calendar', key: 'last_year' }, 'UTC', now)).toBe('month');
    expect(bucketFor({ kind: 'custom', from: '2026-01-01', to: '2026-04-02' }, 'UTC', now)).toBe('day');
    expect(bucketFor({ kind: 'custom', from: '2026-01-01', to: '2026-04-03' }, 'UTC', now)).toBe('month');
  });
});

describe('rangeLabel', () => {
  it('names each kind', () => {
    expect(rangeLabel({ kind: 'rolling', key: '24h' })).toBe('Last 24 hours');
    expect(rangeLabel({ kind: 'calendar', key: 'last_week' })).toBe('Last week');
  });
});

describe('range persistence', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it.each([
    ['day', '24h'], ['week', '7d'], ['month', '30d'], ['year', '365d'], ['all', 'all']
  ])('maps legacy %s to %s', async (legacy, key) => {
    localStorage.setItem('tw-range', legacy);
    const { range } = await import('./range');
    let value: unknown;
    range.subscribe((v) => (value = v))();
    expect(value).toEqual({ kind: 'rolling', key });
  });

  it('falls back to the default for a corrupt custom range', async () => {
    localStorage.setItem('tw-range-v2', JSON.stringify({ kind: 'custom', from: 'x', to: '2026-01-01' }));
    const { range } = await import('./range');
    let value: unknown;
    range.subscribe((v) => (value = v))();
    expect(value).toEqual({ kind: 'rolling', key: '30d' });
  });

  it('prefers the v2 key', async () => {
    localStorage.setItem('tw-range', 'month');
    localStorage.setItem('tw-range-v2', JSON.stringify({ kind: 'calendar', key: 'this_year' }));
    const { range } = await import('./range');
    let value: unknown;
    range.subscribe((v) => (value = v))();
    expect(value).toEqual({ kind: 'calendar', key: 'this_year' });
  });

  it('defaults to 30d', async () => {
    const { range } = await import('./range');
    let value: unknown;
    range.subscribe((v) => (value = v))();
    expect(value).toEqual({ kind: 'rolling', key: '30d' });
  });
});

describe('rangeQuery', () => {
  const user = (timezone: string | null) => ({
    username: 'a', is_admin: false, timezone, disconnected: false,
    last_synced_at: null, last_played_at: null
  });

  it('compare is false only for all time', () => {
    range.set({ kind: 'rolling', key: 'all' });
    expect(get(rangeQuery).compare).toBe(false);
    range.set({ kind: 'rolling', key: '7d' });
    expect(get(rangeQuery).compare).toBe(true);
    range.set({ kind: 'calendar', key: 'this_month' });
    expect(get(rangeQuery).compare).toBe(true);
  });

  it('uses the user timezone, UTC when missing, and re-emits on change', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-12-31T23:30:00Z'));
    try {
      range.set({ kind: 'calendar', key: 'this_year' });
      auth.set({ user: null, loading: false });
      expect(get(rangeQuery).params.start).toBe('2026-01-01');
      const seen: (string | undefined)[] = [];
      const unsub = rangeQuery.subscribe((q) => seen.push(q.params.start));
      auth.set({ user: user('Europe/Berlin'), loading: false });
      auth.set({ user: user('America/Los_Angeles'), loading: false });
      unsub();
      expect(seen).toEqual(['2026-01-01', '2027-01-01', '2026-01-01']);
    } finally {
      vi.useRealTimers();
    }
  });
});
