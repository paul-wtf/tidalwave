// The streaming platforms linkhop supports. Scrobbles only give us text
// (artist + title), so each link opens the platform's search for that query —
// reliable without needing per-track IDs.

export type PlatformId = 'spotify' | 'tidal' | 'apple_music' | 'youtube_music' | 'deezer';

export interface Platform {
  id: PlatformId;
  name: string;
  /** Brand colour, used to tint the icon on hover. */
  brand: string;
  /** Build a web URL that opens a search for `query` on this platform. */
  search: (query: string) => string;
}

export const PLATFORMS: Platform[] = [
  {
    id: 'spotify',
    name: 'Spotify',
    brand: '#1ed760',
    search: (q) => `https://open.spotify.com/search/${encodeURIComponent(q)}`
  },
  {
    id: 'tidal',
    name: 'Tidal',
    brand: '#25d1da',
    search: (q) => `https://tidal.com/search?q=${encodeURIComponent(q)}`
  },
  {
    id: 'apple_music',
    name: 'Apple Music',
    brand: '#fa243c',
    search: (q) => `https://music.apple.com/search?term=${encodeURIComponent(q)}`
  },
  {
    id: 'youtube_music',
    name: 'YouTube Music',
    brand: '#ff0000',
    search: (q) => `https://music.youtube.com/search?q=${encodeURIComponent(q)}`
  },
  {
    id: 'deezer',
    name: 'Deezer',
    brand: '#a238ff',
    search: (q) => `https://www.deezer.com/search/${encodeURIComponent(q)}`
  }
];
