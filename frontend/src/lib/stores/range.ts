import { derived, writable } from 'svelte/store';
import { browser } from '$app/environment';
import type { Bucket, StatsParams } from '$lib/api/client';
import { auth } from './auth';

export type RollingKey = '24h' | '7d' | '30d' | '365d' | 'all';
export type CalendarKey =
  | 'this_week' | 'this_month' | 'this_year' | 'last_week' | 'last_month' | 'last_year';

export type RangeSel =
  | { kind: 'rolling'; key: RollingKey }
  | { kind: 'calendar'; key: CalendarKey }
  | { kind: 'custom'; from: string; to: string };

const KEY = 'tw-range-v2';
const LEGACY_KEY = 'tw-range';
const LEGACY: Record<string, RollingKey> = {
  day: '24h', week: '7d', month: '30d', year: '365d', all: 'all'
};
const DEFAULT: RangeSel = { kind: 'rolling', key: '30d' };

export const ROLLING: { key: RollingKey; label: string }[] = [
  { key: '24h', label: 'Last 24 hours' },
  { key: '7d', label: 'Last 7 days' },
  { key: '30d', label: 'Last 30 days' },
  { key: '365d', label: 'Last 365 days' },
  { key: 'all', label: 'All time' }
];

export const CALENDAR: { key: CalendarKey; label: string }[] = [
  { key: 'this_week', label: 'This week' },
  { key: 'this_month', label: 'This month' },
  { key: 'this_year', label: 'This year' },
  { key: 'last_week', label: 'Last week' },
  { key: 'last_month', label: 'Last month' },
  { key: 'last_year', label: 'Last year' }
];

const ROLLING_MS: Record<Exclude<RollingKey, 'all'>, number> = {
  '24h': 86_400_000,
  '7d': 7 * 86_400_000,
  '30d': 30 * 86_400_000,
  '365d': 365 * 86_400_000
};

const DAY_MS = 86_400_000;

const YMD = /^\d{4}-\d{2}-\d{2}$/;

function isSel(v: unknown): v is RangeSel {
  if (typeof v !== 'object' || v === null) return false;
  const s = v as Record<string, unknown>;
  if (s.kind === 'rolling') return ROLLING.some((r) => r.key === s.key);
  if (s.kind === 'calendar') return CALENDAR.some((r) => r.key === s.key);
  return (
    s.kind === 'custom' &&
    typeof s.from === 'string' && typeof s.to === 'string' &&
    YMD.test(s.from) && YMD.test(s.to) && s.from <= s.to
  );
}

function initial(): RangeSel {
  if (!browser) return DEFAULT;
  try {
    const saved = localStorage.getItem(KEY);
    if (saved) {
      const parsed: unknown = JSON.parse(saved);
      if (isSel(parsed)) return parsed;
    }
    const legacy = localStorage.getItem(LEGACY_KEY);
    if (legacy && Object.hasOwn(LEGACY, legacy)) return { kind: 'rolling', key: LEGACY[legacy] };
  } catch {
    return DEFAULT;
  }
  return DEFAULT;
}

/** Globally selected time window: drives every stats request across the site. */
export const range = writable<RangeSel>(initial());

range.subscribe((value) => {
  if (!browser) return;
  try {
    localStorage.setItem(KEY, JSON.stringify(value));
  } catch {
    return;
  }
});

export function rangeLabel(sel: RangeSel): string {
  if (sel.kind === 'custom') return `${sel.from} – ${sel.to}`;
  const list: { key: string; label: string }[] = sel.kind === 'rolling' ? ROLLING : CALENDAR;
  return list.find((r) => r.key === sel.key)?.label ?? '';
}

export type MovingKey =
  | 'rolling_7d' | 'rolling_30d' | 'rolling_365d' | 'this_week' | 'this_month' | 'this_year';

const MOVING: Record<MovingKey, RangeSel> = {
  rolling_7d: { kind: 'rolling', key: '7d' },
  rolling_30d: { kind: 'rolling', key: '30d' },
  rolling_365d: { kind: 'rolling', key: '365d' },
  this_week: { kind: 'calendar', key: 'this_week' },
  this_month: { kind: 'calendar', key: 'this_month' },
  this_year: { kind: 'calendar', key: 'this_year' }
};

