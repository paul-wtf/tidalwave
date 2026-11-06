import { render, screen, waitFor } from '@testing-library/svelte';
import { describe, it, expect, beforeEach } from 'vitest';
import { mockApi } from '$lib/test/mockApi';
import { range } from '$lib/stores/range';
import InsightsPage from './InsightsPage.svelte';

const routes = (prefix: string) => ({
  [`${prefix}/on-this-day`]: [
    { year: 2025, listens: 3, top_tracks: [{ track: 'Aerodynamic', artist: 'Daft Punk', count: 3 }] }
  ],
  [`${prefix}/records`]: {
    longest_streak: null, current_streak: null,
    busiest_day: { date: '2026-10-05', listens: 8 }, longest_session: null
  },
  [`${prefix}/heatmap`]: { start: '2026-11-01', end: '2026-11-03', days: [{ date: '2026-11-02', listens: 2 }] },
  [`${prefix}/discoveries`]: {
    new_artists: [], new_tracks_count: 0, new_tracks: [], rediscoveries: []
  }
});
const headings = () => screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);

describe('InsightsPage', () => {
  beforeEach(() => range.set({ kind: 'rolling', key: '30d' }));

  it('shows the four sections in order', async () => {
    mockApi(routes('/stats'));
    render(InsightsPage);
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Discoveries' })).toBeInTheDocument());
    expect(headings()).toEqual(['On this day', 'Streaks and records', 'Listening heatmap', 'Discoveries']);
  });

  it('sends the selected range to range-bound endpoints but not to on-this-day', async () => {
    const { calls } = mockApi(routes('/stats'));
    render(InsightsPage);
    await waitFor(() => expect(calls.length).toBe(4));
    expect(calls.find((c) => c.startsWith('/stats/on-this-day'))).toBe('/stats/on-this-day');
    for (const p of ['records', 'heatmap', 'discoveries']) {
      expect(calls.find((c) => c.startsWith(`/stats/${p}?`))).toContain('since=');
    }
  });

  it('uses the dashboard container', async () => {
    mockApi(routes('/stats'));
    const { container } = render(InsightsPage);
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Discoveries' })).toBeInTheDocument());
    expect(container.querySelector('.dashboard')).not.toBeNull();
  });

  it('asks for a range instead of discoveries and skips the request for all time', async () => {
    range.set({ kind: 'rolling', key: 'all' });
    const { calls } = mockApi(routes('/stats'));
    render(InsightsPage);
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Listening heatmap' })).toBeInTheDocument());
    expect(screen.getByRole('heading', { name: 'Discoveries' })).toBeInTheDocument();
    expect(screen.getByText('Pick a range to see discoveries.')).toBeInTheDocument();
    expect(calls.some((c) => c.includes('discoveries'))).toBe(false);
  });

  it('reads the shared endpoints without range params in share mode', async () => {
    const { calls } = mockApi(routes('/shared/tok'));
    render(InsightsPage, { token: 'tok' });
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Discoveries' })).toBeInTheDocument());
    expect(calls.sort()).toEqual([
      '/shared/tok/discoveries', '/shared/tok/heatmap',
      '/shared/tok/on-this-day', '/shared/tok/records'
    ]);
  });

  it('shows an error message when a request fails', async () => {
    mockApi({});
    render(InsightsPage);
    await waitFor(() => expect(screen.getByText('Could not load this page. Please try again.')).toBeInTheDocument());
  });
});
