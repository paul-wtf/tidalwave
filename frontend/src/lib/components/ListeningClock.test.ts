import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import ListeningClock from './ListeningClock.svelte';

const hours = new Array(24).fill(0);
const busy = [4, 2, 1, 0, 0, 0, 1, 3, 8, 14, 19, 22, 18, 16, 15, 17, 24, 31, 45, 58, 66, 52, 38, 21];

describe('ListeningClock', () => {
  it('names the timezone in the caption', () => {
    render(ListeningClock, { hours, tz: 'Europe/Berlin' });
    expect(screen.getByText('By hour (Europe/Berlin)')).toBeInTheDocument();
  });

  it('says local time in share views', () => {
    render(ListeningClock, { hours, tz: null });
    expect(screen.getByText('By hour (local time)')).toBeInTheDocument();
  });

  it('draws a ring with one segment per hour', () => {
    const { container } = render(ListeningClock, { hours: busy });
    expect(screen.getByRole('img', { name: 'Listens by hour of day on a 24-hour dial' })).toBeInTheDocument();
    const segments = Array.from(container.querySelectorAll('path.seg'));
    expect(segments.map((s) => s.getAttribute('data-hour'))).toEqual(
      Array.from({ length: 24 }, (_, h) => String(h))
    );
    expect(segments[20].querySelector('title')!.textContent).toBe('20:00: 66 listens');
  });

  it('lets the busiest hour reach the rim and leaves empty hours without a segment', () => {
    const { container } = render(ListeningClock, { hours: busy });
    const reach = (h: number) => Number(container.querySelector(`path.seg[data-hour="${h}"]`)!.getAttribute('data-reach'));
    expect(reach(20)).toBe(1);
    expect(reach(3)).toBe(0);
    expect(reach(10)).toBeGreaterThan(reach(8));
    expect(reach(10)).toBeLessThan(1);
  });

  it('marks 00, 06, 12 and 18 on the dial', () => {
    const { container } = render(ListeningClock, { hours: busy });
    const marks = Array.from(container.querySelectorAll('text.mark'));
    expect(marks.map((m) => m.textContent)).toEqual(['00', '06', '12', '18']);
    const top = marks[0];
    expect(Number(top.getAttribute('x'))).toBeCloseTo(0);
    expect(Number(top.getAttribute('y'))).toBeLessThan(0);
    expect(Number(marks[1].getAttribute('x'))).toBeGreaterThan(0);
  });

  it('offers every hour as text', () => {
    render(ListeningClock, { hours: busy });
    const items = screen.getAllByRole('listitem').map((li) => li.textContent);
    expect(items).toHaveLength(24);
    expect(items[0]).toBe('00:00: 4 listens');
    expect(items[6]).toBe('06:00: 1 listen');
    expect(items[20]).toBe('20:00: 66 listens');
    expect(screen.getByText('475 listens · peak 20:00 with 66')).toBeInTheDocument();
  });

  it('shows the peak hour in the middle, and nothing without listens', () => {
    const { container, unmount } = render(ListeningClock, { hours: busy });
    expect(container.querySelector('text.peak')!.textContent).toBe('20:00');
    unmount();
    const empty = render(ListeningClock, { hours });
    expect(empty.container.querySelector('text.peak')).toBeNull();
    expect(screen.getByText('0 listens')).toBeInTheDocument();
  });
});
