import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import Genres from './Genres.svelte';

const ranking = Array.from({ length: 12 }, (_, i) => ({
  genre: `genre ${i + 1}`, listens: 120 - i * 10, artists: 12 - i
}));

describe('Genres', () => {
  it('draws the top ten as bars scaled to the strongest genre', () => {
    const { container } = render(Genres, {
      genres: { genres: ranking, artists: 40, tagged_artists: 40 }
    });
    const rows = Array.from(container.querySelectorAll('li'));
    expect(rows).toHaveLength(10);
    expect(rows[0]).toHaveTextContent('genre 1');
    expect(rows[0]).toHaveTextContent('120');
    const bars = Array.from(container.querySelectorAll<HTMLElement>('.fill'));
    expect(bars[0].style.width).toBe('100%');
    expect(bars[5].style.width).toBe('58.333333333333336%');
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('links each genre to its page, also inside a share', () => {
    render(Genres, {
      genres: { genres: [{ genre: 'drum & bass', listens: 3, artists: 1 }], artists: 1, tagged_artists: 1 },
      base: '/s/tok'
    });
    expect(screen.getByRole('link', { name: 'drum & bass' }))
      .toHaveAttribute('href', '/s/tok/genre?genre=drum+%26+bass');
  });

  it('says that the ranking is incomplete while artists are still being looked up', () => {
    render(Genres, { genres: { genres: ranking, artists: 40, tagged_artists: 25 } });
    expect(screen.getByRole('status')).toHaveTextContent(
      'Tags for 25 of 40 artists so far. The ranking changes as the rest arrive.'
    );
    expect(screen.getByText('genre 1')).toBeInTheDocument();
  });

  it('shows no ranking before the first tags have arrived', () => {
    const { container } = render(Genres, { genres: { genres: [], artists: 40, tagged_artists: 0 } });
    expect(screen.getByRole('status')).toHaveTextContent(
      'Genres are still being fetched from Last.fm, a few artists with every sync.'
    );
    expect(container.querySelector('li')).toBeNull();
  });

  it('tells apart an empty range and artists without tags', () => {
    const { rerender } = render(Genres, { genres: { genres: [], artists: 0, tagged_artists: 0 } });
    expect(screen.getByText('No data yet.')).toBeInTheDocument();
    rerender({ genres: { genres: [], artists: 3, tagged_artists: 3 } });
    expect(screen.getByText('Last.fm has no genre tags for these artists.')).toBeInTheDocument();
  });
});
