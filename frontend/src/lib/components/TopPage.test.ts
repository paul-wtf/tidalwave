import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
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

  it('opens the collage from the albums page with the albums of the range', async () => {
    HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', ''); };
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
    mockApi({
      '/stats/metrics-over-time': [],
      '/stats/top-albums': [{ album: 'Discovery', artist: 'Daft Punk', count: 12, image_url: null }]
    });
    render(TopPage, { props: { kind: 'albums' } });
    await screen.findByText('Discovery — Daft Punk');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Collage' }));
    expect(screen.getByRole('dialog', { name: 'Cover collage' })).toBeInTheDocument();
    expect(screen.getByText('Only 1 album in this range.')).toBeInTheDocument();
  });

  it('offers the collage in a share view', async () => {
    const { calls } = mockApi({
      '/shared/TOK/metrics-over-time': [],
      '/shared/TOK/top-albums': [{ album: 'Discovery', artist: 'Daft Punk', count: 12, image_url: null }]
    });
    render(TopPage, { props: { kind: 'albums', token: 'TOK' } });
    await screen.findByText('Discovery — Daft Punk');
    expect(screen.getByRole('button', { name: 'Collage' })).toBeInTheDocument();
    expect(calls.every((c) => c.startsWith('/shared/TOK/'))).toBe(true);
  });

  it.each(['artists', 'tracks'] as const)('has no collage on the %s page', async (kind) => {
    mockApi({ '/stats/metrics-over-time': [], '/stats/top-artists': [], '/stats/top-tracks': [] });
    render(TopPage, { props: { kind } });
    await screen.findAllByText('No data yet.');
    expect(screen.queryByRole('button', { name: 'Collage' })).not.toBeInTheDocument();
  });

  it('disables the collage while the range has no albums', async () => {
    mockApi({ '/stats/metrics-over-time': [], '/stats/top-albums': [] });
    render(TopPage, { props: { kind: 'albums' } });
    await screen.findAllByText('No data yet.');
    expect(screen.getByRole('button', { name: 'Collage' })).toBeDisabled();
  });

  it('switches the artists page between the list and the race', async () => {
    const { calls } = mockApi({
      '/stats/metrics-over-time': [],
      '/stats/top-artists': [{ artist: 'Kavinsky', count: 12, image_url: null }],
      '/stats/artist-race': {
        bucket: 'day', periods: ['2026-11-01T00:00:00'],
        artists: [{ artist: 'Kavinsky', image_url: null, totals: [12] }]
      }
    });
    render(TopPage, { props: { kind: 'artists' } });
    await screen.findByText('Kavinsky');
    expect(screen.getByRole('button', { name: 'List' })).toHaveAttribute('aria-pressed', 'true');
    expect(calls.some((c) => c.includes('artist-race'))).toBe(false);

    await userEvent.click(screen.getByRole('button', { name: 'Race' }));
    await screen.findByRole('slider', { name: 'Position in the race' });
    expect(screen.getByRole('button', { name: 'Race' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.queryByRole('heading', { name: 'Top Artists' })).toBeNull();
    expect(calls.filter((c) => c.includes('artist-race'))).toHaveLength(1);

    await userEvent.click(screen.getByRole('button', { name: 'List' }));
    expect(screen.getByRole('heading', { name: 'Top Artists' })).toBeInTheDocument();
  });

  it('offers the race in a share view', async () => {
    const { calls } = mockApi({
      '/shared/TOK/metrics-over-time': [],
      '/shared/TOK/top-artists': [{ artist: 'Kavinsky', count: 12, image_url: null }],
      '/shared/TOK/artist-race': {
        bucket: 'month', periods: ['2026-11-01T00:00:00'],
        artists: [{ artist: 'Kavinsky', image_url: null, totals: [12] }]
      }
    });
    render(TopPage, { props: { kind: 'artists', token: 'TOK' } });
    await screen.findByText('Kavinsky');
    await userEvent.click(screen.getByRole('button', { name: 'Race' }));
    await screen.findByRole('slider');
    expect(calls.every((c) => c.startsWith('/shared/TOK/'))).toBe(true);
  });

  it.each(['tracks', 'albums'] as const)('has no race on the %s page', async (kind) => {
    mockApi({ '/stats/metrics-over-time': [], '/stats/top-tracks': [], '/stats/top-albums': [] });
    render(TopPage, { props: { kind } });
    await screen.findAllByText('No data yet.');
    expect(screen.queryByRole('button', { name: 'Race' })).toBeNull();
  });
});
