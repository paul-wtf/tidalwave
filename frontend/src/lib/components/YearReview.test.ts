import { render, screen, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach } from 'vitest';
import YearReview from './YearReview.svelte';
import { auth } from '$lib/stores/auth';
import type { YearReview as Review } from '$lib/api/client';
import { stubFetch, type Handler } from '$lib/test/stubFetch';

const summary = (total: number, seconds = 0) => ({
  total_listens: total, distinct_artists: 312, distinct_tracks: 2410, distinct_albums: 640,
  total_seconds: seconds
});

const review: Review = {
  year: 2025,
  summary: summary(12480, 2_880_000),
  previous: summary(10400),
  top_artists: [
    { artist: 'Boards of Canada', count: 640, image_url: 'http://img/boc.jpg' },
    { artist: 'Kavinsky', count: 420, image_url: null },
    { artist: 'Radiohead', count: 300, image_url: null }
  ],
  top_tracks: [{ track: 'Nightcall', artist: 'Kavinsky', count: 88 }],
  top_albums: [{ album: 'OutRun', artist: 'Kavinsky', count: 300, image_url: null }],
  months: Array.from({ length: 12 }, (_, i) => ({
    month: i + 1, listens: i === 5 ? 2000 : 800, seconds: 0, artists: 40,
    top_artist: i === 1 ? null : 'Boards of Canada'
  })),
  busiest_day: { date: '2025-06-07', listens: 142, top_artist: 'Boards of Canada' },
  first_listen: {
    track: 'Nightcall', artist: 'Kavinsky', album: 'OutRun',
    played_at: '2025-01-01T00:15:00+01:00', image_url: null
  },
  last_listen: {
    track: 'Nude', artist: 'Radiohead', album: 'In Rainbows',
    played_at: '2025-12-31T23:50:00+01:00', image_url: null
  },
  new_artists: {
    count: 87,
    top: [{ artist: 'Sigur Rós', first_listen: '2025-03-10T18:10:00+01:00', listens: 64, image_url: null }]
  },
  genres: { genres: [{ genre: 'electronic', listens: 5000, artists: 40 }], artists: 312, tagged_artists: 312 },
  decades: { decades: [{ decade: 2010, listens: 6000 }], known: 6000, unknown: 0, pending: 0 },
  longest_streak: { days: 41, start: '2025-02-01', end: '2025-03-13' },
  album_runs: { total: 0, runs: [] }
};

function stub(handler: Handler = () => undefined, base = '/stats') {
  return stubFetch((method, url, body) => {
    const res = handler(method, url, body);
    if (res) return res;
    if (url === `${base}/year/2025`) return Response.json(review);
    if (url === `${base}/years`) {
      return Response.json([{ year: 2026, listens: 900 }, { year: 2025, listens: 12480 }, { year: 2024, listens: 10400 }]);
    }
  });
}

