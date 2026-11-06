import { describe, it, expect, beforeEach, vi } from 'vitest';
import { toParams, bucketFor, rangeLabel } from './range';

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

  it('maps the legacy key', async () => {
    localStorage.setItem('tw-range', 'month');
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
