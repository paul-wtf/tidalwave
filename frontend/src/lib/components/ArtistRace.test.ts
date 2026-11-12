import { render, screen, waitFor, fireEvent } from '@testing-library/svelte';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { mockApi } from '$lib/test/mockApi';
import { range } from '$lib/stores/range';
import ArtistRace from './ArtistRace.svelte';

const race = {
  bucket: 'day',
  periods: ['2026-11-01T00:00:00', '2026-11-02T00:00:00', '2026-11-04T00:00:00'],
  artists: [
    { artist: 'Late', image_url: null, totals: [1, 3, 7] },
    { artist: 'Steady', image_url: null, totals: [2, 4, 4] },
    { artist: 'Early', image_url: null, totals: [3, 3, 3] }
  ]
};
const row = (name: string) => screen.getByText(name).closest<HTMLElement>('li')!;
const places = () => ['Late', 'Steady', 'Early'].map((n) => row(n).dataset.rank);
const allowMotion = () =>
  vi.stubGlobal('matchMedia', (query: string) => ({ matches: false, media: query }));

describe('ArtistRace', () => {
  beforeEach(() => range.set({ kind: 'rolling', key: '30d' }));
  afterEach(() => vi.useRealTimers());

  it('opens on the final standings with the last date', async () => {
    mockApi({ '/stats/artist-race': race });
    render(ArtistRace);
    await waitFor(() => expect(screen.getByText('Late')).toBeInTheDocument());
    expect(places()).toEqual(['0', '1', '2']);
    expect(screen.getByText('4 Nov 2026')).toBeInTheDocument();
    expect(row('Late')).toHaveTextContent('7');
    expect(row('Late').querySelector<HTMLElement>('.fill')!.style.width).toBe('100%');
    expect(row('Early').style.getPropertyValue('--place')).toBe('2');
  });

  it('asks once, with the range and its bucket', async () => {
    const { calls } = mockApi({ '/stats/artist-race': race });
    render(ArtistRace);
    await waitFor(() => expect(screen.getByText('Late')).toBeInTheDocument());
    expect(calls).toHaveLength(1);
    expect(calls[0]).toContain('/stats/artist-race?');
    expect(calls[0]).toContain('bucket=day');
    expect(calls[0]).toContain('since=');
  });

  it('follows the scrubber', async () => {
    mockApi({ '/stats/artist-race': race });
    render(ArtistRace);
    const scrubber = await screen.findByRole('slider', { name: 'Position in the race' });
    expect(scrubber).toHaveAttribute('max', '2');
    await fireEvent.input(scrubber, { target: { value: '0' } });
    expect(screen.getByText('1 Nov 2026')).toBeInTheDocument();
    expect(places()).toEqual(['2', '1', '0']);
    expect(row('Early')).toHaveTextContent('3');
    expect(scrubber).toHaveAttribute('aria-valuetext', '1 Nov 2026');
  });

  it('shows only the scrubber under reduced motion', async () => {
    mockApi({ '/stats/artist-race': race });
    render(ArtistRace);
    await screen.findByRole('slider');
    expect(screen.queryByRole('button', { name: 'Play' })).toBeNull();
  });

  it('plays from the start, bucket by bucket, and stops at the end', async () => {
    allowMotion();
    mockApi({ '/stats/artist-race': race });
    render(ArtistRace);
    const play = await screen.findByRole('button', { name: 'Play' });
    vi.useFakeTimers();
    await fireEvent.click(play);
    expect(screen.getByText('1 Nov 2026')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(700);
    expect(screen.getByText('2 Nov 2026')).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(700);
    expect(screen.getByText('4 Nov 2026')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(2000);
    expect(screen.getByText('4 Nov 2026')).toBeInTheDocument();
  });

  it('pauses where it is', async () => {
    allowMotion();
    mockApi({ '/stats/artist-race': race });
    render(ArtistRace);
    const play = await screen.findByRole('button', { name: 'Play' });
    vi.useFakeTimers();
    await fireEvent.click(play);
    await vi.advanceTimersByTimeAsync(700);
    await fireEvent.click(screen.getByRole('button', { name: 'Pause' }));
    await vi.advanceTimersByTimeAsync(3000);
    expect(screen.getByText('2 Nov 2026')).toBeInTheDocument();
  });

  it('labels monthly buckets with the month', async () => {
    mockApi({ '/stats/artist-race': { ...race, bucket: 'month', periods: ['2026-09-01T00:00:00', '2026-10-01T00:00:00', '2026-11-01T00:00:00'] } });
    render(ArtistRace);
    await waitFor(() => expect(screen.getByText('Nov 2026')).toBeInTheDocument());
  });

  it('lets the server pick the bucket in a share and links inside it', async () => {
    const { calls } = mockApi({ '/shared/tok/artist-race': race });
    render(ArtistRace, { token: 'tok' });
    await waitFor(() => expect(screen.getByText('Late')).toBeInTheDocument());
    expect(calls).toEqual(['/shared/tok/artist-race']);
    expect(screen.getByRole('link', { name: 'Late' })).toHaveAttribute('href', '/s/tok/artist?artist=Late');
  });

  it('has an empty and an error state', async () => {
    mockApi({ '/stats/artist-race': { bucket: 'day', periods: [], artists: [] } });
    const { unmount } = render(ArtistRace);
    await waitFor(() => expect(screen.getByText('No data yet.')).toBeInTheDocument());
    unmount();
    mockApi({});
    render(ArtistRace);
    await waitFor(() => expect(screen.getByText('Could not load the race. Please try again.')).toBeInTheDocument());
  });
});
