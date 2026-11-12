import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import HourWeekdayGrid from './HourWeekdayGrid.svelte';

const empty = () => Array.from({ length: 7 }, () => new Array(24).fill(0));
const cell = (c: HTMLElement, title: string) => c.querySelector(`[title="${title}"]`)!;

describe('HourWeekdayGrid', () => {
  const grid = empty();
  grid[0][13] = 2;
  grid[4][20] = 8;
  grid[6][0] = 1;

  it('draws one cell per weekday and hour', () => {
    const { container } = render(HourWeekdayGrid, { grid });
    expect(container.querySelectorAll('.cell')).toHaveLength(7 * 24);
  });

  it('titles each cell with weekday, hour and count', () => {
    const { container } = render(HourWeekdayGrid, { grid });
    expect(cell(container, 'Mon 13:00: 2 listens')).toBeTruthy();
    expect(cell(container, 'Sun 00:00: 1 listen')).toBeTruthy();
    expect(cell(container, 'Tue 05:00: 0 listens')).toBeTruthy();
  });

  it('shades the busiest slot darkest and empty slots lightest', () => {
    const { container } = render(HourWeekdayGrid, { grid });
    const level = (t: string) => Number(cell(container, t).getAttribute('data-level'));
    expect(level('Fri 20:00: 8 listens')).toBe(4);
    expect(level('Tue 05:00: 0 listens')).toBe(0);
    expect(level('Sun 00:00: 1 listen')).toBe(1);
    expect(level('Mon 13:00: 2 listens')).toBe(1);
  });

  it('puts Monday in the first row and midnight in the first column', () => {
    const { container } = render(HourWeekdayGrid, { grid });
    const cells = Array.from(container.querySelectorAll('.cell'));
    expect(cells[0].getAttribute('title')).toBe('Mon 00:00: 0 listens');
    expect(cells[24].getAttribute('title')).toBe('Tue 00:00: 0 listens');
    expect(cells[167].getAttribute('title')).toBe('Sun 23:00: 0 listens');
  });

  it('names the timezone in the heading and says local time in share views', () => {
    const { unmount } = render(HourWeekdayGrid, { grid, tz: 'Europe/Berlin' });
    expect(screen.getByRole('heading', { name: 'By weekday and hour (Europe/Berlin)' })).toBeInTheDocument();
    unmount();
    render(HourWeekdayGrid, { grid, tz: null });
    expect(screen.getByRole('heading', { name: 'By weekday and hour (local time)' })).toBeInTheDocument();
  });

  it('summarises total and peak as text', () => {
    render(HourWeekdayGrid, { grid });
    expect(screen.getByText('11 listens · busiest Fri 20:00 with 8')).toBeInTheDocument();
  });

  it('has no peak to report without listens', () => {
    const { container } = render(HourWeekdayGrid, { grid: empty() });
    expect(screen.getByText('0 listens')).toBeInTheDocument();
    expect(container.querySelectorAll('[data-level="0"]')).toHaveLength(7 * 24);
  });
});
