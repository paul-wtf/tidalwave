import { render, screen, within } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import AlbumRuns from './AlbumRuns.svelte';

const run = (album: string, started_at: string, extra = {}) => ({
  artist: 'Daft Punk', album, started_at, tracks: 14, listens: 15, seconds: 3660, image_url: null, ...extra
});
const runs = {
  total: 5,
  runs: [
    run('Discovery', '2026-11-10T20:15:00+01:00'),
    run('Homework', '2026-11-02T09:00:00+01:00', { tracks: 6, listens: 6, seconds: 0 })
  ]
};

describe('AlbumRuns', () => {
  it('lists the runs with album, artist, track count, time and date', () => {
    render(AlbumRuns, { runs, tz: 'Europe/Berlin' });
    expect(screen.getByRole('heading', { name: 'Albums played through' })).toBeInTheDocument();
    const rows = screen.getAllByRole('listitem');
    expect(rows).toHaveLength(2);
    const first = within(rows[0]);
    expect(first.getByRole('link', { name: 'Discovery' }))
      .toHaveAttribute('href', '/album?artist=Daft+Punk&album=Discovery');
    expect(first.getByRole('link', { name: 'Daft Punk' })).toHaveAttribute('href', '/artist?artist=Daft+Punk');
    expect(rows[0]).toHaveTextContent('14 tracks, 1h 1m, 2026-11-10');
    expect(rows[1]).toHaveTextContent('6 tracks, 2026-11-02');
  });

  it('says how many more there are than it shows', () => {
    render(AlbumRuns, { runs });
    expect(screen.getByText('and 3 more in this range')).toBeInTheDocument();
  });

  it('links inside a share', () => {
    render(AlbumRuns, { runs: { total: 1, runs: [runs.runs[0]] }, base: '/s/tok', tz: null });
    expect(screen.getByRole('link', { name: 'Discovery' }))
      .toHaveAttribute('href', '/s/tok/album?artist=Daft+Punk&album=Discovery');
    expect(screen.queryByText(/more in this range/)).toBeNull();
  });

  it('has an empty state', () => {
    render(AlbumRuns, { runs: { total: 0, runs: [] } });
    expect(screen.getByText('No album played through in this range.')).toBeInTheDocument();
  });

  it('counts the runs of one album in the heading and leaves the names out', () => {
    const { rerender } = render(AlbumRuns, { runs, single: true, tz: 'Europe/Berlin' });
    expect(screen.getByRole('heading', { name: 'Played through 5 times' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Discovery' })).toBeNull();
    expect(screen.getAllByRole('listitem')[0]).toHaveTextContent('10 Nov 2026, 20:15');
    expect(screen.getAllByRole('listitem')[0]).toHaveTextContent('14 tracks, 1h 1m');
    rerender({ runs: { total: 1, runs: [runs.runs[0]] }, single: true });
    expect(screen.getByRole('heading', { name: 'Played through once' })).toBeInTheDocument();
  });
});