/** The symbol a share can store to follow this selection, if it has one. */
export function movingKey(sel: RangeSel): MovingKey | null {
  if (sel.kind === 'custom') return null;
  const found = (Object.keys(MOVING) as MovingKey[]).find((k) => {
    const m = MOVING[k];
    return m.kind === sel.kind && 'key' in m && m.key === sel.key;
  });
  return found ?? null;
}

export function movingLabel(key: string): string {
  return Object.hasOwn(MOVING, key) ? rangeLabel(MOVING[key as MovingKey]) : key;
}

type Ymd = [number, number, number];

function parseYmd(s: string): Ymd {
  const [y, m, d] = s.split('-').map(Number);
  return [y, m, d];
}

function fmtYmd(y: number, m: number, d: number): string {
  return new Date(Date.UTC(y, m - 1, d)).toISOString().slice(0, 10);
}

function addDays(s: string, n: number): string {
  const [y, m, d] = parseYmd(s);
  return fmtYmd(y, m, d + n);
}

function diffDays(a: string, b: string): number {
  const [ay, am, ad] = parseYmd(a);
  const [by, bm, bd] = parseYmd(b);
  return Math.round((Date.UTC(by, bm - 1, bd) - Date.UTC(ay, am - 1, ad)) / DAY_MS);
}

function localDate(now: Date, tz: string): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit'
  }).format(now);
}

function weekStart(s: string): string {
  const [y, m, d] = parseYmd(s);
  const dow = new Date(Date.UTC(y, m - 1, d)).getUTCDay();
  return addDays(s, -((dow + 6) % 7));
}

function monthStart(s: string, offset = 0): string {
  const [y, m] = parseYmd(s);
  return fmtYmd(y, m + offset, 1);
}

function yearStart(s: string, offset = 0): string {
  return fmtYmd(parseYmd(s)[0] + offset, 1, 1);
}

type Span = { start: string; end?: string; calendar?: 'week' | 'month' | 'year' };

function calendarSpan(key: CalendarKey, today: string): Span {
  switch (key) {
    case 'this_week': return { start: weekStart(today), calendar: 'week' };
    case 'this_month': return { start: monthStart(today), calendar: 'month' };
    case 'this_year': return { start: yearStart(today), calendar: 'year' };
    case 'last_week': {
      const start = addDays(weekStart(today), -7);
      return { start, end: addDays(start, 7), calendar: 'week' };
    }
    case 'last_month': return { start: monthStart(today, -1), end: monthStart(today), calendar: 'month' };
    case 'last_year': return { start: yearStart(today, -1), end: yearStart(today), calendar: 'year' };
  }
}

export function toParams(sel: RangeSel, tz: string, now: Date): StatsParams {
  if (sel.kind === 'rolling') {
    return sel.key === 'all'
      ? {}
      : { since: new Date(now.getTime() - ROLLING_MS[sel.key]).toISOString() };
  }
  if (sel.kind === 'calendar') return calendarSpan(sel.key, localDate(now, tz));
  return { start: sel.from, end: addDays(sel.to, 1) };
}

export function bucketFor(sel: RangeSel, tz: string, now: Date): Bucket {
  let days: number;
  if (sel.kind === 'rolling') {
    days = sel.key === 'all' ? Infinity : ROLLING_MS[sel.key] / DAY_MS;
  } else if (sel.kind === 'calendar') {
    const today = localDate(now, tz);
    const span = calendarSpan(sel.key, today);
    days = diffDays(span.start, span.end ?? addDays(today, 1));
  } else {
    days = diffDays(sel.from, sel.to) + 1;
  }
  return days <= 92 ? 'day' : 'month';
}

export const rangeQuery = derived([range, auth], ([$range, $auth]) => {
  const tz = $auth.user?.timezone ?? 'UTC';
  const now = new Date();
  return {
    params: toParams($range, tz, now),
    bucket: bucketFor($range, tz, now),
    compare: !($range.kind === 'rolling' && $range.key === 'all')
  };
});
