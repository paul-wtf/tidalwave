import { render, screen, waitFor } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import Dashboard from './Dashboard.svelte';
import { mockApi } from '$lib/test/mockApi';
import { auth } from '$lib/stores/auth';

describe('Dashboard', () => {
  it('loads and renders the headline stats and top lists', async () => {
    mockApi({
      '/stats/summary': {
        total_listens: 42, distinct_artists: 5, distinct_tracks: 30, distinct_albums: 8, total_seconds: 7200
      },
      // Empty trend → charts show no y-axis numbers, so the stat-card values below stay unique.
      '/stats/metrics-over-time': [],
      '/stats/top-artists': [{ artist: 'Daft Punk', count: 10, image_url: null }],
      '/stats/top-tracks': [{ track: 'Aerodynamic', artist: 'Daft Punk', count: 6 }],
      '/stats/top-albums': [{ album: 'Discovery', artist: 'Daft Punk', count: 8, image_url: null }],
      '/stats/clock': new Array(24).fill(0),
      '/stats/weekday': new Array(7).fill(0),
      '/stats/recent': []
    });

    render(Dashboard);
    await waitFor(() => expect(screen.getByText('42')).toBeInTheDocument());
    expect(screen.getByText('Daft Punk')).toBeInTheDocument();
    expect(screen.getByText('Aerodynamic — Daft Punk')).toBeInTheDocument();
    expect(screen.getByText('2h 0m')).toBeInTheDocument(); // 7200s formatted
  });

  const rest = {
    '/stats/metrics-over-time': [],
    '/stats/top-artists': [],
    '/stats/top-tracks': [],
    '/stats/top-albums': [],
    '/stats/clock': new Array(24).fill(0),
    '/stats/weekday': new Array(7).fill(0),
    '/stats/recent': []
  };

  it('shows the change against the previous period on each card', async () => {
    mockApi({
      ...rest,
      '/stats/summary': {
        total_listens: 112, distinct_artists: 5, distinct_tracks: 30, distinct_albums: 8, total_seconds: 3600,
        previous: {
          total_listens: 100, distinct_artists: 10, distinct_tracks: 30, distinct_albums: 8, total_seconds: 0
        }
      }
    });
    render(Dashboard);
    await waitFor(() => expect(screen.getByText('+12 % vs. previous')).toBeInTheDocument());
    expect(screen.getByText('−50 % vs. previous')).toBeInTheDocument();
    expect(screen.getByText('±0 % vs. previous')).toBeInTheDocument();
    // previous seconds is 0, so no delta there: exactly three deltas
    expect(screen.getAllByText(/vs\. previous/)).toHaveLength(3);
  });

  it('shows no change without previous data', async () => {
    mockApi({
      ...rest,
      '/stats/summary': {
        total_listens: 42, distinct_artists: 5, distinct_tracks: 30, distinct_albums: 8, total_seconds: 7200,
        previous: null
      }
    });
    render(Dashboard);
    await waitFor(() => expect(screen.getByText('42')).toBeInTheDocument());
    expect(screen.queryByText(/vs\. previous/)).toBeNull();
  });

  it('shows no change in shared mode', async () => {
    mockApi({
      ...rest,
      '/shared/tok/summary': {
        total_listens: 42, distinct_artists: 5, distinct_tracks: 30, distinct_albums: 8, total_seconds: 7200,
        previous: {
          total_listens: 21, distinct_artists: 5, distinct_tracks: 30, distinct_albums: 8, total_seconds: 7200
        }
      },
      '/shared/tok/metrics-over-time': [],
      '/shared/tok/top-artists': [],
      '/shared/tok/top-tracks': [],
      '/shared/tok/top-albums': [],
      '/shared/tok/clock': new Array(24).fill(0),
      '/shared/tok/weekday': new Array(7).fill(0),
      '/shared/tok/recent': []
    });
    render(Dashboard, { token: 'tok' });
    await waitFor(() => expect(screen.getByText('42')).toBeInTheDocument());
    expect(screen.queryByText(/vs\. previous/)).toBeNull();
  });

  it('links top-list rows under the share base in shared mode', async () => {
    mockApi({
      ...rest,
      '/shared/tok/summary': {
        total_listens: 42, distinct_artists: 5, distinct_tracks: 30, distinct_albums: 8, total_seconds: 7200
      },
      '/shared/tok/metrics-over-time': [],
      '/shared/tok/top-artists': [{ artist: 'Daft Punk', count: 10, image_url: null }],
      '/shared/tok/top-tracks': [],
      '/shared/tok/top-albums': [{ album: null, artist: 'Daft Punk', count: 2, image_url: null }],
      '/shared/tok/clock': new Array(24).fill(0),
      '/shared/tok/weekday': new Array(7).fill(0),
      '/shared/tok/recent': []
    });
    render(Dashboard, { token: 'tok' });
    const link = await screen.findByRole('link', { name: 'Daft Punk' });
    expect(link.getAttribute('href')!.startsWith('/s/tok/artist?')).toBe(true);
    expect(screen.getByText('Unknown album — Daft Punk').closest('a')).toHaveAttribute(
      'href', '/s/tok/artist?artist=Daft+Punk');
  });

  it("labels the clock with the user's timezone, and with local time in share mode", async () => {
    auth.set({
      user: { username: 'p', is_admin: false, timezone: 'Europe/Berlin', disconnected: false, last_synced_at: null, last_played_at: null },
      loading: false
    });
    const summary = { total_listens: 1, distinct_artists: 1, distinct_tracks: 1, distinct_albums: 1, total_seconds: 60 };
    mockApi({ ...rest, '/stats/summary': summary, '/shared/tok/summary': summary,
      '/shared/tok/metrics-over-time': [], '/shared/tok/top-artists': [], '/shared/tok/top-tracks': [],
      '/shared/tok/top-albums': [], '/shared/tok/clock': new Array(24).fill(0),
      '/shared/tok/weekday': new Array(7).fill(0), '/shared/tok/recent': [] });
    const own = render(Dashboard);
    await waitFor(() => expect(screen.getByText('By hour (Europe/Berlin)')).toBeInTheDocument());
    own.unmount();
    render(Dashboard, { token: 'tok' });
    await waitFor(() => expect(screen.getByText('By hour (local time)')).toBeInTheDocument());
  });

  const summary = {
    total_listens: 42, distinct_artists: 5, distinct_tracks: 30, distinct_albums: 8, total_seconds: 7200
  };
  const point = (day: number, listens: number) => ({
    period: `2026-11-0${day}T00:00:00`, listens, artists: 1, albums: 1, seconds: 60
  });

  it('turns the listening trend into the background wave', async () => {
    mockApi({
      ...rest, '/stats/summary': summary,
      '/stats/metrics-over-time': [point(1, 3), point(2, 9), point(3, 5)]
    });
    const { container } = render(Dashboard);
    await waitFor(() => expect(container.querySelector('.wave')).not.toBeNull());
    expect(container.querySelectorAll('.wave path.layer')).toHaveLength(4);
  });

  it('keeps the static background without a trend', async () => {
    mockApi({ ...rest, '/stats/summary': summary });
    const { container } = render(Dashboard);
    await waitFor(() => expect(screen.getByText('42')).toBeInTheDocument());
    expect(container.querySelector('.wave')).toBeNull();
  });

  it('shows what is playing on the own overview', async () => {
    const { calls } = mockApi({
      ...rest,
      '/stats/summary': {
        total_listens: 42, distinct_artists: 5, distinct_tracks: 30, distinct_albums: 8, total_seconds: 7200
      },
      '/stats/now-playing': { track: 'Nightcall', artist: 'Kavinsky', album: 'OutRun', image_url: null }
    });
    render(Dashboard);
    expect(await screen.findByText('now playing')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Nightcall' })).toBeInTheDocument();
    expect(calls).toContain('/stats/now-playing');
  });

  it('never asks what is playing in a share view', async () => {
    const shared = Object.fromEntries(
      Object.entries(rest).map(([path, body]) => [path.replace('/stats/', '/shared/TOK/'), body])
    );
    const { calls } = mockApi({
      ...shared,
      '/shared/TOK/summary': {
        total_listens: 42, distinct_artists: 5, distinct_tracks: 30, distinct_albums: 8, total_seconds: 7200
      },
      '/shared/TOK/now-playing': { track: 'Nightcall', artist: 'Kavinsky', album: 'OutRun', image_url: null }
    });
    render(Dashboard, { props: { token: 'TOK' } });
    await waitFor(() => expect(screen.getByText('42')).toBeInTheDocument());
    expect(calls.some((c) => c.includes('now-playing'))).toBe(false);
    expect(screen.queryByText('now playing')).toBeNull();
  });

  it('notes how many listens before the first scrobble come from an import', async () => {
    auth.set({ user: { username: 'paul', is_admin: false, timezone: 'UTC' } as never, loading: false });
    mockApi({
      ...rest,
      '/stats/summary': { total_listens: 20000, distinct_artists: 1, distinct_tracks: 1, distinct_albums: 1, total_seconds: 0 },
      '/stats/sources': {
        imported: 9000, imported_before_lastfm: 8714, lastfm_first: '2021-07-01T08:00:00+00:00',
        sources: [{ source: 'spotify', listens: 9000 }]
      }
    });
    render(Dashboard);
    expect(await screen.findByText(/8,714 listens before 1 Jul 2021 come from a Spotify import/))
      .toBeInTheDocument();
  });

  it('says nothing about imports when there are none', async () => {
    mockApi({
      ...rest,
      '/stats/summary': { total_listens: 3, distinct_artists: 1, distinct_tracks: 1, distinct_albums: 1, total_seconds: 0 },
      '/stats/sources': { imported: 0, imported_before_lastfm: 0, lastfm_first: null, sources: [] }
    });
    render(Dashboard);
    await waitFor(() => expect(screen.getByText('3')).toBeInTheDocument());
    expect(screen.queryByText(/import/)).toBeNull();
  });
});
