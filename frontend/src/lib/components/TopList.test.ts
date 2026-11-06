import { render, screen } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import TopList from './TopList.svelte';

describe('TopList', () => {
  it('renders the title and ranked rows', () => {
    render(TopList, { props: { title: 'Top Artists', items: [
      { label: 'Daft Punk', count: 10 },
      { label: 'Kavinsky', count: 4 }
    ] } });
    expect(screen.getByRole('heading', { name: 'Top Artists' })).toBeInTheDocument();
    expect(screen.getByText('Daft Punk')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
  });

  it('renders an empty hint when there are no items', () => {
    render(TopList, { props: { title: 'Top Artists', items: [] } });
    expect(screen.getByText(/no data/i)).toBeInTheDocument();
  });

  it('renders platform search links for items with a query', () => {
    render(TopList, { props: { title: 'Top Tracks', items: [
      { label: 'Around the World', count: 5, query: 'Daft Punk Around the World' }
    ] } });
    const spotify = screen.getByRole('link', { name: /spotify/i });
    expect(spotify).toHaveAttribute(
      'href',
      'https://open.spotify.com/search/Daft%20Punk%20Around%20the%20World'
    );
    // All four linkhop platforms are offered.
    expect(screen.getAllByRole('link')).toHaveLength(4);
  });

  it('renders items with identical labels (same track title, different artists)', () => {
    render(TopList, { props: { title: 'Top Tracks', items: [
      { label: 'Paradise', count: 12, query: 'Coldplay Paradise' },
      { label: 'Paradise', count: 7, query: 'George Ezra Paradise' }
    ] } });
    expect(screen.getAllByText('Paradise')).toHaveLength(2);
  });

  it('omits platform links when an item has no query', () => {
    render(TopList, { props: { title: 'Top Artists', items: [
      { label: 'Daft Punk', count: 10 }
    ] } });
    expect(screen.queryByRole('link')).toBeNull();
  });
});

describe('TopList links and covers', () => {
  it('links the label when an item has an href', () => {
    render(TopList, { props: { title: 'Top Artists', items: [
      { label: 'Daft Punk', count: 10, href: '/artist?artist=Daft+Punk' },
      { label: 'Unknown album', count: 2 }
    ] } });
    expect(screen.getByRole('link', { name: 'Daft Punk' })).toHaveAttribute('href', '/artist?artist=Daft+Punk');
    expect(screen.queryByRole('link', { name: 'Unknown album' })).toBeNull();
  });

  it('shows covers only when enabled', () => {
    const items = [{ label: 'Discovery', count: 3, image: 'https://img/d.png' }];
    const { container, unmount } = render(TopList, { props: { title: 'Top Albums', items, covers: true } });
    const img = container.querySelector('img');
    expect(img).toHaveAttribute('src', 'https://img/d.png');
    expect(img).toHaveAttribute('alt', '');
    unmount();
    const plain = render(TopList, { props: { title: 'Top Albums', items } });
    expect(plain.container.querySelector('img')).toBeNull();
  });
});
