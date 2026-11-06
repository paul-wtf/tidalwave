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
});
