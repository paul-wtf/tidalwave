import { render, screen, waitFor, within } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { mockApi } from '$lib/test/mockApi';
import { range } from '$lib/stores/range';

const pageStore = vi.hoisted(() => {
  const { writable } = require('svelte/store');
  return writable({ url: new URL('http://localhost/genre?genre=french+house') });
});
vi.mock('$app/stores', () => ({ page: pageStore }));

import GenrePage from './GenrePage.svelte';

const routes = (prefix: string) => ({
  [`${prefix}/genre`]: { genre: 'french house', listens: 1234, seconds: 7200, artists: 2 },
  [`${prefix}/metrics-over-time`]: [],
  [`${prefix}/top-artists`]: [
    { artist: 'Daft Punk', count: 900, image_url: null },
    { artist: 'Justice', count: 334, image_url: null }
  ]
});
const heading = () => screen.getByRole('heading', { level: 1 });

describe('GenrePage', () => {
  beforeEach(() => {
    range.set({ kind: 'rolling', key: '30d' });
    pageStore.set({ url: new URL('http://localhost/genre?genre=french+house') });
  });

  it('shows the totals and the top artists of the genre', async () => {
    mockApi(routes('/stats'));
    render(GenrePage);
    await waitFor(() => expect(heading()).toHaveTextContent('french house'));
    expect(screen.getByText('1,234')).toBeInTheDocument();
    expect(screen.getByText('2h 0m')).toBeInTheDocument();
    const list = within(screen.getByRole('heading', { name: 'Top Artists' }).closest('section')!);
    expect(list.getByRole('link', { name: 'Daft Punk' })).toHaveAttribute('href', '/artist?artist=Daft+Punk');
    expect(list.getByText('Justice')).toBeInTheDocument();
    expect(screen.getByText('Listens over time').closest('figure')).toBeInTheDocument();
  });

  it('asks every endpoint for the genre inside the selected range', async () => {
    const { calls } = mockApi(routes('/stats'));
    render(GenrePage);
    await waitFor(() => expect(calls).toHaveLength(3));
    for (const path of ['genre', 'metrics-over-time', 'top-artists']) {
      const call = calls.find((c) => c.startsWith(`/stats/${path}?`))!;
      expect(call).toContain('genre=french+house');
      expect(call).toContain('since=');
    }
  });

  it('reads the shared endpoints and links inside the share', async () => {
    const { calls } = mockApi(routes('/shared/tok'));
    render(GenrePage, { token: 'tok' });
    await waitFor(() => expect(heading()).toHaveTextContent('french house'));
    expect(calls.every((c) => c.startsWith('/shared/tok/') && !c.includes('since='))).toBe(true);
    expect(screen.getByRole('link', { name: 'Daft Punk' }))
      .toHaveAttribute('href', '/s/tok/artist?artist=Daft+Punk');
  });

  it('says so when nothing carries the genre', async () => {
    mockApi({});
    render(GenrePage);
    await waitFor(() => expect(screen.getByText('Nothing found for french house.')).toBeInTheDocument());
  });
});
