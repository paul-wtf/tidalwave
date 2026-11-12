import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import Decades from './Decades.svelte';

const decades = [
  { decade: 1970, listens: 20 }, { decade: 1980, listens: 0 },
  { decade: 1990, listens: 80 }, { decade: 2000, listens: 40 }
];

describe('Decades', () => {
  it('draws one bar per decade, scaled to the strongest', () => {
    const { container } = render(Decades, { decades: { decades, known: 140, unknown: 60, pending: 0 } });
    expect(screen.getByRole('img', { name: 'Listens by release decade' })).toBeInTheDocument();
    const bars = Array.from(container.querySelectorAll<HTMLElement>('.bar'));
    expect(bars.map((b) => b.style.height)).toEqual(['25%', '0%', '100%', '50%']);
    expect(Array.from(container.querySelectorAll('.barlabels span')).map((s) => s.textContent))
      .toEqual(['1970s', '1980s', '1990s', '2000s']);
    expect(container.querySelector('.col')).toHaveAttribute('title', '1970s: 20 listens');
  });

  it('states the share of listens it covers', () => {
    render(Decades, { decades: { decades, known: 140, unknown: 60, pending: 0 } });
    expect(screen.getByText('Covers 70 % of the listens in this range (140 of 200). The rest has no known release year.'))
      .toBeInTheDocument();
  });

  it('says how much is still being looked up', () => {
    render(Decades, { decades: { decades, known: 140, unknown: 60, pending: 30 } });
    expect(screen.getByText(
      'Covers 70 % of the listens in this range (140 of 200). Release years for another 15 % are still being looked up.'
    )).toBeInTheDocument();
  });

  it('needs no caveat when every listen has a year', () => {
    render(Decades, { decades: { decades, known: 140, unknown: 0, pending: 0 } });
    expect(screen.getByText('Covers all listens in this range.')).toBeInTheDocument();
  });

  it('draws no chart without a known year', () => {
    const { container, rerender } = render(Decades, {
      decades: { decades: [], known: 0, unknown: 50, pending: 50 }
    });
    expect(screen.getByText('Release years are still being looked up on MusicBrainz.')).toBeInTheDocument();
    expect(container.querySelector('.barchart')).toBeNull();
    rerender({ decades: { decades: [], known: 0, unknown: 50, pending: 0 } });
    expect(screen.getByText('No release years are known for the listens in this range.')).toBeInTheDocument();
    rerender({ decades: { decades: [], known: 0, unknown: 0, pending: 0 } });
    expect(screen.getByText('No data yet.')).toBeInTheDocument();
  });
});
