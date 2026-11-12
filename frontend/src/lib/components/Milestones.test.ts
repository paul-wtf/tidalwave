import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import Milestones from './Milestones.svelte';

const reached = [
  { count: 1000, played_at: '2024-03-01T23:30:00+00:00', track: 'Nightcall', artist: 'Kavinsky', album: 'OutRun' },
  { count: 5000, played_at: '2025-08-14T10:00:00+00:00', track: 'Sunset', artist: 'The Midnight', album: null }
];

describe('Milestones', () => {
  it('lists each reached milestone with its track, artist and local date', () => {
    render(Milestones, {
      milestones: { total: 6237, reached, next: { count: 10000, remaining: 3763 } },
      tz: 'Europe/Berlin'
    });
    expect(screen.getByRole('heading', { name: 'Milestones' })).toBeInTheDocument();
    expect(screen.getByText('1,000th listen')).toBeInTheDocument();
    expect(screen.getByText('5,000th listen')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Nightcall' })).toHaveAttribute(
      'href', '/track?artist=Kavinsky&track=Nightcall'
    );
    expect(screen.getByRole('link', { name: 'The Midnight' })).toHaveAttribute(
      'href', '/artist?artist=The+Midnight'
    );
    expect(screen.getByText('2 Mar 2024')).toBeInTheDocument();
  });

  it('says how many listens are left to the next milestone', () => {
    render(Milestones, { milestones: { total: 6237, reached, next: { count: 10000, remaining: 3763 } } });
    expect(screen.getByText('3,763 listens to go until 10,000')).toBeInTheDocument();
  });

  it('uses the singular for the last listen before a milestone', () => {
    render(Milestones, { milestones: { total: 999, reached: [], next: { count: 1000, remaining: 1 } } });
    expect(screen.getByText('1 listen to go until 1,000')).toBeInTheDocument();
  });

  it('shows only the countdown before the first milestone', () => {
    const { container } = render(Milestones, {
      milestones: { total: 12, reached: [], next: { count: 1000, remaining: 988 } }
    });
    expect(screen.getByText('988 listens to go until 1,000')).toBeInTheDocument();
    expect(container.querySelector('dl')).toBeNull();
  });

  it('drops the countdown after the last milestone', () => {
    render(Milestones, { milestones: { total: 120000, reached, next: null } });
    expect(screen.queryByText(/to go until/)).toBeNull();
  });
});
