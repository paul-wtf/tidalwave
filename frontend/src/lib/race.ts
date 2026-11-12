import type { RaceArtist } from '$lib/api/client';

export const RACE_SIZE = 10;

export type Standing = { rank: number; total: number; shown: boolean };

/** Place and total of every artist at one frame, in the order the artists came in. */
export function standings(
  artists: RaceArtist[], frame: number, size: number
): { max: number; rows: Standing[] } {
  const order = artists
    .map((a, index) => ({ index, artist: a.artist, total: a.totals[frame] ?? 0 }))
    .sort((a, b) => b.total - a.total || (a.artist < b.artist ? -1 : 1));
  const rows: Standing[] = new Array(artists.length);
  order.forEach((entry, rank) => {
    rows[entry.index] = { rank, total: entry.total, shown: rank < size && entry.total > 0 };
  });
  return { max: Math.max(1, order[0]?.total ?? 0), rows };
}

const RACE_MS = 20_000;

/** Time per frame: the whole race takes about RACE_MS, within a watchable pace. */
export function stepMs(frames: number): number {
  return Math.min(700, Math.max(150, Math.round(RACE_MS / Math.max(1, frames))));
}
