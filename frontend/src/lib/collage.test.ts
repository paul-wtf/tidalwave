import { describe, it, expect } from 'vitest';
import { TILE, collageAlbums, drawCollage, wrapLines, type CollageColors, type Tile } from './collage';

const colors: CollageColors = {
  tile: '#surface0', tileAlt: '#base', text: '#text', muted: '#muted', accent: '#accent'
};

function fakeContext() {
  const calls: unknown[][] = [];
  const ctx = {
    fillStyle: '',
    font: '',
    textBaseline: '',
    measureText: (text: string) => ({ width: text.length * 10 }),
    fillRect(...args: number[]) { calls.push(['fillRect', ctx.fillStyle, ...args]); },
    fillText(...args: unknown[]) { calls.push(['fillText', ctx.fillStyle, ...args]); },
    drawImage(...args: unknown[]) { calls.push(['drawImage', ...args]); }
  };
  return { ctx: ctx as unknown as CanvasRenderingContext2D, calls };
}

describe('collageAlbums', () => {
  it('takes the first n by n albums and skips rows without an album name', () => {
    const rows = [
      { album: 'A', artist: 'x', count: 9, image_url: 'a.png' },
      { album: null, artist: 'x', count: 8, image_url: null },
      ...Array.from({ length: 12 }, (_, i) => ({ album: `B${i}`, artist: 'y', count: 7 - i / 10 }))
    ];
    const picked = collageAlbums(rows, 3);
    expect(picked).toHaveLength(9);
    expect(picked[0]).toEqual({ album: 'A', artist: 'x', url: 'a.png' });
    expect(picked[1]).toEqual({ album: 'B0', artist: 'y', url: null });
    expect(picked.at(-1)?.album).toBe('B7');
  });
});

describe('wrapLines', () => {
  const measure = (text: string) => text.length * 10;

  it('breaks between words to fit the width', () => {
    expect(wrapLines(measure, 'Random Access Memories', 130, 4)).toEqual(['Random Access', 'Memories']);
  });

  it('ends the last allowed line with an ellipsis when text is left over', () => {
    expect(wrapLines(measure, 'one two three four five', 80, 2)).toEqual(['one two', 'three…']);
  });

  it('cuts a single word that is wider than the tile', () => {
    expect(wrapLines(measure, 'Supercalifragilistic', 100, 2)).toEqual(['Supercali…']);
  });
});

describe('drawCollage', () => {
  it('draws covers into their grid cells, cropped to a centred square', () => {
    const { ctx, calls } = fakeContext();
    const wide = { width: 600, height: 300 } as unknown as CanvasImageSource;
    const square = { width: 300, height: 300 } as unknown as CanvasImageSource;
    const tiles: Tile[] = Array.from({ length: 4 }, (_, i) => ({
      album: `A${i}`, artist: 'x', image: i === 3 ? wide : square
    }));
    drawCollage(ctx, 2, tiles, colors);
    const draws = calls.filter((c) => c[0] === 'drawImage');
    expect(draws).toEqual([
      ['drawImage', square, 0, 0, 300, 300, 0, 0, TILE, TILE],
      ['drawImage', square, 0, 0, 300, 300, TILE, 0, TILE, TILE],
      ['drawImage', square, 0, 0, 300, 300, 0, TILE, TILE, TILE],
      ['drawImage', wide, 150, 0, 300, 300, TILE, TILE, TILE, TILE]
    ]);
    expect(calls.some((c) => c[0] === 'fillText')).toBe(false);
  });

  it('writes artist and album onto a tile that has no cover', () => {
    const { ctx, calls } = fakeContext();
    const tiles: Tile[] = [
      { album: 'Discovery', artist: 'Daft Punk', image: null },
      { album: 'OutRun', artist: 'Kavinsky', image: null }
    ];
    drawCollage(ctx, 2, tiles, colors);
    const fills = calls.filter((c) => c[0] === 'fillRect');
    expect(fills).toContainEqual(['fillRect', '#surface0', 0, 0, TILE, TILE]);
    expect(fills).toContainEqual(['fillRect', '#base', TILE, 0, TILE, TILE]);
    const texts = calls.filter((c) => c[0] === 'fillText');
    expect(texts.map((c) => [c[1], c[2]])).toEqual([
      ['#muted', 'Daft Punk'], ['#text', 'Discovery'], ['#muted', 'Kavinsky'], ['#text', 'OutRun']
    ]);
    const [, , , x, y] = texts[1] as [string, string, string, number, number];
    expect(x).toBeGreaterThan(0);
    expect(x).toBeLessThan(TILE);
    expect(y).toBeLessThan(TILE);
  });

  it('fills cells beyond the last album with the plain tile colours', () => {
    const { ctx, calls } = fakeContext();
    drawCollage(ctx, 2, [{ album: 'A', artist: 'x', image: null }], colors);
    const tiles = calls.filter((c) => c[0] === 'fillRect' && c[4] === TILE && c[5] === TILE);
    expect(tiles).toEqual([
      ['fillRect', '#surface0', 0, 0, TILE, TILE],
      ['fillRect', '#base', TILE, 0, TILE, TILE],
      ['fillRect', '#base', 0, TILE, TILE, TILE],
      ['fillRect', '#surface0', TILE, TILE, TILE, TILE]
    ]);
    expect(calls.filter((c) => c[0] === 'fillText')).toHaveLength(2);
  });
});
