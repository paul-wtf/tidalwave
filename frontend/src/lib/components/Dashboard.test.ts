import { render, screen, waitFor } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import Dashboard from './Dashboard.svelte';
import { mockApi } from '$lib/test/mockApi';

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
    expect(screen.getByText('Unknown album — Daft Punk').closest('a')).toBeNull();
  });
});
