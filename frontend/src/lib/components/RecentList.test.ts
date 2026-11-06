import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import RecentList from './RecentList.svelte';

describe('RecentList', () => {
  it('renders each recent track with its artist', () => {
    render(RecentList, { props: { items: [
      { track: 'Nightcall', artist: 'Kavinsky', album: 'OutRun', played_at: '2024-06-17T12:00:00Z' }
    ] } });
    expect(screen.getByText('Nightcall')).toBeInTheDocument();
    expect(screen.getByText('Kavinsky')).toBeInTheDocument();
  });
});

describe('RecentList links', () => {
  it('links the track and artist to their detail pages and shows the cover', () => {
    render(RecentList, { props: { base: '/s/tok', items: [
      { track: 'Nightcall', artist: 'AC/DC & Co', album: 'OutRun', played_at: '2024-06-17T12:00:00Z', image_url: 'https://img/o.png' }
    ] } });
    expect(screen.getByRole('link', { name: 'Nightcall' }))
      .toHaveAttribute('href', '/s/tok/track?artist=AC%2FDC+%26+Co&track=Nightcall');
    expect(screen.getByRole('link', { name: 'AC/DC & Co' }))
      .toHaveAttribute('href', '/s/tok/artist?artist=AC%2FDC+%26+Co');
    const { container } = { container: document.body };
    expect(container.querySelector('img')).toHaveAttribute('src', 'https://img/o.png');
  });
});
