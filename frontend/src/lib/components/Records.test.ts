import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import Records from './Records.svelte';

const empty = { longest_streak: null, current_streak: null, busiest_day: null, longest_session: null };

describe('Records', () => {
  it('renders every record that is present', () => {
    render(Records, {
      records: {
        longest_streak: { days: 9, start: '2026-10-01', end: '2026-10-09' },
        current_streak: { days: 1, start: '2026-11-06' },
        busiest_day: { date: '2026-10-05', listens: 88 },
        longest_session: { start: '2026-10-05T10:00:00Z', listens: 40, seconds: 9000 }
      }
    });
    expect(screen.getByText('9 days')).toBeInTheDocument();
    expect(screen.getByText('2026-10-01 to 2026-10-09')).toBeInTheDocument();
    expect(screen.getByText('1 day')).toBeInTheDocument();
    expect(screen.getByText('since 2026-11-06')).toBeInTheDocument();
    expect(screen.getByText('88 listens')).toBeInTheDocument();
    expect(screen.getByText('2026-10-05')).toBeInTheDocument();
    expect(screen.getByText('40 listens')).toBeInTheDocument();
    expect(screen.getByText('2026-10-05, 2h 30m')).toBeInTheDocument();
  });

  it('omits records that are null', () => {
    render(Records, { records: { ...empty, busiest_day: { date: '2026-10-05', listens: 3 } } });
    expect(screen.getByText('Busiest day')).toBeInTheDocument();
    expect(screen.queryByText('Current streak')).toBeNull();
    expect(screen.queryByText('Longest streak')).toBeNull();
  });

  it('formats the session start in the given timezone', () => {
    render(Records, {
      records: { ...empty, longest_session: { start: '2026-10-05T23:30:00Z', listens: 5, seconds: 600 } },
      tz: 'Europe/Berlin'
    });
    expect(screen.getByText('2026-10-06, 10m')).toBeInTheDocument();
  });

  it('shows the empty state when nothing is recorded', () => {
    render(Records, { records: empty });
    expect(screen.getByText('No records in this range yet.')).toBeInTheDocument();
  });
});
