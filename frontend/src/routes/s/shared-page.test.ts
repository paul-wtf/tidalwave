import { render, screen, waitFor } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import SharedPage from './[token]/+page.svelte';
import { mockApi } from '$lib/test/mockApi';

describe('shared dashboard page', () => {
  it('renders shared stats for a valid token', async () => {
    mockApi({
      '/shared/TOK/summary': {
        total_listens: 7, distinct_artists: 1, distinct_tracks: 1, distinct_albums: 0, total_seconds: 0
      },
      '/shared/TOK/top-artists': [{ artist: 'Kavinsky', count: 3, image_url: null }],
      '/shared/TOK/top-tracks': [],
      '/shared/TOK/top-albums': [],
      '/shared/TOK/clock': new Array(24).fill(0),
      '/shared/TOK/weekday': new Array(7).fill(0),
      '/shared/TOK/metrics-over-time': [],
      '/shared/TOK/recent': []
    });

    render(SharedPage, { props: { data: { token: 'TOK' } } });
    await waitFor(() => expect(screen.getByText('7')).toBeInTheDocument());
    expect(screen.getByText('Kavinsky')).toBeInTheDocument();
  });

  it('shows a not-found message when the token is invalid', async () => {
    mockApi({});
    render(SharedPage, { props: { data: { token: 'BAD' } } });
    await waitFor(() => expect(screen.getByText(/not found|revoked/i)).toBeInTheDocument());
  });
});