describe('YearReview', () => {
  beforeEach(() => {
    auth.set({ user: { username: 'paul', is_admin: false, timezone: 'Europe/Berlin' } as never, loading: false });
  });

  it('opens with the totals of the year against the one before', async () => {
    stub();
    render(YearReview, { year: 2025 });
    const hero = await screen.findByRole('region', { name: '2025' });
    expect(hero).toHaveTextContent('12,480');
    expect(hero).toHaveTextContent('800h');
    expect(hero).toHaveTextContent('+20%');
    expect(hero).toHaveTextContent('312 artists');
  });

  it('shows the top artist first and the rest after it', async () => {
    stub();
    render(YearReview, { year: 2025 });
    const top = await screen.findByRole('region', { name: 'Top artists' });
    expect(within(top).getByRole('heading', { name: 'Boards of Canada' })).toBeInTheDocument();
    expect(top).toHaveTextContent('640 listens');
    expect(within(top).getByRole('link', { name: /Kavinsky/ })).toHaveAttribute('href', '/artist?artist=Kavinsky');
  });

  it('goes through the year month by month', async () => {
    stub();
    render(YearReview, { year: 2025 });
    const months = await screen.findByRole('region', { name: 'Month by month' });
    expect(within(months).getAllByRole('listitem')).toHaveLength(12);
    expect(within(months).getByRole('listitem', { name: /June/ })).toHaveTextContent('2,000');
    expect(months).toHaveTextContent('Your biggest month was June');
  });

  it('names the busiest day, the first and the last listen', async () => {
    stub();
    render(YearReview, { year: 2025 });
    expect(await screen.findByText(/7 Jun 2025/)).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Busiest day' })).toHaveTextContent('142 listens');
    const ends = screen.getByRole('region', { name: 'First and last' });
    expect(ends).toHaveTextContent('Nightcall');
    expect(ends).toHaveTextContent('Nude');
    expect(ends).toHaveTextContent('1 Jan 2025');
  });

  it('counts the new artists and the longest streak', async () => {
    stub();
    render(YearReview, { year: 2025 });
    const found = await screen.findByRole('region', { name: 'New to you' });
    expect(found).toHaveTextContent('87 artists');
    expect(found).toHaveTextContent('Sigur Rós');
    expect(screen.getByRole('region', { name: 'Longest streak' })).toHaveTextContent('41 days');
  });

  it('offers the other years with listens', async () => {
    stub();
    render(YearReview, { year: 2025 });
    const picker = await screen.findByRole('navigation', { name: 'Years' });
    expect(within(picker).getByRole('link', { name: '2024' })).toHaveAttribute('href', '/year/2024');
    expect(within(picker).getByRole('link', { name: '2025' })).toHaveAttribute('aria-current', 'page');
  });

  it('shares the year as a link to its review', async () => {
    let sent: unknown = null;
    stub((method, url, body) => {
      if (method === 'POST' && url === '/shares') {
        sent = JSON.parse(body!);
        return Response.json({ share_token: 'tok', label: '2025 in review', range_from: null, range_to: null, created_at: '' }, { status: 201 });
      }
    });
    render(YearReview, { year: 2025 });
    await userEvent.click(await screen.findByRole('button', { name: 'Share this year' }));
    expect(sent).toEqual({ start: '2025-01-01', end: '2026-01-01', label: '2025 in review' });
    expect(await screen.findByRole('textbox', { name: 'Share link' })).toHaveValue(
      `${location.origin}/s/tok/year/2025`
    );
  });

  it('works inside a share without offering to share again', async () => {
    stub(() => undefined, '/shared/tok');
    render(YearReview, { year: 2025, token: 'tok' });
    const top = await screen.findByRole('region', { name: 'Top artists' });
    expect(within(top).getByRole('link', { name: /Kavinsky/ })).toHaveAttribute('href', '/s/tok/artist?artist=Kavinsky');
    expect(screen.queryByRole('button', { name: 'Share this year' })).toBeNull();
    expect(within(screen.getByRole('navigation', { name: 'Years' })).getByRole('link', { name: '2024' }))
      .toHaveAttribute('href', '/s/tok/year/2024');
  });

  it('says so when a share does not cover the year', async () => {
    stub((_, url) => (url === '/shared/tok/year/2025' ? new Response('{}', { status: 404 }) : undefined), '/shared/tok');
    render(YearReview, { year: 2025, token: 'tok' });
    expect(await screen.findByText('This share does not cover 2025.')).toBeInTheDocument();
  });

  it('says so when the year has no listens', async () => {
    stub((_, url) => (url === '/stats/year/2025' ? Response.json({ ...review, summary: summary(0) }) : undefined));
    render(YearReview, { year: 2025 });
    expect(await screen.findByText('No listens in 2025.')).toBeInTheDocument();
  });

  it('shows every section at once when motion is reduced', async () => {
    stub();
    const { container } = render(YearReview, { year: 2025 });
    await screen.findByRole('region', { name: 'Top artists' });
    expect(container.querySelectorAll('.reveal')).toHaveLength(0);
  });
});
