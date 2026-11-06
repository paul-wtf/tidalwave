import { render, screen, waitFor } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mockApi } from '$lib/test/mockApi';

const pageStore = vi.hoisted(() => {
  const { writable } = require('svelte/store');
  return writable({ url: new URL('http://localhost/artist?artist=Daft%20Punk') });
});
vi.mock('$app/stores', () => ({ page: pageStore }));

import ArtistPage from './ArtistPage.svelte';

const common = {
  '/stats/metrics-over-time': [],
  '/stats/recent': [],
  '/stats/top-tracks': [],
  '/stats/top-albums': []
};
const sharedCommon = {
  '/shared/tok/metrics-over-time': [],
  '/shared/tok/recent': [],
  '/shared/tok/top-tracks': [],
  '/shared/tok/top-albums': []
};
const detail = { artist: 'Daft Punk', listens: 1234, seconds: 7200, rank: 1, first_listen: '2019-03-01T12:00:00Z', last_listen: '2026-11-06T12:00:00Z', image_url: null };

describe('ArtistPage', () => {
  beforeEach(() => pageStore.set({ url: new URL('http://localhost/artist?artist=Daft%20Punk') }));

  it('renders the header stats from the detail response', async () => {
    mockApi({ ...common, '/stats/artist': detail });
    render(ArtistPage);
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Daft Punk'));
    expect(screen.getByText('1,234')).toBeInTheDocument();
    expect(screen.getByText('2h 0m')).toBeInTheDocument();
    expect(screen.getByText('2019-03-01')).toBeInTheDocument();
    expect(screen.getByText('2026-11-06')).toBeInTheDocument();
  });

  it('shows the not-found text on 404', async () => {
    mockApi({ ...common });
    render(ArtistPage);
    await waitFor(() => expect(screen.getByText('Nothing found for Daft Punk.')).toBeInTheDocument());
  });

  it('reads from the shared endpoints in share mode', async () => {
    const { calls } = mockApi({ ...sharedCommon, '/shared/tok/artist': detail });
    render(ArtistPage, { token: 'tok' });
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Daft Punk'));
    expect(calls.length).toBeGreaterThan(0);
    expect(calls.every((c) => c.startsWith('/shared/tok/'))).toBe(true);
  });

  it('loads the new item when the URL changes', async () => {
    const calls = mockApi({ ...common, '/stats/artist': detail }).calls;
    render(ArtistPage);
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument());
    pageStore.set({ url: new URL('http://localhost/artist?artist=Other&album=Other&track=Other') });
    await waitFor(() =>
      expect(calls.some((c) => c.startsWith('/stats/artist?') && c.includes('Other'))).toBe(true)
    );
  });
});
