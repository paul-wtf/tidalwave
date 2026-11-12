import type { AlbumCount } from '$lib/api/client';

/** Edge of one tile in canvas pixels: the size Last.fm serves covers in. */
export const TILE = 300;

export const COLLAGE_SIZES = [3, 4, 5] as const;
export type CollageSize = (typeof COLLAGE_SIZES)[number];

export interface CollageAlbum { album: string; artist: string; url: string | null }
export interface Tile { album: string; artist: string; image: CanvasImageSource | null }
export interface CollageColors {
  tile: string; tileAlt: string; text: string; muted: string; accent: string;
}

export function collageAlbums(rows: AlbumCount[], size: number): CollageAlbum[] {
  return rows
    .filter((r): r is AlbumCount & { album: string } => r.album != null)
    .slice(0, size * size)
    .map((r) => ({ album: r.album, artist: r.artist, url: r.image_url ?? null }));
}

type Measure = (text: string) => number;

function fit(measure: Measure, text: string, maxWidth: number): string {
  if (measure(text) <= maxWidth) return text;
  let cut = text;
  while (cut.length > 1 && measure(`${cut}…`) > maxWidth) cut = cut.slice(0, -1);
  return `${cut.trimEnd()}…`;
}

export function wrapLines(measure: Measure, text: string, maxWidth: number, maxLines: number): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let next = 0;
  while (next < words.length && lines.length < maxLines) {
    let line = words[next++];
    while (next < words.length && measure(`${line} ${words[next]}`) <= maxWidth) {
      line += ` ${words[next++]}`;
    }
    lines.push(line);
  }
  if (next < words.length) lines[lines.length - 1] += '…';
  return lines.map((line) => fit(measure, line, maxWidth));
}

const PAD = 24;
const FONT = '"JetBrains Mono Variable", "JetBrains Mono", ui-monospace, monospace';

function drawTextTile(
  ctx: CanvasRenderingContext2D, tile: Tile, x: number, y: number, colors: CollageColors
) {
  const measure: Measure = (text) => ctx.measureText(text).width;
  const width = TILE - 2 * PAD;
  ctx.fillStyle = colors.accent;
  ctx.fillRect(x + PAD, y + PAD, 14, 14);
  ctx.textBaseline = 'alphabetic';

  ctx.font = `700 26px ${FONT}`;
  const album = wrapLines(measure, tile.album, width, 4);
  ctx.font = `400 18px ${FONT}`;
  const artist = wrapLines(measure, tile.artist, width, 2);

  const albumTop = y + TILE - PAD - (album.length - 1) * 32;
  const artistTop = albumTop - 38 - (artist.length - 1) * 24;
  ctx.fillStyle = colors.muted;
  artist.forEach((line, i) => ctx.fillText(line, x + PAD, artistTop + i * 24));
  ctx.font = `700 26px ${FONT}`;
  ctx.fillStyle = colors.text;
  album.forEach((line, i) => ctx.fillText(line, x + PAD, albumTop + i * 32));
}

function sourceSize(image: CanvasImageSource): [number, number] {
  const img = image as { naturalWidth?: number; naturalHeight?: number; width: number; height: number };
  return [img.naturalWidth || img.width, img.naturalHeight || img.height];
}

/** Draws `size` by `size` tiles onto a canvas of `size * TILE` pixels. */
export function drawCollage(
  ctx: CanvasRenderingContext2D, size: number, tiles: Tile[], colors: CollageColors
): void {
  for (let i = 0; i < size * size; i++) {
    const col = i % size;
    const row = Math.floor(i / size);
    const x = col * TILE;
    const y = row * TILE;
    const tile = tiles[i];
    if (tile?.image) {
      const [w, h] = sourceSize(tile.image);
      const side = Math.min(w, h);
      ctx.drawImage(tile.image, (w - side) / 2, (h - side) / 2, side, side, x, y, TILE, TILE);
      continue;
    }
    ctx.fillStyle = (col + row) % 2 === 0 ? colors.tile : colors.tileAlt;
    ctx.fillRect(x, y, TILE, TILE);
    if (tile) drawTextTile(ctx, tile, x, y, colors);
  }
}

/** Resolves to null when the cover is missing, fails to load or is served
 *  without CORS headers, so the canvas never gets tainted. */
export function loadCover(url: string | null): Promise<HTMLImageElement | null> {
  if (!url) return Promise.resolve(null);
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = url;
  });
}

export function collageColors(root: Element): CollageColors {
  const style = getComputedStyle(root);
  const token = (name: string) => style.getPropertyValue(name).trim();
  return {
    tile: token('--surface0'),
    tileAlt: token('--base'),
    text: token('--text'),
    muted: token('--text-muted'),
    accent: token('--accent')
  };
}
