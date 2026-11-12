import { describe, it, expect } from 'vitest';
import { artistHref, albumHref, trackHref, genreHref } from './links';

const NAME = 'AC/DC & "Friends" #1 ?+ Ünïcode';

function parse(href: string) {
  const url = new URL(href, 'http://localhost');
  return { path: url.pathname, params: url.searchParams, hash: url.hash };
}

describe('links', () => {
  it('round-trips awkward names through the artist link', () => {
    const { path, params, hash } = parse(artistHref('', NAME));
    expect(path).toBe('/artist');
    expect(params.get('artist')).toBe(NAME);
    expect(hash).toBe('');
  });

  it('round-trips awkward names through the album link', () => {
    const { path, params } = parse(albumHref('/s/tok', NAME, `${NAME} II`));
    expect(path).toBe('/s/tok/album');
    expect(params.get('artist')).toBe(NAME);
    expect(params.get('album')).toBe(`${NAME} II`);
  });

  it('round-trips awkward names through the track link', () => {
    const { path, params } = parse(trackHref('', NAME, NAME));
    expect(path).toBe('/track');
    expect(params.get('artist')).toBe(NAME);
    expect(params.get('track')).toBe(NAME);
  });

  it('round-trips a genre name through the genre link', () => {
    const { path, params } = parse(genreHref('/s/tok', 'drum & bass'));
    expect(path).toBe('/s/tok/genre');
    expect(params.get('genre')).toBe('drum & bass');
  });
});
