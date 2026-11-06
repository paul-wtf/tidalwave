import { describe, it, expect } from 'vitest';
import { artistItems, trackItems, albumItems } from './listItems';

describe('listItems', () => {
  it('links an album without a title to its artist', () => {
    const [item] = albumItems([{ album: null, artist: 'Daft Punk', count: 3, image_url: null }], '');
    expect(item.label).toBe('Unknown album — Daft Punk');
    expect(item.href).toBe('/artist?artist=Daft+Punk');
    expect(item.query).toBe('Daft Punk');
  });

  it('keeps the share prefix on the artist link of an unknown album', () => {
    const [item] = albumItems([{ album: null, artist: 'AC/DC', count: 1, image_url: null }], '/s/tok');
    expect(item.href).toBe('/s/tok/artist?artist=AC%2FDC');
  });

  it('links named albums with artist and album', () => {
    const [item] = albumItems([{ album: 'Discovery', artist: 'Daft Punk', count: 3, image_url: 'u' }], '');
    const url = new URL(item.href!, 'http://x');
    expect(url.pathname).toBe('/album');
    expect(url.searchParams.get('album')).toBe('Discovery');
    expect(url.searchParams.get('artist')).toBe('Daft Punk');
    expect(item.image).toBe('u');
  });

  it('prefixes every link with the share base', () => {
    const base = '/s/tok';
    const items = [
      ...artistItems([{ artist: 'A', count: 1, image_url: null }], base),
      ...trackItems([{ track: 'T', artist: 'A', count: 1 }], base),
      ...albumItems([{ album: 'B', artist: 'A', count: 1, image_url: null }], base)
    ];
    expect(items).toHaveLength(3);
    for (const i of items) expect(i.href!.startsWith('/s/tok/')).toBe(true);
  });

  it('takes artist covers from image_url and leaves tracks without one', () => {
    expect(artistItems([{ artist: 'A', count: 1, image_url: 'img' }], '')[0].image).toBe('img');
    expect(trackItems([{ track: 'T', artist: 'A', count: 1 }], '')[0].image).toBeUndefined();
  });
});
