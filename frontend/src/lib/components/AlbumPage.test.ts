import { render, screen, waitFor, within } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mockApi } from '$lib/test/mockApi';
import { stubDeferredFetch } from '$lib/test/deferredFetch';

const pageStore = vi.hoisted(() => {
  const { writable } = require('svelte/store');
  return writable({ url: new URL('http://localhost/album?artist=Daft+Punk&album=Discovery') });
});
vi.mock('$app/stores', () => ({ page: pageStore }));

import AlbumPage from './AlbumPage.svelte';

const url = (name: string) => new URL(`http://localhost/album?${new URLSearchParams({ artist: "Daft Punk", album: name })}`);
const detail = (name: string) => ({ artist: 'Daft Punk', album: name, listens: 1234, seconds: 7200, first_listen: '2019-03-01T12:00:00Z', last_listen: '2026-11-06T12:00:00Z', image_url: null });
const rows = {
  topTracks: [{ track: 'Aerodynamic', artist: 'Daft Punk', count: 6 }],
  topAlbums: [{ album: 'Discovery', artist: 'Daft Punk', count: 8, image_url: null }],
  recent: [
    { track: 'One More Time', artist: 'Daft Punk', album: 'Discovery', played_at: '2026-11-05T10:00:00Z' }
  ]
};
const routes = (prefix: string, name = 'Discovery') => ({
  [`${prefix}/album`]: detail(name),
  [`${prefix}/album-runs`]: { total: 0, runs: [] },
  [`${prefix}/metrics-over-time`]: [],
  [`${prefix}/recent`]: rows.recent,
  [`${prefix}/top-tracks`]: rows.topTracks,
  [`${prefix}/top-albums`]: rows.topAlbums
});
const section = (title: string) => within(screen.getByRole('heading', { name: title }).closest('section')!);
const heading = () => screen.getByRole('heading', { level: 1 });

describe('AlbumPage', () => {
  beforeEach(() => pageStore.set({ url: url('Discovery') }));

  it('renders the header stats from the detail response', async () => {
    mockApi(routes('/stats'));
    render(AlbumPage);
    await waitFor(() => expect(heading()).toHaveTextContent('Discovery'));
    expect(screen.getByText('1,234')).toBeInTheDocument();
    expect(screen.getByText('2h 0m')).toBeInTheDocument();
    expect(screen.getByText('1 Mar 2019')).toBeInTheDocument();
    expect(screen.getByText('6 Nov 2026')).toBeInTheDocument();
  });

  it('lists its tracks and links to the artist', async () => {
    const { calls } = mockApi(routes('/stats'));
    render(AlbumPage);
    await waitFor(() => expect(section('Tracks').getByText('Aerodynamic — Daft Punk')).toBeInTheDocument());
    expect(calls.some((c) => c.startsWith('/stats/top-tracks?') && c.includes('album=Discovery'))).toBe(true);
    expect(screen.getByRole('link', { name: 'Daft Punk' })).toHaveAttribute('href', '/artist?artist=Daft+Punk');
  });

  it('says how often the album was played through', async () => {
    const { calls } = mockApi({
      ...routes('/stats'),
      '/stats/album-runs': {
        total: 3,
        runs: [{
          artist: 'Daft Punk', album: 'Discovery', started_at: '2026-11-05T10:00:00Z',
          tracks: 14, listens: 14, seconds: 3660, image_url: null
        }]
      }
    });
    render(AlbumPage);
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Played through 3 times' })).toBeInTheDocument());
    const call = calls.find((c) => c.startsWith('/stats/album-runs?'))!;
    expect(call).toContain('artist=Daft+Punk');
    expect(call).toContain('album=Discovery');
  });

  it('leaves the section out when the album was never played through', async () => {
    mockApi(routes('/stats'));
    render(AlbumPage);
    await waitFor(() => expect(heading()).toBeInTheDocument());
    expect(screen.queryByRole('heading', { name: /Played through/ })).toBeNull();
  });

  it('shows a dash while durations resolve', async () => {
    mockApi({ ...routes('/stats'), '/stats/album': { ...detail('Discovery'), seconds: 0 } });
    render(AlbumPage);
    await waitFor(() => expect(heading()).toBeInTheDocument());
    expect(screen.queryByText('0s')).toBeNull();
    expect(screen.getByText('resolving durations…')).toBeInTheDocument();
  });

  it('shows the owner\'s local date in share mode', async () => {
    mockApi({
      ...routes('/shared/tok'),
      '/shared/tok/album': { ...detail('Discovery'), first_listen: '2024-11-08T00:30:00+01:00', last_listen: '2024-11-08T00:30:00+01:00' }
    });
    render(AlbumPage, { token: 'tok' });
    await waitFor(() => expect(heading()).toBeInTheDocument());
    expect(screen.getAllByText('8 Nov 2024')).toHaveLength(2);
  });

  it('uses the dashboard container', async () => {
    mockApi(routes('/stats'));
    const { container } = render(AlbumPage);
    await waitFor(() => expect(heading()).toBeInTheDocument());
    expect(container.querySelector('.dashboard')).not.toBeNull();
  });

  it('shows the not-found text on 404', async () => {
    mockApi({});
    render(AlbumPage);
    await waitFor(() => expect(screen.getByText('Nothing found for Discovery.')).toBeInTheDocument());
  });

  it('reads from the shared endpoints in share mode', async () => {
    const { calls } = mockApi(routes('/shared/tok'));
    render(AlbumPage, { token: 'tok' });
    await waitFor(() => expect(heading()).toHaveTextContent('Discovery'));
    expect(calls.length).toBeGreaterThan(0);
    expect(calls.every((c) => c.startsWith('/shared/tok/'))).toBe(true);
    expect(screen.getByRole('link', { name: 'Daft Punk' })).toHaveAttribute('href', '/s/tok/artist?artist=Daft+Punk');
  });

  it('loads the new item when the URL changes', async () => {
    const { calls } = mockApi(routes('/stats'));
    render(AlbumPage);
    await waitFor(() => expect(heading()).toBeInTheDocument());
    pageStore.set({ url: url('Other') });
    await waitFor(() =>
      expect(calls.some((c) => c.startsWith('/stats/album?') && c.includes('album=Other'))).toBe(true)
    );
  });

  it('ignores a slow response for the previous URL', async () => {
    const { release } = stubDeferredFetch(
      (u) => {
        const name = u.searchParams.get('album') ?? '';
        const map: Record<string, unknown> = {
          '/stats/album': detail(name),
          '/stats/album-runs': { total: 0, runs: [] },
          '/stats/metrics-over-time': [],
          '/stats/recent': [],
          '/stats/top-tracks': [],
          '/stats/top-albums': []
        };
        return map[u.pathname];
      },
      (u) => u.searchParams.get('album') === 'Slow'
    );
    pageStore.set({ url: url('Slow') });
    render(AlbumPage);
    pageStore.set({ url: url('Fast') });
    await waitFor(() => expect(heading()).toHaveTextContent('Fast'));
    release();
    await new Promise((r) => setTimeout(r, 50));
    expect(heading()).toHaveTextContent('Fast');
  });

  it('puts the trend chart under the header so both share the cover colour', async () => {
    mockApi(routes('/stats'));
    const { container } = render(AlbumPage);
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument());
    const tinted = container.querySelector<HTMLElement>('.tinted')!;
    expect(tinted).toContainElement(screen.getByRole('heading', { level: 1 }));
    expect(tinted).toContainElement(screen.getByRole('img', { name: 'Listens over time' }));
  });
});
