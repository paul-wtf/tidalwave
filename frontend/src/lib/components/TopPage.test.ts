import { render, screen, waitFor } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import TopPage from './TopPage.svelte';
import { mockApi } from '$lib/test/mockApi';

describe('TopPage', () => {
  it('labels tracks with their artist so same-titled songs are distinguishable', async () => {
    mockApi({
      '/stats/metrics-over-time': [],
      '/stats/top-tracks': [
        { track: 'Paradise', artist: 'Coldplay', count: 12 },
        { track: 'Paradise', artist: 'George Ezra', count: 7 }
      ]
    });

    render(TopPage, { props: { kind: 'tracks' } });
    await waitFor(() => expect(screen.getByText('Paradise — Coldplay')).toBeInTheDocument());
    expect(screen.getByText('Paradise — George Ezra')).toBeInTheDocument();
  });

  it('labels shared tracks with their artist as well', async () => {
    const { calls } = mockApi({
      '/shared/TOK/metrics-over-time': [],
      '/shared/TOK/top-tracks': [{ track: 'Paradise', artist: 'Coldplay', count: 12 }]
    });

    render(TopPage, { props: { kind: 'tracks', token: 'TOK' } });
    await waitFor(() => expect(screen.getByText('Paradise — Coldplay')).toBeInTheDocument());
    expect(calls.every((c) => c.startsWith('/shared/TOK/'))).toBe(true);
  });
});
