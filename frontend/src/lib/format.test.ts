import { describe, it, expect } from 'vitest';
import { weekdayName, formatRelative, formatLocalDate } from './format';

describe('weekdayName', () => {
  it('maps index 0 to Monday and 6 to Sunday', () => {
    expect(weekdayName(0)).toBe('Mon');
    expect(weekdayName(6)).toBe('Sun');
  });
});

describe('formatRelative', () => {
  const now = new Date('2026-11-06T12:00:00Z');
  const ago = (ms: number) => new Date(now.getTime() - ms).toISOString();
  it.each([
    [5_000, 'just now'],
    [59_000, 'just now'],
    [60_000, '1 min ago'],
    [3 * 60_000, '3 min ago'],
    [59 * 60_000, '59 min ago'],
    [3_600_000, '1 h ago'],
    [2 * 3_600_000, '2 h ago'],
    [23 * 3_600_000, '23 h ago'],
    [24 * 3_600_000, '1 day ago'],
    [4 * 24 * 3_600_000, '4 days ago']
  ])('%d ms -> %s', (ms, expected) => {
    expect(formatRelative(ago(ms), now)).toBe(expected);
  });
  it('treats future timestamps as just now', () => {
    expect(formatRelative(new Date(now.getTime() + 5000).toISOString(), now)).toBe('just now');
  });
});

describe('formatLocalDate', () => {
  it('formats in UTC', () => {
    expect(formatLocalDate('2026-11-05T23:30:00Z', 'UTC')).toBe('2026-11-05');
  });
  it('rolls over midnight in a zone ahead of UTC', () => {
    expect(formatLocalDate('2026-11-05T23:30:00Z', 'Europe/Berlin')).toBe('2026-11-06');
  });
  it('rolls back in a zone behind UTC', () => {
    expect(formatLocalDate('2026-11-06T02:00:00Z', 'America/New_York')).toBe('2026-11-05');
  });
});
