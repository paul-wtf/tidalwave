import { describe, it, expect } from 'vitest';
import { standings, stepMs } from './race';

const artists = [
  { artist: 'Late', image_url: null, totals: [1, 3, 7] },
  { artist: 'Steady', image_url: null, totals: [2, 4, 4] },
  { artist: 'Early', image_url: null, totals: [3, 3, 3] },
  { artist: 'Absent', image_url: null, totals: [0, 0, 5] }
];

describe('standings', () => {
  it('ranks the artists by their total at the frame', () => {
    const first = standings(artists, 0, 10);
    expect(first.max).toBe(3);
    expect(first.rows.map((r) => r.rank)).toEqual([2, 1, 0, 3]);
    const last = standings(artists, 2, 10);
    expect(last.max).toBe(7);
    expect(last.rows.map((r) => r.rank)).toEqual([0, 2, 3, 1]);
    expect(last.rows.map((r) => r.total)).toEqual([7, 4, 3, 5]);
  });

  it('breaks ties by name', () => {
    expect(standings(artists, 1, 10).rows.map((r) => r.rank)).toEqual([2, 0, 1, 3]);
  });

  it('shows only the top places and nobody without a listen', () => {
    expect(standings(artists, 2, 2).rows.map((r) => r.shown)).toEqual([true, false, false, true]);
    expect(standings(artists, 0, 10).rows.map((r) => r.shown)).toEqual([true, true, true, false]);
  });

  it('copes with an empty race', () => {
    expect(standings([], 0, 10)).toEqual({ max: 1, rows: [] });
  });
});

describe('stepMs', () => {
  it('spreads a long race over about twenty seconds', () => {
    expect(stepMs(40)).toBe(500);
  });

  it('neither crawls through a short race nor rushes through a long one', () => {
    expect(stepMs(5)).toBe(700);
    expect(stepMs(400)).toBe(150);
  });
});
