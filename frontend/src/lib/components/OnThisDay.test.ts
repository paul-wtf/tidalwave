import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import OnThisDay from './OnThisDay.svelte';

const years = [
  { year: 2025, listens: 12, top_tracks: [{ track: 'Aerodynamic', artist: 'Daft Punk', count: 3 }] },
  { year: 2024, listens: 1, top_tracks: [{ track: 'Around the World', artist: 'Daft Punk', count: 1 }] }
];

describe('OnThisDay', () => {
  it('lists each year with its count and top tracks', () => {
    render(OnThisDay, { years });
    expect(screen.getByRole('heading', { name: 'On this day' })).toBeInTheDocument();
    expect(screen.getByText('2025')).toBeInTheDocument();
    expect(screen.getByText('12 listens')).toBeInTheDocument();
    expect(screen.getByText('1 listen')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Aerodynamic' })).toHaveAttribute(
      'href', '/track?artist=Daft+Punk&track=Aerodynamic');
  });

  it('prefixes links in share mode', () => {
    render(OnThisDay, { years, base: '/s/tok' });
    expect(screen.getAllByRole('link', { name: 'Daft Punk' })[0]).toHaveAttribute(
      'href', '/s/tok/artist?artist=Daft+Punk');
  });

  it('shows the empty state', () => {
    render(OnThisDay, { years: [] });
    expect(screen.getByText('Nothing on this day in earlier years.')).toBeInTheDocument();
  });
});
