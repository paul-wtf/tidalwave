import type { ArtistCount, AlbumCount, TrackCount } from '$lib/api/client';
import { artistHref, albumHref, trackHref } from '$lib/links';

export type ListItem = {
  label: string;
  count: number;
  query?: string;
  href?: string;
  image?: string | null;
};

export const artistItems = (rows: ArtistCount[], base: string): ListItem[] =>
  rows.map((r) => ({
    label: r.artist, count: r.count, query: r.artist,
    href: artistHref(base, r.artist), image: r.image_url
  }));

export const trackItems = (rows: TrackCount[], base: string): ListItem[] =>
  rows.map((r) => ({
    label: `${r.track} — ${r.artist}`, count: r.count, query: `${r.artist} ${r.track}`,
    href: trackHref(base, r.artist, r.track)
  }));

export const albumItems = (rows: AlbumCount[], base: string): ListItem[] =>
  rows.map((r) => ({
    label: `${r.album ?? 'Unknown album'} — ${r.artist}`, count: r.count,
    query: r.album ?? r.artist,
    href: r.album == null ? artistHref(base, r.artist) : albumHref(base, r.artist, r.album),
    image: r.image_url
  }));
