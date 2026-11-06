import { render } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import Heatmap from './Heatmap.svelte';

const cells = (c: HTMLElement) => Array.from(c.querySelectorAll('rect'));
const byTitle = (c: HTMLElement, text: string) =>
  cells(c).find((r) => r.querySelector('title')?.textContent === text)!;

describe('Heatmap', () => {
  const heatmap = {
    start: '2026-11-02',
    end: '2026-11-12',
    days: [
      { date: '2026-11-03', listens: 1 },
      { date: '2026-11-06', listens: 14 },
      { date: '2026-11-10', listens: 7 }
    ]
  };

  it('draws one cell per day of the window, including empty days', () => {
    const { container } = render(Heatmap, { heatmap });
    expect(cells(container)).toHaveLength(11);
  });

  it('keeps a full year readable by scrolling instead of shrinking', () => {
    const year = { start: '2025-11-07', end: '2026-11-06', days: [] };
    const { container } = render(Heatmap, { heatmap: year });
    const svg = container.querySelector('svg')!;
    const columns = Number(svg.getAttribute('viewBox')!.split(' ')[2]) / 14;
    expect(columns).toBe(53);
    expect(svg.style.minWidth).toBe(`${columns * 14}px`);
  });

  it('scales to the container instead of a fixed pixel width', () => {
    const { container } = render(Heatmap, { heatmap });
    const svg = container.querySelector('svg')!;
    expect(svg.getAttribute('width')).toBe('100%');
    expect(svg.getAttribute('viewBox')).toMatch(/^0 0 \d+ 98$/);
  });

  it('titles each cell with date and count, singular for one listen', () => {
    const { container } = render(Heatmap, { heatmap });
    expect(byTitle(container, '2026-11-06: 14 listens')).toBeTruthy();
    expect(byTitle(container, '2026-11-03: 1 listen')).toBeTruthy();
    expect(byTitle(container, '2026-11-04: 0 listens')).toBeTruthy();
  });

  it('shades the busiest day darkest and empty days lightest', () => {
    const { container } = render(Heatmap, { heatmap });
    const level = (t: string) => Number(byTitle(container, t).getAttribute('data-level'));
    expect(level('2026-11-06: 14 listens')).toBe(4);
    expect(level('2026-11-04: 0 listens')).toBe(0);
    expect(level('2026-11-03: 1 listen')).toBeGreaterThan(0);
    expect(level('2026-11-03: 1 listen')).toBeLessThan(level('2026-11-10: 7 listens'));
    expect(level('2026-11-10: 7 listens')).toBeLessThan(4);
  });

  it('starts a new column on Monday and rows run Monday to Sunday', () => {
    const { container } = render(Heatmap, { heatmap });
    const pos = (t: string) => {
      const r = byTitle(container, t);
      return [Number(r.getAttribute('x')), Number(r.getAttribute('y'))];
    };
    const [monX, monY] = pos('2026-11-02: 0 listens');
    const [sunX, sunY] = pos('2026-11-08: 0 listens');
    const [nextMonX, nextMonY] = pos('2026-11-09: 0 listens');
    expect(sunX).toBe(monX);
    expect(sunY).toBeGreaterThan(monY);
    expect(nextMonX).toBeGreaterThan(monX);
    expect(nextMonY).toBe(monY);
  });

  it('places a window starting mid-week below the top row', () => {
    const { container } = render(Heatmap, {
      heatmap: { start: '2026-11-04', end: '2026-11-09', days: [] }
    });
    const wed = byTitle(container, '2026-11-04: 0 listens');
    const mon = byTitle(container, '2026-11-09: 0 listens');
    expect(Number(wed.getAttribute('y'))).toBeGreaterThan(Number(mon.getAttribute('y')));
  });
});
