import { fireEvent, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest';
import { PLATFORMS } from '$lib/platforms';
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
    expect(screen.getAllByRole('link')).toHaveLength(PLATFORMS.length);
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

describe('TopList on a device that can hover', () => {
  const items = [
    { label: 'Nightcall', count: 9, query: 'Kavinsky Nightcall', href: '/track?t=1' },
    { label: 'Sunset', count: 4, query: 'The Midnight Sunset', href: '/track?t=2' }
  ];
  const spotify = () => screen.queryAllByRole('link', { name: /on spotify/i });

  beforeEach(() => {
    vi.spyOn(window, 'matchMedia').mockImplementation((query: string) => ({
      matches: query === '(hover: hover)', media: query, onchange: null,
      addListener: () => {}, removeListener: () => {},
      addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false
    }));
  });
  afterEach(() => vi.restoreAllMocks());

  it('renders no platform links, and so reserves no room, until a row is hovered', async () => {
    render(TopList, { props: { title: 'Top Tracks', items } });
    expect(spotify()).toHaveLength(0);

    await fireEvent.pointerEnter(screen.getByText('Sunset').closest('li')!);
    expect(spotify()).toHaveLength(1);
    expect(spotify()[0]).toHaveAccessibleName('Open “The Midnight Sunset” on Spotify');

    await fireEvent.pointerLeave(screen.getByText('Sunset').closest('li')!);
    expect(spotify()).toHaveLength(0);
  });

  it('shows a row\'s links while focus is in the row, so the keyboard reaches them', async () => {
    const user = userEvent.setup();
    render(TopList, { props: { title: 'Top Tracks', items } });

    await user.tab();
    expect(screen.getByRole('link', { name: 'Nightcall' })).toHaveFocus();
    expect(spotify()).toHaveLength(1);
    await user.tab();
    expect(spotify()[0]).toHaveFocus();

    for (let i = 0; i < PLATFORMS.length; i++) await user.tab();
    expect(screen.getByRole('link', { name: 'Sunset' })).toHaveFocus();
    expect(spotify()).toHaveLength(1);
    expect(spotify()[0]).toHaveAccessibleName('Open “The Midnight Sunset” on Spotify');
  });

  it('keeps the links of a row without a label link, which has nothing else to focus', () => {
    render(TopList, { props: { title: 'Top Tracks', items: [{ label: 'Loose', count: 1, query: 'Loose' }] } });
    expect(spotify()).toHaveLength(1);
  });
});
