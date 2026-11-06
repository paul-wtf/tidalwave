import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import Discoveries from './Discoveries.svelte';

const data = {
  new_artists: [{ artist: 'Justice', first_listen: '2026-10-02T12:00:00Z', listens: 4, image_url: null }],
  new_tracks_count: 17,
  new_tracks: [{ track: 'D.A.N.C.E.', artist: 'Justice', first_listen: '2026-10-02T12:00:00Z', listens: 1 }],
  rediscoveries: [{ artist: 'Moby', previous_listen: '2025-01-03T12:00:00Z', gap_days: 400, listens: 2 }]
};
const none = { new_artists: [], new_tracks_count: 0, new_tracks: [], rediscoveries: [] };

describe('Discoveries', () => {
  it('renders new artists, new tracks and rediscoveries', () => {
    render(Discoveries, { discoveries: data });
    expect(screen.getByRole('heading', { name: 'Discoveries' })).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: 'Justice' })[0]).toHaveAttribute('href', '/artist?artist=Justice');
    expect(screen.getByText('4 listens, first heard 2026-10-02')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'New tracks (17)' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'D.A.N.C.E.' })).toHaveAttribute(
      'href', '/track?artist=Justice&track=D.A.N.C.E.');
    expect(screen.getByRole('link', { name: 'Moby' })).toBeInTheDocument();
    expect(screen.getByText(/back after 400 days, last heard 2025-01-03/)).toBeInTheDocument();
  });

  it('prefixes links in share mode', () => {
    render(Discoveries, { discoveries: data, base: '/s/tok' });
    expect(screen.getAllByRole('link', { name: 'Justice' })[0]).toHaveAttribute(
      'href', '/s/tok/artist?artist=Justice');
  });

  it('shows an empty state per list', () => {
    render(Discoveries, { discoveries: none });
    expect(screen.getByText('No new artists in this range.')).toBeInTheDocument();
    expect(screen.getByText('No new tracks in this range.')).toBeInTheDocument();
    expect(screen.getByText('No rediscoveries in this range.')).toBeInTheDocument();
  });
});
