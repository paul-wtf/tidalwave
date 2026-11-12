import { render, screen, waitFor, within } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mockApi } from '$lib/test/mockApi';
import { stubDeferredFetch } from '$lib/test/deferredFetch';

const pageStore = vi.hoisted(() => {
  const { writable } = require('svelte/store');
  return writable({ url: new URL('http://localhost/artist?artist=Daft+Punk') });
});
vi.mock('$app/stores', () => ({ page: pageStore }));

import ArtistPage from './ArtistPage.svelte';

const url = (name: string) => new URL(`http://localhost/artist?${new URLSearchParams({ artist: name })}`);
const detail = (name: string) => ({ artist: name, listens: 1234, seconds: 7200, rank: 1, first_listen: '2019-03-01T12:00:00Z', last_listen: '2026-11-06T12:00:00Z', image_url: null });
const rows = {
  topTracks: [{ track: 'Aerodynamic', artist: 'Daft Punk', count: 6 }],
  topAlbums: [{ album: 'Discovery', artist: 'Daft Punk', count: 8, image_url: null }],
  recent: [
    { track: 'One More Time', artist: 'Daft Punk', album: 'Discovery', played_at: '2026-11-05T10:00:00Z' }
  ]
};
const routes = (prefix: string, name = 'Daft Punk') => ({
  [`${prefix}/artist`]: detail(name),
  [`${prefix}/metrics-over-time`]: [],
  [`${prefix}/recent`]: rows.recent,
  [`${prefix}/top-tracks`]: rows.topTracks,
  [`${prefix}/top-albums`]: rows.topAlbums
});
const section = (title: string) => within(screen.getByRole('heading', { name: title }).closest('section')!);
const heading = () => screen.getByRole('heading', { level: 1 });

describe('ArtistPage', () => {
  beforeEach(() => pageStore.set({ url: url('Daft Punk') }));

  it('renders the header stats from the detail response', async () => {
    mockApi(routes('/stats'));
    render(ArtistPage);
    await waitFor(() => expect(heading()).toHaveTextContent('Daft Punk'));
    expect(screen.getByText('1,234')).toBeInTheDocument();
    expect(screen.getByText('2h 0m')).toBeInTheDocument();
    expect(screen.getByText('1 Mar 2019')).toBeInTheDocument();
    expect(screen.getByText('6 Nov 2026')).toBeInTheDocument();
  });

  it('lists top tracks, top albums and recent plays in their sections', async () => {
    mockApi(routes('/stats'));
    render(ArtistPage);
    await waitFor(() => expect(heading()).toBeInTheDocument());
    await waitFor(() => expect(section('Top Tracks').getByText('Aerodynamic — Daft Punk')).toBeInTheDocument());
    expect(section('Top Albums').getByText('Discovery — Daft Punk')).toBeInTheDocument();
    expect(section('Recent').getByText('One More Time')).toBeInTheDocument();
    expect(section('Top Tracks').getByRole('link', { name: 'Aerodynamic — Daft Punk' })).toHaveAttribute(
      'href', '/track?artist=Daft+Punk&track=Aerodynamic');
  });

  it('shows a dash while durations resolve', async () => {
    mockApi({ ...routes('/stats'), '/stats/artist': { ...detail('Daft Punk'), seconds: 0 } });
    render(ArtistPage);
    await waitFor(() => expect(heading()).toHaveTextContent('Daft Punk'));
    expect(screen.queryByText('0s')).toBeNull();
    expect(screen.getByText('resolving durations…')).toBeInTheDocument();
  });

  it('shows the owner\'s local date in share mode', async () => {
    mockApi({
      ...routes('/shared/tok'),
      '/shared/tok/artist': { ...detail('Daft Punk'), first_listen: '2024-11-08T00:30:00+01:00', last_listen: '2024-11-08T00:30:00+01:00' }
    });
    render(ArtistPage, { token: 'tok' });
    await waitFor(() => expect(heading()).toHaveTextContent('Daft Punk'));
    expect(screen.getAllByText('8 Nov 2024')).toHaveLength(2);
  });

  it('uses the dashboard container', async () => {
    mockApi(routes('/stats'));
    const { container } = render(ArtistPage);
    await waitFor(() => expect(heading()).toBeInTheDocument());
    expect(container.querySelector('.dashboard')).not.toBeNull();
  });

  it('shows the not-found text on 404', async () => {
    mockApi({});
    render(ArtistPage);
    await waitFor(() => expect(screen.getByText('Nothing found for Daft Punk.')).toBeInTheDocument());
  });

  it('reads from the shared endpoints in share mode', async () => {
    const { calls } = mockApi(routes('/shared/tok'));
    render(ArtistPage, { token: 'tok' });
    await waitFor(() => expect(heading()).toHaveTextContent('Daft Punk'));
    expect(calls.length).toBeGreaterThan(0);
    expect(calls.every((c) => c.startsWith('/shared/tok/'))).toBe(true);
    await waitFor(() =>
      expect(section('Top Albums').getByRole('link', { name: 'Discovery — Daft Punk' })).toHaveAttribute(
        'href', '/s/tok/album?artist=Daft+Punk&album=Discovery')
    );
  });

  it('loads the new item when the URL changes', async () => {
    const { calls } = mockApi(routes('/stats'));
    render(ArtistPage);
    await waitFor(() => expect(heading()).toBeInTheDocument());
    pageStore.set({ url: url('Other') });
    await waitFor(() =>
      expect(calls.some((c) => c.startsWith('/stats/artist?') && c.includes('artist=Other'))).toBe(true)
    );
  });

  it('ignores a slow response for the previous URL', async () => {
    const { release } = stubDeferredFetch(
      (u) => {
        const name = u.searchParams.get('artist') ?? '';
        const map: Record<string, unknown> = {
          '/stats/artist': detail(name),
          '/stats/metrics-over-time': [],
          '/stats/recent': [],
          '/stats/top-tracks': [],
          '/stats/top-albums': []
        };
        return map[u.pathname];
      },
      (u) => u.searchParams.get('artist') === 'Slow'
    );
    pageStore.set({ url: url('Slow') });
    render(ArtistPage);
    pageStore.set({ url: url('Fast') });
    await waitFor(() => expect(heading()).toHaveTextContent('Fast'));
    release();
    await new Promise((r) => setTimeout(r, 50));
    expect(heading()).toHaveTextContent('Fast');
  });

  it('puts the trend chart under the header so both share the cover colour', async () => {
    mockApi(routes('/stats'));
    const { container } = render(ArtistPage);
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument());
    const tinted = container.querySelector<HTMLElement>('.tinted')!;
    expect(tinted).toContainElement(screen.getByRole('heading', { level: 1 }));
    expect(tinted).toContainElement(screen.getByText('Listens over time').closest('figure'));
  });
});
